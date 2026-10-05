import json
from pathlib import Path

import pytest

from ecommerce_kg.cli import main


def test_cli_inspect_ask_demo_and_export(tmp_path, capsys):
    assert main(["inspect"]) == 0
    assert json.loads(capsys.readouterr().out)["banana_occurrences"] == 5
    assert main(["ask", "How many products contain the keyword banana?", "--json"]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["retrieval"]["rows"][0]["values"] == {"count(p)": 5}
    results = tmp_path / "results.json"
    assert main(["demo", "--output", str(results)]) == 0
    assert len(json.loads(results.read_text())) == 10
    capsys.readouterr()
    exported = tmp_path / "graph.json"
    assert main(["export", str(exported)]) == 0
    assert len(json.loads(exported.read_text())["nodes"]) == 34
    assert main(["ask", "Unsupported offline question"]) == 1
    assert "Offline mode supports" in capsys.readouterr().err


def test_streamlit_demo_has_graph_counts_and_retrieves_five_products():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert [metric.value for metric in app.metric] == ["34", "67", "5"]
    app.selectbox[0].select("Which products contain the keyword banana?").run()
    app.button[0].click().run()
    assert not app.exception
    text = "\n".join(element.value for element in app.markdown)
    assert "Organic Fruit Bunch" in text and "Fruit Bread" in text
    assert all(f"[R{index}]" in text for index in range(1, 6))
    app.selectbox[1].select("Last answer evidence").run()
    assert not app.exception
