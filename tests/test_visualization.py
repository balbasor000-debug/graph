from ecommerce_kg.visualization import graph_dot


def test_evidence_graph_shows_only_retrieved_relationships(graph):
    nodes = {"O001", "V001", "P001"}
    edges = {("O001", "FULFILLED_BY", "V001"), ("V001", "SUPPLIES", "P001")}
    dot = graph_dot(graph, nodes, edge_ids=edges)
    assert 'label="FULFILLED_BY"' in dot
    assert 'label="SUPPLIES"' in dot
    # The actual graph has O001 -> P001, but this relationship was not retrieved.
    assert "CONTAINS" not in dot
    assert '"O001" -> "P001"' not in dot
    assert "CONTAINS" in graph_dot(graph, nodes)
