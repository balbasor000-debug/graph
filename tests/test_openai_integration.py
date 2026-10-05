import json

import httpx
import pytest
from openai import OpenAI

from ecommerce_kg.examples import SAMPLE_QUERIES
from ecommerce_kg.llm import BackendError, OpenAIBackend, UnsupportedQuestion
from ecommerce_kg.query import AnswerPlan, QueryDecision
from ecommerce_kg.service import RetrievalService


def mock_client(handler):
    return OpenAI(
        api_key="test-only-not-a-real-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def completion(content, refusal=None):
    return httpx.Response(200, json={
        "id": "mock-completion", "object": "chat.completion", "created": 0,
        "model": "gpt-4o-mini", "choices": [{
            "index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": content, "refusal": refusal},
        }],
    })


def test_real_sdk_two_structured_calls_retrieve_then_present(graph, retriever):
    question = "Which products from Brand X are supplied by Vendor Y?"
    calls = []

    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        calls.append(body)
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        # Some structured-output models do not accept an explicit temperature.
        assert "temperature" not in body
        if len(calls) == 1:
            decision = QueryDecision(query=SAMPLE_QUERIES[question])
            return completion(decision.model_dump_json())
        payload = json.loads(body["messages"][1]["content"])
        ids = [row["evidence_id"] for row in payload["evidence"]["rows"]]
        return completion(AnswerPlan(evidence_ids=ids, style="bullets").model_dump_json())

    with mock_client(handler) as client:
        backend = OpenAIBackend(graph, client=client)
        answer = RetrievalService(retriever, backend).ask(question)
    assert len(calls) == 2
    assert "Wireless Headphones" in answer.markdown
    assert "USD 79.99" in answer.markdown
    assert answer.backend == "openai"
    first_payload = json.loads(calls[0]["messages"][1]["content"])
    assert first_payload["schema"]["nodes"]["Product"]["keyword"] == "str"
    assert first_payload["schema"]["relationships"]["CONTAINS"]["properties"]["quantity"] == "int"
    second_payload = json.loads(calls[1]["messages"][1]["content"])
    assert second_payload["evidence"] == answer.retrieval.to_dict()
    assert [row["values"]["p.id"] for row in second_payload["evidence"]["rows"]] == (
        ["P001", "P002", "P003", "P011"]
    )


@pytest.mark.parametrize("response,exception", [
    (completion('{"query": null}'), UnsupportedQuestion),
    (completion(None, refusal="Cannot comply"), BackendError),
    (httpx.Response(401, json={"error": {"message": "Bad key", "type": "authentication_error"}}),
     BackendError),
])
def test_abstention_refusal_and_api_failure_do_not_fallback(graph, response, exception):
    with mock_client(lambda request: response) as client:
        backend = OpenAIBackend(graph, client=client)
        with pytest.raises(exception):
            backend.plan_query("Tell me facts outside the graph")


def test_live_backend_requires_key(graph, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIBackend(graph)


@pytest.mark.parametrize("content", ["not valid JSON", '{"query": {}}'])
def test_malformed_structured_responses_fail_with_a_backend_error(graph, content):
    with mock_client(lambda request: completion(content)) as client:
        backend = OpenAIBackend(graph, client=client)
        with pytest.raises(BackendError, match="invalid structured response"):
            backend.plan_query("Which products contain the keyword banana?")


def test_empty_completion_choices_fail_with_a_backend_error(graph):
    response = httpx.Response(200, json={
        "id": "empty", "object": "chat.completion", "created": 0,
        "model": "gpt-4o-mini", "choices": [],
    })
    with mock_client(lambda request: response) as client:
        with pytest.raises(BackendError, match="usable structured response"):
            OpenAIBackend(graph, client=client).plan_query("List the products")
