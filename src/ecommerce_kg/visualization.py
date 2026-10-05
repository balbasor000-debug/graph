"""Dependency-free Graphviz DOT output for the optional Streamlit demo."""

import json

import networkx as nx

COLORS = {
    "Product": "#a7f3d0", "Brand": "#bfdbfe", "Category": "#ddd6fe",
    "Vendor": "#fed7aa", "Order": "#fecaca", "Customer": "#bae6fd",
}


def graph_dot(graph: nx.DiGraph, node_ids=None) -> str:
    selected = set(graph.nodes) if node_ids is None else set(node_ids)
    lines = [
        "digraph KG {", 'rankdir=LR; bgcolor="transparent";',
        'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=10];',
        'edge [fontname="Arial", fontsize=8];',
    ]
    for identifier, attrs in graph.nodes(data=True):
        if identifier in selected:
            label = f"{attrs['kind']}: {attrs.get('name', identifier)}\n{identifier}"
            if attrs.get("keyword"):
                label += f"\nkeyword={attrs['keyword']}"
            lines.append(
                f"{json.dumps(identifier)} [label={json.dumps(label)}, "
                f"fillcolor={json.dumps(COLORS[attrs['kind']])}];"
            )
    for source, target, attrs in graph.edges(data=True):
        if source in selected and target in selected:
            label = attrs["relationship"]
            if "quantity" in attrs:
                label += f" (qty {attrs['quantity']})"
            lines.append(
                f"{json.dumps(source)} -> {json.dumps(target)} [label={json.dumps(label)}];"
            )
    return "\n".join([*lines, "}"])
