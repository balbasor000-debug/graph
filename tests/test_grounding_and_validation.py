import pytest
from pydantic import ValidationError

from ecommerce_kg.examples import SAMPLE_QUERIES
from ecommerce_kg.llm import OfflineBackend, UnsupportedQuestion
from ecommerce_kg.query import AnswerPlan, QueryPlan
from ecommerce_kg.service import GroundingError, RetrievalService, render_answer


@pytest.mark.parametrize("mutation", [
    "unknown_field", "unknown_relation", "wrong_direction", "unknown_alias", "extra_code",
    "disconnected", "bad_limit", "wrong_filter_type", "bad_sum", "duplicate_alias",
])
def test_invalid_or_unsafe_queries_are_rejected(mutation):
    data = SAMPLE_QUERIES["Which products from Brand X are supplied by Vendor Y?"].model_dump()
    if mutation == "unknown_field":
        data["select"][0]["field"] = "__import__('os').system('whoami')"
    elif mutation == "unknown_relation":
        data["edges"][0]["relationship"] = "DELETE"
    elif mutation == "wrong_direction":
        data["edges"][0]["source"], data["edges"][0]["target"] = "b", "p"
    elif mutation == "unknown_alias":
        data["filters"][0]["alias"] = "missing"
    elif mutation == "extra_code":
        data["python"] = "delete_all_nodes()"
    elif mutation == "disconnected":
        data["edges"] = []
    elif mutation == "bad_limit":
        data["limit"] = 10000
    elif mutation == "wrong_filter_type":
        data["filters"][0]["value"] = 42
    elif mutation == "bad_sum":
        data["select"], data["order_by"] = [], []
        data["aggregate"] = {"op": "sum", "alias": "p", "field": "name"}
    else:
        data["nodes"].append(data["nodes"][0])
    with pytest.raises(ValidationError):
        QueryPlan.model_validate(data)


@pytest.mark.parametrize("evidence_ids", [["R999"], [], ["R1", "R1"], ["R2", "R1", "R3", "R4"]])
def test_fabricated_missing_duplicate_or_reordered_evidence_is_rejected(retriever, evidence_ids):
    result = retriever.execute(SAMPLE_QUERIES[
        "Which products from Brand X are supplied by Vendor Y?"
    ])
    with pytest.raises(GroundingError):
        render_answer(result, AnswerPlan(evidence_ids=evidence_ids, style="table"))


def test_free_form_factual_text_is_not_an_answer_contract():
    with pytest.raises(ValidationError):
        AnswerPlan.model_validate({
            "evidence_ids": ["R1"], "style": "table", "answer": "An invented product costs $1."
        })


def test_no_matches_bypass_llm_and_question_bounds(retriever):
    class NoAnswerBackend(OfflineBackend):
        def plan_answer(self, question, result):
            pytest.fail("LLM must not be invoked for an empty row result")

    service = RetrievalService(retriever, NoAnswerBackend())
    assert service.ask(
        "Which products from Brand X are supplied by Orchard Supply?"
    ).markdown == "No matching data was found in the graph."
    for question in (" ", "x" * 2001):
        with pytest.raises(ValueError):
            service.ask(question)


def test_unknown_offline_question_does_not_invent_an_answer(service):
    with pytest.raises(UnsupportedQuestion):
        service.ask("What will the weather be tomorrow?")


def test_currency_rendering_and_count_are_not_confused(retriever):
    query = QueryPlan.model_validate({
        "nodes": [{"alias": "o_cents", "kind": "Order"}],
        "aggregate": {"op": "count", "alias": "o_cents"},
    })
    result = retriever.execute(query)
    text = render_answer(result, AnswerPlan(evidence_ids=["R1"], style="bullets"))
    assert "USD" not in text
    assert ": 7 [R1]" in text


@pytest.mark.parametrize("value", [True, 3.5])
def test_numeric_filters_accept_only_integer_graph_values(value):
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({
            "nodes": [{"alias": "p", "kind": "Product"}],
            "filters": [{"alias": "p", "field": "price_cents", "op": "eq", "value": value}],
            "select": [{"alias": "p", "field": "id"}],
        })
