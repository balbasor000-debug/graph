"""Typed, bounded, read-only graph query language. No generated code is evaluated."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schema import EDGE_FIELDS, NODE_FIELDS, RELATIONSHIPS, EntityKind, RelationshipKind

Alias = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,15}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NodeMatch(StrictModel):
    alias: Alias
    kind: EntityKind


class EdgeMatch(StrictModel):
    alias: Alias
    source: Alias
    target: Alias
    relationship: RelationshipKind


class FieldRef(StrictModel):
    alias: Alias
    field: str

    @property
    def column(self) -> str:
        return f"{self.alias}.{self.field}"


class PropertyFilter(FieldRef):
    op: Literal["eq", "ne", "contains", "gt", "gte", "lt", "lte"]
    value: str | int | float | bool


class Sort(FieldRef):
    direction: Literal["asc", "desc"] = "asc"


class Aggregate(StrictModel):
    op: Literal["count", "sum"]
    alias: Alias
    field: str | None = None

    @property
    def column(self) -> str:
        target = self.alias if self.field is None else f"{self.alias}.{self.field}"
        return f"{self.op}({target})"


class QueryPlan(StrictModel):
    nodes: Annotated[list[NodeMatch], Field(min_length=1, max_length=6)]
    edges: Annotated[list[EdgeMatch], Field(max_length=8)] = []
    filters: Annotated[list[PropertyFilter], Field(max_length=16)] = []
    select: Annotated[list[FieldRef], Field(max_length=12)] = []
    aggregate: Aggregate | None = None
    distinct: bool = True
    order_by: Annotated[list[Sort], Field(max_length=3)] = []
    limit: Annotated[int, Field(ge=1, le=100)] = 20

    @model_validator(mode="after")
    def validate_graph_schema(self):
        nodes = {node.alias: node.kind for node in self.nodes}
        edges = {edge.alias: edge for edge in self.edges}
        if len(nodes) != len(self.nodes) or len(edges) != len(self.edges) or nodes.keys() & edges:
            raise ValueError("All node/edge aliases must be unique")
        connected = {alias: set() for alias in nodes}
        for edge in self.edges:
            if edge.source not in nodes or edge.target not in nodes:
                raise ValueError("Every edge endpoint must reference a declared node alias")
            endpoints = (nodes[edge.source], nodes[edge.target])
            if endpoints != RELATIONSHIPS[edge.relationship]:
                raise ValueError(f"Wrong direction or endpoint types for {edge.relationship}")
            connected[edge.source].add(edge.target)
            connected[edge.target].add(edge.source)
        visited, stack = set(), [self.nodes[0].alias]
        while stack:
            alias = stack.pop()
            if alias not in visited:
                visited.add(alias)
                stack.extend(connected[alias] - visited)
        if len(visited) != len(nodes):
            raise ValueError("Query patterns must be connected; Cartesian products are prohibited")

        def field_type(alias, field):
            if alias in nodes:
                allowed = NODE_FIELDS[nodes[alias]]
            elif alias in edges:
                allowed = EDGE_FIELDS[edges[alias].relationship]
            else:
                raise ValueError(f"Unknown alias: {alias}")
            if field not in allowed:
                raise ValueError(f"Unknown property {alias}.{field}")
            return allowed[field]

        for ref in [*self.select, *self.order_by]:
            field_type(ref.alias, ref.field)
        for condition in self.filters:
            expected = field_type(condition.alias, condition.field)
            if type(condition.value) is not expected:
                raise ValueError(f"{condition.column} requires a {expected.__name__} filter value")
            if condition.op == "contains" and expected is not str:
                raise ValueError("contains requires a string property")
            if condition.op in {"gt", "gte", "lt", "lte"}:
                if expected is not int and condition.field != "placed_on":
                    raise ValueError("Range comparisons require numeric fields or ISO dates")
            if condition.field == "placed_on":
                if date.fromisoformat(condition.value).isoformat() != condition.value:
                    raise ValueError("Date filters must be ISO YYYY-MM-DD")
        columns = [ref.column for ref in self.select]
        if len(set(columns)) != len(columns):
            raise ValueError("Selected columns must be unique")
        if self.aggregate:
            agg = self.aggregate
            if agg.alias not in nodes and agg.alias not in edges:
                raise ValueError("Aggregate requires a declared alias")
            if self.select or self.order_by:
                raise ValueError("Aggregate queries cannot also select/sort rows")
            if agg.op == "sum":
                if agg.field is None or field_type(agg.alias, agg.field) is not int:
                    raise ValueError("sum requires a numeric field")
            elif agg.field is not None:
                raise ValueError("count counts unique entities/edges; omit field")
        elif not self.select:
            raise ValueError("A query requires selected fields or an aggregate")
        if any(sort.column not in columns for sort in self.order_by):
            raise ValueError("Sort fields must also be selected")
        return self


class QueryDecision(StrictModel):
    """Null is an explicit abstention if a question is unsupported or ambiguous."""

    query: QueryPlan | None


class AnswerPlan(StrictModel):
    """The LLM can choose presentation, but cannot introduce factual text."""

    evidence_ids: Annotated[list[str], Field(max_length=100)]
    style: Literal["table", "bullets"]
