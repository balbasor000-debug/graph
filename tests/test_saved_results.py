import json
from pathlib import Path

import pytest

from ecommerce_kg.examples import SAMPLE_QUERIES
from ecommerce_kg.query import QueryPlan

EXPECTED = [
    ("Product", {"P001", "P002", "P003", "P011"}),
    ("Product", {"P004", "P005", "P006", "P007", "P008"}),
    ("Product", 5),
    ("Product", {"P001", "P002", "P003", "P011"}),
    ("Customer", {"CU002", "CU003"}),
    ("Order", 30996),
    ("Vendor", {"V001", "V003"}),
    ("Product", {"P009", "P010"}),
    ("Product", {"P001", "P003"}),
    ("Product", set()),
]


@pytest.mark.parametrize("filename", ["sample_results.json", "groq_sample_results.json"])
@pytest.mark.parametrize("index", range(10))
def test_saved_answers_replay_exactly_and_match_independent_graph_facts(
    graph, retriever, filename, index,
):
    path = Path(__file__).parents[1] / "docs" / filename
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved) == 10
    answer = saved[index]
    assert answer["question"] == list(SAMPLE_QUERIES)[index]
    assert answer["backend"] == (
        "groq" if filename.startswith("groq") else "offline-demo (deterministic; no LLM calls)"
    )
    query = QueryPlan.model_validate(answer["query"])
    result = retriever.execute(query)
    assert result.to_dict() == answer["retrieval"]
    kind, expected = EXPECTED[index]
    aliases = {node.alias for node in query.nodes if node.kind == kind}
    if isinstance(expected, int):
        assert query.aggregate is not None and query.aggregate.alias in aliases
        assert query.aggregate.op == ("count" if index == 2 else "sum")
        assert list(result.rows[0].values.values()) == [expected]
        return
    columns = [ref.column for ref in query.select if ref.alias in aliases and ref.field == "id"]
    if columns:
        actual = {row.values[columns[0]] for row in result.rows}
    else:
        columns = [ref.column for ref in query.select
                   if ref.alias in aliases and ref.field == "name"]
        assert columns, "The answer must project the requested entity's ID or name"
        identifiers = {
            attrs["name"]: identifier for identifier, attrs in graph.nodes(data=True)
            if attrs["kind"] == kind
        }
        actual = {identifiers[row.values[columns[0]]] for row in result.rows}
    assert actual == expected
    if index == 1:
        keywords = [ref.column for ref in query.select if ref.field == "keyword"]
        assert keywords
        assert [row.values[keywords[0]] for row in result.rows] == ["banana"] * 5
    if index == 8:
        quantity = next(ref.column for ref in query.select if ref.field == "quantity")
        total = next(ref.column for ref in query.select if ref.field == "line_total_cents")
        assert {(row.values[quantity], row.values[total]) for row in result.rows} == {
            (1, 7999), (2, 2500),
        }


def test_saved_live_question_outside_offline_fixtures_replays_correctly(retriever):
    path = Path(__file__).parents[1] / "docs" / "groq_additional_result.json"
    answer = json.loads(path.read_text(encoding="utf-8"))
    assert answer["question"] not in SAMPLE_QUERIES
    assert answer["backend"] == "groq" and answer["model"] == "openai/gpt-oss-20b"
    query = QueryPlan.model_validate(answer["query"])
    result = retriever.execute(query)
    assert result.to_dict() == answer["retrieval"]
    aliases = {node.alias for node in query.nodes if node.kind == "Vendor"}
    column = next(ref.column for ref in query.select if ref.alias in aliases and ref.field == "id")
    assert {row.values[column] for row in result.rows} == {"V001", "V002"}
