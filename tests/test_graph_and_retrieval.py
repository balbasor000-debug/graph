import json
from importlib.resources import files

import networkx as nx
import pytest

from ecommerce_kg.examples import SAMPLE_QUERIES
from ecommerce_kg.graph import export_graph, graph_stats, load_graph, word_occurrences
from ecommerce_kg.query import QueryPlan
from ecommerce_kg.retrieval import GraphRetriever, QueryBudgetExceeded
from ecommerce_kg.schema import RELATIONSHIPS


@pytest.mark.parametrize("question,column,expected", [
    (
        "Which products from Brand X are supplied by Vendor Y?", "p.id",
        ["P001", "P002", "P003", "P011"],
    ),
    (
        "Which products contain the keyword banana?", "p.id",
        ["P004", "P005", "P006", "P007", "P008"],
    ),
    ("How many products contain the keyword banana?", "count(p)", [5]),
    (
        "Which products did Alice Johnson order?", "p.name",
        ["Wireless Headphones", "Mechanical Keyboard", "Ceramic Coffee Mug", "Trail Water Bottle"],
    ),
    (
        "Which customers have delivered orders containing products with the keyword banana?",
        "c.name", ["Bob Smith", "Carla Gomez"],
    ),
    ("What is the total value of delivered orders?", "sum(o.total_cents)", [30996]),
    (
        "Which vendors supply Wireless Headphones?", "v.name", ["Vendor Y", "Digital Depot"],
    ),
    (
        "What products are in Electronics and cost less than $50?", "p.price_cents", [2999, 4999],
    ),
    (
        "What items are in order O001, with quantities and line totals?",
        "item.line_total_cents", [7999, 2500],
    ),
    ("Which products from Brand X are supplied by Orchard Supply?", "p.id", []),
])
def test_sample_answers(service, graph, question, column, expected):
    answer = service.ask(question)
    assert [row.values[column] for row in answer.retrieval.rows] == expected
    assert "offline" in answer.backend
    for row in answer.retrieval.rows:
        assert all(identifier in graph for identifier in row.node_ids)
        for edge in row.edges:
            assert graph.edges[edge["source"], edge["target"]]["relationship"] == (
                edge["relationship"]
            )


def test_graph_counts_relationships_totals_and_keyword_values(graph):
    assert nx.is_frozen(graph)
    assert graph_stats(graph)["nodes"] == 34
    assert graph_stats(graph)["edges"] == 67
    assert word_occurrences(graph, "banana") == 5
    assert [identifier for identifier, attrs in graph.nodes(data=True)
            if attrs.get("keyword") == "banana"] == ["P004", "P005", "P006", "P007", "P008"]
    for source, target, attrs in graph.edges(data=True):
        assert (graph.nodes[source]["kind"], graph.nodes[target]["kind"]) == (
            RELATIONSHIPS[attrs["relationship"]]
        )
    assert graph.nodes["O001"]["total_cents"] == 10499
    assert graph.edges["O001", "P003"]["quantity"] == 2


def test_export_preserves_exact_word_count(graph, tmp_path):
    destination = tmp_path / "graph.json"
    export_graph(graph, destination)
    restored = nx.node_link_graph(json.loads(destination.read_text()), edges="edges")
    assert word_occurrences(restored, "banana") == 5
    assert restored.number_of_edges() == 67
    # Also inspect every serialized value, not just the keyword field.
    assert destination.read_text().count('"banana"') == 5


@pytest.mark.parametrize("corruption,match", [
    ("duplicate", "Duplicate entity ID"),
    ("dangling", "Dangling reference"),
    ("wrong_vendor", "vendor does not supply"),
    ("extra_keyword", "exactly 5 banana"),
    ("duplicate_line", "Duplicate relationship"),
])
def test_loader_rejects_inconsistent_data(tmp_path, corruption, match):
    data = json.loads(files("ecommerce_kg").joinpath("data/ecommerce.json").read_text())
    if corruption == "duplicate":
        data["brands"].append(data["brands"][0])
    elif corruption == "dangling":
        data["products"][0]["brand_id"] = "missing"
    elif corruption == "wrong_vendor":
        data["orders"][0]["vendor_id"] = "V002"
    elif corruption == "extra_keyword":
        data["brands"][0]["name"] = "banana"
    else:
        data["orders"][0]["items"].append(data["orders"][0]["items"][0])
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=match):
        load_graph(path)


def test_word_counter_includes_metadata_and_edge_values_and_word_boundaries(graph):
    copy = graph.copy()
    copy.graph["note"] = "BANANA and banana; bananas is not the whole word."
    copy.edges["O001", "P001"]["note"] = "banana"
    assert word_occurrences(copy, "banana") == 8


def test_deduplication_merges_all_supporting_paths(retriever):
    query = SAMPLE_QUERIES[
        "Which customers have delivered orders containing products with the keyword banana?"
    ]
    result = retriever.execute(query)
    assert result.matched_bindings == 5
    assert result.total_rows == 2
    bob = result.rows[0]
    assert {"O002", "O007", "P004", "P005"} <= set(bob.node_ids)
    assert len(bob.edges) == 5


def test_aggregates_do_not_double_count_orders_after_joining_products(retriever):
    base = {
        "nodes": [{"alias": "o", "kind": "Order"}, {"alias": "p", "kind": "Product"}],
        "edges": [{"alias": "i", "source": "o", "target": "p", "relationship": "CONTAINS"}],
        "filters": [{"alias": "o", "field": "status", "op": "eq", "value": "delivered"}],
        "aggregate": {"op": "sum", "alias": "o", "field": "total_cents"},
        "limit": 1,
    }
    result = retriever.execute(QueryPlan.model_validate(base))
    assert result.matched_bindings == 10
    assert result.rows[0].values == {"sum(o.total_cents)": 30996}
    base["aggregate"] = {"op": "count", "alias": "o"}
    assert retriever.execute(QueryPlan.model_validate(base)).rows[0].values == {"count(o)": 5}
    base["aggregate"] = {"op": "sum", "alias": "i", "field": "line_total_cents"}
    assert retriever.execute(QueryPlan.model_validate(base)).rows[0].values == {
        "sum(i.line_total_cents)": 30996
    }


def test_limit_and_empty_aggregate_are_explicit(retriever):
    query = SAMPLE_QUERIES["Which products contain the keyword banana?"].model_copy(deep=True)
    query.limit = 2
    result = retriever.execute(query)
    assert len(result.rows) == 2
    assert result.total_rows == 5 and result.truncated
    query = SAMPLE_QUERIES["How many products contain the keyword banana?"].model_copy(deep=True)
    query.filters[0].value = "not present"
    result = retriever.execute(query)
    assert result.rows[0].values == {"count(p)": 0}
    assert result.rows[0].node_ids == []


def test_edge_filters_and_numeric_sort(retriever):
    query = SAMPLE_QUERIES[
        "What items are in order O001, with quantities and line totals?"
    ].model_dump()
    query["filters"].append({"alias": "item", "field": "quantity", "op": "gte", "value": 2})
    result = retriever.execute(QueryPlan.model_validate(query))
    assert result.rows[0].values["p.id"] == "P003"
    query = SAMPLE_QUERIES["Which products from Brand X are supplied by Vendor Y?"].model_dump()
    query["order_by"] = [{"alias": "p", "field": "price_cents", "direction": "desc"}]
    result = retriever.execute(QueryPlan.model_validate(query))
    assert [row.values["p.id"] for row in result.rows] == ["P002", "P001", "P011", "P003"]


def test_traversal_budget_rejects_incomplete_results(graph):
    retriever = GraphRetriever(graph, max_states=1)
    with pytest.raises(QueryBudgetExceeded):
        retriever.execute(SAMPLE_QUERIES["How many products contain the keyword banana?"])


def test_not_equal_keyword_includes_products_without_a_keyword(retriever):
    query = SAMPLE_QUERIES["Which products contain the keyword banana?"].model_copy(deep=True)
    query.filters[0].op = "ne"
    result = retriever.execute(query)
    assert [row.values["p.id"] for row in result.rows] == [
        "P001", "P002", "P003", "P009", "P010", "P011", "P012",
    ]
    assert all(row.values["p.keyword"] is None for row in result.rows)


@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_missing_sort_values_are_last_in_both_directions(retriever, direction):
    query = QueryPlan.model_validate({
        "nodes": [{"alias": "p", "kind": "Product"}],
        "select": [{"alias": "p", "field": "id"}, {"alias": "p", "field": "keyword"}],
        "order_by": [
            {"alias": "p", "field": "keyword", "direction": direction},
            {"alias": "p", "field": "id", "direction": "asc"},
        ],
        "limit": 5,
    })
    result = retriever.execute(query)
    assert [row.values["p.id"] for row in result.rows] == [
        "P004", "P005", "P006", "P007", "P008",
    ]
    assert result.total_rows == 12 and result.truncated


@pytest.mark.parametrize("entity,field", [
    ("products", "name"), ("customers", "city"), ("brands", "id"),
])
def test_loader_rejects_whitespace_only_text(tmp_path, entity, field):
    data = json.loads(files("ecommerce_kg").joinpath("data/ecommerce.json").read_text())
    data[entity][0][field] = " \t "
    path = tmp_path / "blank.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_graph(path)


def test_loader_normalizes_padded_text_and_references(tmp_path):
    data = json.loads(files("ecommerce_kg").joinpath("data/ecommerce.json").read_text())
    data["products"][0]["id"] = " P001 "
    data["brands"][0]["name"] = " Brand X "
    data["products"][3]["keyword"] = " banana "
    data["orders"][0]["items"][0]["product_id"] = " P001 "
    path = tmp_path / "padded.json"
    path.write_text(json.dumps(data))
    graph = load_graph(path)
    assert "P001" in graph and " P001 " not in graph
    assert graph.nodes["B001"]["name"] == "Brand X"
    assert graph.nodes["P004"]["keyword"] == "banana"
    assert word_occurrences(graph, "banana") == 5


def test_case_insensitive_id_lookup_cannot_be_ambiguous(tmp_path):
    data = json.loads(files("ecommerce_kg").joinpath("data/ecommerce.json").read_text())
    data["brands"].append({"id": "b001", "name": "Another brand"})
    path = tmp_path / "ambiguous.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate entity ID"):
        load_graph(path)


def test_date_range_filters_and_case_insensitive_contains(retriever):
    query = QueryPlan.model_validate({
        "nodes": [{"alias": "o", "kind": "Order"}],
        "filters": [
            {"alias": "o", "field": "placed_on", "op": "gte", "value": "2026-09-05"},
            {"alias": "o", "field": "placed_on", "op": "lte", "value": "2026-09-10"},
        ],
        "select": [{"alias": "o", "field": "id"}],
    })
    assert [row.values["o.id"] for row in retriever.execute(query).rows] == [
        "O003", "O004", "O005",
    ]
    query = QueryPlan.model_validate({
        "nodes": [{"alias": "p", "kind": "Product"}],
        "filters": [{"alias": "p", "field": "name", "op": "contains", "value": "WIRELESS"}],
        "select": [{"alias": "p", "field": "id"}],
    })
    assert [row.values["p.id"] for row in retriever.execute(query).rows] == ["P001", "P009"]


def test_match_budget_boundary_does_not_return_partial_aggregates(graph):
    query = SAMPLE_QUERIES["How many products contain the keyword banana?"]
    with pytest.raises(QueryBudgetExceeded):
        GraphRetriever(graph, max_matches=4).execute(query)
    assert GraphRetriever(graph, max_matches=5).execute(query).rows[0].values == {"count(p)": 5}


def test_historical_order_totals_do_not_change_with_catalog_prices(tmp_path):
    data = json.loads(files("ecommerce_kg").joinpath("data/ecommerce.json").read_text())
    data["products"][2]["price_cents"] = 9999
    path = tmp_path / "new_prices.json"
    path.write_text(json.dumps(data))
    graph = load_graph(path)
    assert graph.nodes["P003"]["price_cents"] == 9999
    assert graph.nodes["O001"]["total_cents"] == 10499
    result = GraphRetriever(graph).execute(SAMPLE_QUERIES[
        "What is the total value of delivered orders?"
    ])
    assert result.rows[0].values == {"sum(o.total_cents)": 30996}
