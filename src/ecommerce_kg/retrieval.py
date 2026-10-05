"""Execute validated graph patterns; attach provenance to every result row."""

import json
from dataclasses import asdict, dataclass

import networkx as nx

from .query import QueryPlan


class QueryBudgetExceeded(ValueError):
    pass


@dataclass
class EvidenceRow:
    evidence_id: str
    values: dict
    node_ids: list[str]
    edges: list[dict]


@dataclass
class RetrievalResult:
    rows: list[EvidenceRow]
    total_rows: int
    matched_bindings: int
    truncated: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _matches(actual, condition) -> bool:
    if actual is None:
        return False
    wanted = condition.value
    if isinstance(actual, str):
        actual, wanted = actual.casefold(), wanted.casefold()
    if condition.op == "eq":
        return actual == wanted
    if condition.op == "ne":
        return actual != wanted
    if condition.op == "contains":
        return wanted in actual
    if condition.op == "gt":
        return actual > wanted
    if condition.op == "gte":
        return actual >= wanted
    if condition.op == "lt":
        return actual < wanted
    return actual <= wanted


class GraphRetriever:
    def __init__(self, graph: nx.DiGraph, max_states: int = 50_000, max_matches: int = 10_000):
        self.graph = graph
        self.max_states = max_states
        self.max_matches = max_matches

    def execute(self, plan: QueryPlan) -> RetrievalResult:
        # Revalidate even if a caller used Pydantic model_construct or mutated a plan.
        plan = QueryPlan.model_validate(plan.model_dump())
        graph = self.graph
        candidates = {}
        for node in plan.nodes:
            filters = [condition for condition in plan.filters if condition.alias == node.alias]
            candidates[node.alias] = {
                identifier for identifier, attrs in graph.nodes(data=True)
                if attrs["kind"] == node.kind
                and all(_matches(attrs.get(condition.field), condition) for condition in filters)
            }
        bindings, states = [], 0

        def edge_matches(edge, source, target):
            attrs = graph.get_edge_data(source, target)
            return attrs is not None and attrs["relationship"] == edge.relationship and all(
                _matches(attrs.get(condition.field), condition)
                for condition in plan.filters if condition.alias == edge.alias
            )

        def search(bound):
            nonlocal states
            states += 1
            if states > self.max_states:
                raise QueryBudgetExceeded("Query exceeded traversal budget; narrow its filters")
            if len(bound) == len(plan.nodes):
                if len(bindings) >= self.max_matches:
                    raise QueryBudgetExceeded("Query exceeded match budget; narrow its filters")
                bindings.append(dict(bound))
                return
            unbound = set(candidates) - bound.keys()

            def score(alias):
                links = sum(
                    (edge.source == alias and edge.target in bound)
                    or (edge.target == alias and edge.source in bound)
                    for edge in plan.edges
                )
                return (-links, len(candidates[alias]), alias)

            alias = min(unbound, key=score)
            allowed = set(candidates[alias])
            for edge in plan.edges:
                if edge.source == alias and edge.target in bound:
                    target = bound[edge.target]
                    allowed &= {
                        source for source in graph.predecessors(target)
                        if edge_matches(edge, source, target)
                    }
                elif edge.target == alias and edge.source in bound:
                    source = bound[edge.source]
                    allowed &= {
                        target for target in graph.successors(source)
                        if edge_matches(edge, source, target)
                    }
            for identifier in sorted(allowed):
                bound[alias] = identifier
                search(bound)
                del bound[alias]

        search({})
        edge_lookup = {edge.alias: edge for edge in plan.edges}

        def identity(binding, alias):
            if alias in edge_lookup:
                edge = edge_lookup[alias]
                return (binding[edge.source], binding[edge.target])
            return binding[alias]

        def field_value(binding, alias, field):
            identifier = identity(binding, alias)
            attrs = graph.edges[identifier] if alias in edge_lookup else graph.nodes[identifier]
            return attrs.get(field)

        def provenance(matches):
            nodes, edges = set(), set()
            for binding in matches:
                nodes.update(binding.values())
                for edge in plan.edges:
                    edges.add((binding[edge.source], edge.relationship, binding[edge.target]))
            return sorted(nodes), [
                {"source": source, "relationship": relationship, "target": target}
                for source, relationship, target in sorted(edges)
            ]

        if plan.aggregate:
            agg = plan.aggregate
            # Each entity/edge contributes once, even if a join reaches it multiple times.
            unique = {identity(binding, agg.alias): binding for binding in bindings}
            value = len(unique) if agg.op == "count" else sum(
                field_value(binding, agg.alias, agg.field) for binding in unique.values()
            )
            nodes, edges = provenance(bindings)
            row = EvidenceRow("R1", {agg.column: value}, nodes, edges)
            return RetrievalResult([row], 1, len(bindings), False)

        groups = {}
        for index, binding in enumerate(bindings):
            values = {ref.column: field_value(binding, ref.alias, ref.field) for ref in plan.select}
            key = json.dumps(values, sort_keys=True) if plan.distinct else str(index)
            if key not in groups:
                groups[key] = (values, [])
            groups[key][1].append(binding)
        grouped = list(groups.values())
        for sort in reversed(plan.order_by):
            grouped.sort(
                key=lambda group: (
                    group[0][sort.column] is None,
                    group[0][sort.column] if group[0][sort.column] is not None else "",
                ),
                reverse=sort.direction == "desc",
            )
        rows = []
        for index, (values, matches) in enumerate(grouped[:plan.limit], start=1):
            nodes, edges = provenance(matches)
            rows.append(EvidenceRow(f"R{index}", values, nodes, edges))
        return RetrievalResult(rows, len(grouped), len(bindings), len(grouped) > plan.limit)
