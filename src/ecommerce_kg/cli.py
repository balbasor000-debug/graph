"""Command-line interface for questions, demos, direct queries and graph exports."""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .examples import SAMPLE_QUERIES
from .graph import export_graph, graph_stats, load_graph
from .llm import BackendError, OfflineBackend, OpenAIBackend
from .query import QueryPlan
from .retrieval import GraphRetriever
from .service import RetrievalService


def _parser():
    parser = argparse.ArgumentParser(description="Evidence-grounded e-commerce knowledge graph")
    parser.add_argument("--dataset", type=Path, help="Override the bundled sample JSON dataset")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect", help="Show entity/relationship counts and keyword invariant")
    commands.add_parser("questions", help="List the offline demo questions")
    export = commands.add_parser("export", help="Export the graph as NetworkX node-link JSON")
    export.add_argument("destination", type=Path)
    ask = commands.add_parser("ask", help="Ask a natural-language question")
    ask.add_argument("question")
    ask.add_argument(
        "--json", action="store_true", help="Output answer, query and evidence as JSON"
    )
    ask.add_argument("--trace", action="store_true", help="Also print the query and raw evidence")
    demo = commands.add_parser("demo", help="Run all ten sample questions")
    demo.add_argument(
        "--output", type=Path, help="Also save questions, queries and evidence as JSON"
    )
    query = commands.add_parser("query", help="Execute a validated JSON query plan from a file")
    query.add_argument("file", type=Path)
    query.add_argument("--json", action="store_true")
    query.add_argument("--trace", action="store_true")
    for command in (ask, demo, query):
        command.add_argument("--mode", choices=("offline", "openai"), default="offline")
        command.add_argument(
            "--model", help="OpenAI model; defaults to OPENAI_MODEL or gpt-4o-mini"
        )
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv(Path.cwd() / ".env", override=False)
    try:
        if args.command == "questions":
            for index, question in enumerate(SAMPLE_QUERIES, 1):
                print(f"{index}. {question}")
            return 0
        graph = load_graph(args.dataset)
        if args.command == "inspect":
            print(json.dumps(graph_stats(graph), indent=2))
            return 0
        if args.command == "export":
            export_graph(graph, args.destination)
            print(f"Graph exported to {args.destination}")
            return 0
        backend = OpenAIBackend(graph, args.model) if args.mode == "openai" else OfflineBackend()
        service = RetrievalService(GraphRetriever(graph), backend)
        if args.command == "demo":
            answers = []
            for index, question in enumerate(SAMPLE_QUERIES, 1):
                answer = service.ask(question)
                answers.append(answer.to_dict())
                print(f"\n## {index}. {question}\nBackend: {answer.backend}\n\n{answer.markdown}")
            if args.output:
                args.output.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
                print(f"\nResults saved to {args.output}")
            return 0
        if args.command == "query":
            plan = QueryPlan.model_validate_json(args.file.read_text(encoding="utf-8"))
            answer = service.answer_query(plan)
        else:
            answer = service.ask(args.question)
        if args.json:
            print(json.dumps(answer.to_dict(), indent=2))
        else:
            print(f"Backend: {answer.backend}\n\n{answer.markdown}")
            if args.trace:
                print("\nGraph query:\n" + answer.query.model_dump_json(indent=2))
                print("\nRetrieved evidence:\n" + json.dumps(answer.retrieval.to_dict(), indent=2))
        return 0
    except (ValueError, OSError, BackendError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
