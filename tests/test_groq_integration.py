import json

import httpx
import pytest
from openai import OpenAI

from ecommerce_kg.examples import SAMPLE_QUERIES
from ecommerce_kg.llm import BackendError, GroqBackend, OfflineBackend, create_backend
from ecommerce_kg.query import AnswerPlan, QueryDecision
from ecommerce_kg.service import RetrievalService


def test_groq_real_sdk_uses_groq_endpoint_for_both_stages(graph, retriever):
    question = "Which products from Brand X are supplied by Vendor Y?"
    calls = []

    def handler(request):
        assert request.url.host == "api.groq.com"
        assert request.url.path == "/openai/v1/chat/completions"
        body = json.loads(request.content)
        calls.append(body)
        assert body["model"] == "openai/gpt-oss-20b"
        assert body["response_format"]["json_schema"]["strict"] is True
        if len(calls) == 1:
            schema = body["response_format"]["json_schema"]["schema"]
            value_types = schema["$defs"]["PropertyFilter"]["properties"]["value"]["anyOf"]
            assert {variant["type"] for variant in value_types} == {"string", "integer"}
            content = QueryDecision(query=SAMPLE_QUERIES[question]).model_dump_json()
        else:
            payload = json.loads(body["messages"][1]["content"])
            ids = [row["evidence_id"] for row in payload["evidence"]["rows"]]
            content = AnswerPlan(evidence_ids=ids, style="table").model_dump_json()
        return httpx.Response(200, json={
            "id": "groq-mock", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{
                "index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }],
        })

    with OpenAI(
        api_key="test-only-not-a-real-key", base_url=GroqBackend.base_url,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0,
    ) as client:
        answer = RetrievalService(retriever, GroqBackend(graph, client=client)).ask(question)
    assert answer.backend == "groq"
    assert len(calls) == 2
    assert "Wireless Headphones" in answer.markdown and "USD 79.99" in answer.markdown
    assert json.loads(calls[1]["messages"][1]["content"])["evidence"] == (
        answer.retrieval.to_dict()
    )


def test_groq_configuration_is_independent_of_openai(graph, monkeypatch):
    options = {}

    def client_factory(**kwargs):
        options.update(kwargs)
        return object()

    monkeypatch.setenv("GROQ_API_KEY", "test-only-groq-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("OPENAI_API_KEY", "different-test-only-key")
    monkeypatch.setattr("ecommerce_kg.llm.OpenAI", client_factory)
    backend = create_backend("groq", graph)
    assert isinstance(backend, GroqBackend)
    assert backend.model == "openai/gpt-oss-120b"
    assert options["api_key"] == "test-only-groq-key"
    assert options["base_url"] == "https://api.groq.com/openai/v1"
    assert create_backend("groq", graph, "custom-model").model == "custom-model"
    assert isinstance(create_backend("offline", graph), OfflineBackend)
    with pytest.raises(ValueError, match="Unknown backend"):
        create_backend("unknown", graph)


def test_groq_requires_its_own_key(graph, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-openai-key")
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        GroqBackend(graph)


def test_groq_api_errors_are_controlled_and_do_not_expose_provider_details(graph):
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "private provider detail"}})

    with OpenAI(
        api_key="test-only-key", base_url=GroqBackend.base_url,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0,
    ) as client:
        with pytest.raises(BackendError, match="Groq request failed") as error:
            GroqBackend(graph, client=client).plan_query("List products")
    assert "private provider detail" not in str(error.value)
