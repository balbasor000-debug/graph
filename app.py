"""Run with: streamlit run app.py (install the optional [ui] dependencies)."""

import json
from pathlib import Path

import networkx as nx
import streamlit as st
from dotenv import load_dotenv

from ecommerce_kg.examples import SAMPLE_QUERIES
from ecommerce_kg.graph import graph_stats, load_graph
from ecommerce_kg.llm import BackendError, OfflineBackend, OpenAIBackend
from ecommerce_kg.retrieval import GraphRetriever
from ecommerce_kg.service import RetrievalService
from ecommerce_kg.visualization import graph_dot

load_dotenv(Path(__file__).parent / ".env", override=False)
st.set_page_config(page_title="E-commerce Knowledge Graph", layout="wide")
st.title("E-commerce Knowledge Graph")
st.caption("Question → validated graph query → retrieved evidence → verified answer")


@st.cache_resource
def get_graph():
    return load_graph()


graph = get_graph()
stats = graph_stats(graph)
with st.sidebar:
    mode = st.radio("Backend", ["Offline demo", "OpenAI live"])
    st.caption(
        "Offline uses predefined queries. OpenAI live supports new natural-language questions "
        "and makes query-planning and evidence-presentation calls."
    )
    st.metric("Entities", stats["nodes"])
    st.metric("Relationships", stats["edges"])
    st.metric("banana occurrences", stats["banana_occurrences"])

ask_tab, graph_tab, data_tab = st.tabs(["Ask the graph", "Graph explorer", "Dataset & schema"])
with ask_tab:
    sample = st.selectbox("Sample question", list(SAMPLE_QUERIES))
    question = st.text_area("Question", value=sample, key=f"question_{sample}")
    if st.button("Retrieve answer", type="primary"):
        try:
            backend = OpenAIBackend(graph) if mode == "OpenAI live" else OfflineBackend()
            with st.spinner("Planning, retrieving and verifying evidence…"):
                answer = RetrievalService(GraphRetriever(graph), backend).ask(question)
            st.session_state["answer"] = answer
        except (ValueError, BackendError) as exc:
            st.session_state.pop("answer", None)
            st.error(str(exc))
    if "answer" in st.session_state:
        answer = st.session_state["answer"]
        st.subheader("Answer")
        st.caption(f"Question: {answer.question} | Backend: {answer.backend}")
        st.markdown(answer.markdown)
        with st.expander("Validated graph query"):
            st.json(answer.query.model_dump())
        with st.expander("Retrieved evidence and relationship provenance"):
            st.json(answer.retrieval.to_dict())
        st.download_button(
            "Download answer + query + evidence", json.dumps(answer.to_dict(), indent=2),
            file_name="answer.json", mime="application/json",
        )

with graph_tab:
    view = st.selectbox(
        "Graph view", ["All entities", "banana neighborhood", "Last answer evidence"]
    )
    selected = None
    selected_edges = None
    if view == "banana neighborhood":
        tagged = {identifier for identifier, attrs in graph.nodes(data=True)
                  if attrs.get("keyword") == "banana"}
        selected = set(tagged)
        for identifier in tagged:
            selected.update(graph.predecessors(identifier))
            selected.update(graph.successors(identifier))
    elif view == "Last answer evidence":
        answer = st.session_state.get("answer")
        selected = (
            {identifier for row in answer.retrieval.rows for identifier in row.node_ids}
            if answer is not None else set()
        )
        selected_edges = (
            {
                (edge["source"], edge["relationship"], edge["target"])
                for row in answer.retrieval.rows for edge in row.edges
            }
            if answer is not None else set()
        )
    st.graphviz_chart(graph_dot(graph, selected, edge_ids=selected_edges))
    st.caption("Node colors identify entity types; arrows show relationship direction.")
    st.download_button(
        "Download knowledge graph JSON",
        json.dumps(nx.node_link_data(graph, edges="edges"), indent=2),
        file_name="knowledge_graph.json", mime="application/json",
    )

with data_tab:
    st.json(stats)
    st.subheader("Entities")
    st.dataframe([attrs for _, attrs in graph.nodes(data=True)], hide_index=True)
    st.subheader("Relationships")
    st.dataframe([
        {"source": source, "target": target, **attrs}
        for source, target, attrs in graph.edges(data=True)
    ], hide_index=True)
