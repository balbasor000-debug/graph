import pytest

from ecommerce_kg.graph import load_graph
from ecommerce_kg.llm import OfflineBackend
from ecommerce_kg.retrieval import GraphRetriever
from ecommerce_kg.service import RetrievalService


@pytest.fixture(scope="session")
def graph():
    return load_graph()


@pytest.fixture
def retriever(graph):
    return GraphRetriever(graph)


@pytest.fixture
def service(retriever):
    return RetrievalService(retriever, OfflineBackend())
