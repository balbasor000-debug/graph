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


def test_cli_accepts_groq_and_reports_missing_key_without_a_network_call(monkeypatch, capsys):
    # An explicit empty variable prevents the local .env from supplying a real test key.
    monkeypatch.setenv("GROQ_API_KEY", "")
    assert main(["ask", "List the products", "--mode", "groq"]) == 1
    assert "GROQ_API_KEY" in capsys.readouterr().err


def test_streamlit_groq_selection_uses_the_selected_backend(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    from ecommerce_kg.llm import OfflineBackend

    calls = []

    class MockGroqBackend(OfflineBackend):
        name = "groq"

    def factory(mode, graph, model=None):
        calls.append(mode)
        return MockGroqBackend()

    monkeypatch.setattr("ecommerce_kg.llm.create_backend", factory)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=30).run()
    app.radio[0].set_value("Groq live").run()
    app.selectbox[0].select("How many products contain the keyword banana?").run()
    app.button[0].click().run()
    assert not app.exception and not app.error
    assert calls == ["groq"]
    assert app.session_state["answer"].backend == "groq"
    assert app.session_state["answer"].retrieval.rows[0].values == {"count(p)": 5}


def test_demo_pacing_waits_between_questions_only(monkeypatch, tmp_path, capsys):
    waits = []
    monkeypatch.setattr("ecommerce_kg.cli.time.sleep", waits.append)
    destination = tmp_path / "paced_results.json"
    assert main(["demo", "--delay-seconds", "2", "--output", str(destination)]) == 0
    assert waits == [2.0] * 9
    assert len(json.loads(destination.read_text())) == 10
    capsys.readouterr()


@pytest.mark.parametrize("delay", ["-1", "nan"])
def test_invalid_demo_pacing_is_rejected(delay, capsys):
    assert main(["demo", "--delay-seconds", delay]) == 1
    assert "--delay-seconds must be" in capsys.readouterr().err
