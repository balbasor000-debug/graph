"""Question -> query -> graph evidence -> LLM presentation -> verified answer."""

from dataclasses import dataclass

from .llm import Backend
from .query import AnswerPlan, QueryPlan
from .retrieval import GraphRetriever, RetrievalResult


class GroundingError(ValueError):
    pass


def _escape(value) -> str:
    # Render data literally in Markdown rather than treating data as links/instructions.
    text = str(value)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for char in ("\\", "`", "*", "_", "[", "]", "|", "#"):
        text = text.replace(char, f"\\{char}")
    return text.replace("\n", " ").replace("\r", " ")


def _is_money(column):
    return column.endswith("_cents") or (
        column.startswith("sum(") and column.endswith("_cents)")
    )


def _display_column(column):
    if _is_money(column):
        prefix, suffix = column.rsplit("_cents", 1)
        column = f"{prefix}{suffix} (USD)"
    return _escape(column)


def _display_value(column, value):
    if value is None:
        return "not stored"
    if _is_money(column) and isinstance(value, int):
        return f"USD {value // 100:,}.{value % 100:02d}"
    return _escape(value)


def render_answer(result: RetrievalResult, presentation: AnswerPlan) -> str:
    expected = [row.evidence_id for row in result.rows]
    if presentation.evidence_ids != expected:
        raise GroundingError("Answer rejected: LLM evidence IDs do not match retrieved rows")
    if not result.rows:
        return "No matching data was found in the graph."
    columns = list(result.rows[0].values)
    if presentation.style == "table":
        lines = [
            "| " + " | ".join([*map(_display_column, columns), "Evidence"]) + " |",
            "| " + " | ".join("---" for _ in range(len(columns) + 1)) + " |",
        ]
        for row in result.rows:
            cells = [_display_value(column, row.values[column]) for column in columns]
            lines.append("| " + " | ".join([*cells, f"[{row.evidence_id}]"]) + " |")
    else:
        lines = [
            "- " + "; ".join(
                f"{_display_column(column)}: {_display_value(column, value)}"
                for column, value in row.values.items()
            ) + f" [{row.evidence_id}]"
            for row in result.rows
        ]
    if result.truncated:
        lines.append(f"\nShowing {len(result.rows)} of {result.total_rows} matching rows.")
    lines.append("\n**Evidence sources** (graph node IDs):")
    for row in result.rows:
        nodes = ", ".join(map(_escape, row.node_ids)) or (
            "no matching nodes (aggregate over empty set)"
        )
        lines.append(f"- [{row.evidence_id}]: {nodes}")
    return "\n".join(lines)


@dataclass
class Answer:
    question: str
    backend: str
    query: QueryPlan
    retrieval: RetrievalResult
    markdown: str

    def to_dict(self):
        return {
            "question": self.question,
            "backend": self.backend,
            "query": self.query.model_dump(),
            "retrieval": self.retrieval.to_dict(),
            "answer": self.markdown,
        }


class RetrievalService:
    def __init__(self, retriever: GraphRetriever, backend: Backend):
        self.retriever = retriever
        self.backend = backend

    def ask(self, question: str) -> Answer:
        question = question.strip()
        if not question or len(question) > 2000:
            raise ValueError("Question must contain 1..2000 characters")
        query = self.backend.plan_query(question)
        return self.answer_query(query, question)

    def answer_query(self, query: QueryPlan, question: str = "Direct graph query") -> Answer:
        query = QueryPlan.model_validate(query.model_dump())
        result = self.retriever.execute(query)
        # Empty evidence bypasses the LLM and returns a fixed no-match response.
        presentation = self.backend.plan_answer(question, result) if result.rows else AnswerPlan(
            evidence_ids=[], style="table"
        )
        return Answer(
            question, self.backend.name, query, result, render_answer(result, presentation)
        )
