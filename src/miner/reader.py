"""
A role and a relevance for every paper, which is the only model call this package makes

Fusing the grade with the score is what keeps a heavily cited but unrelated hub out of an answer
A paper graded out leaves the answer and stays in the graph, since a bridge need not be relevant
"""

from __future__ import annotations

import logging

from src.core import llm
from src.core.schema import Grade, Paper

LOG = logging.getLogger(__name__)

LABELS = ("foundational", "core", "frontier", "adjacent", "survey", "unrelated")
ABSTRACT_CHARS = 900
BATCH = 16
REPLY_TOKENS = 40

PROMPT = """You grade research papers for a focused literature review answering a QUESTION.

QUESTION: {question}

Assign each paper exactly one role:
- foundational: seminal or origin work the question's methods are built upon.
- core: a central, widely built-on method or result in the question's main line.
- frontier: recent work pushing the leading edge, new capabilities or open directions.
- adjacent: genuinely related but tangential, an adjacent-domain application.
- survey: a survey, benchmark or tooling paper overviewing the area.
- unrelated: off-topic for THIS question, a retrieval error that does not belong.

Also grade relevance -2 to 2: 2 = must cover, 1 = should cover, 0 = borderline, -1 = probably
out, -2 = certainly out. A paper you call unrelated MUST get -2. Judge by content against the
question, never by fame. Use the year only as a recency hint.

Reply with json only, no preamble:
{{"papers": [{{"id": 1, "role": "core", "relevance": 2}}]}}

{body}
"""


def grade(model: llm.Gemma, question: str, papers: list[Paper]) -> dict[str, Grade]:
    """
    One verdict per paper, read off title, date and abstract

    Args:
        model: The router client.
        question: What the reader grades against.
        papers: The papers to read.

    Returns:
        One verdict per paper the model returned, keyed by arXiv id.
    """
    if not papers:
        return {}
    batches = [papers[i : i + BATCH] for i in range(0, len(papers), BATCH)]
    prompts = [
        PROMPT.format(
            question=question,
            body="\n\n".join(
                f"{i}. ({p.date.year}) {p.title}\n{p.abstract[:ABSTRACT_CHARS]}"
                for i, p in enumerate(batch, 1)
            ),
        )
        for batch in batches
    ]
    replies = model.ask_many(prompts, max_tokens=REPLY_TOKENS * BATCH)
    out: dict[str, Grade] = {}
    for batch, reply in zip(batches, replies, strict=True):
        out |= read_reply(reply, batch)
    LOG.info("graded %d of %d papers", len(out), len(papers))
    return out


def read_reply(reply: str, batch: list[Paper]) -> dict[str, Grade]:
    """
    The verdicts one reply carries, dropping anything that does not name a label

    Args:
        reply: What the model returned.
        batch: The papers it was shown, in the order they were numbered.

    Returns:
        One verdict per entry that parsed.
    """
    parsed = llm.parse_json(reply)
    entries = parsed.get("papers") if isinstance(parsed, dict) else None
    if not isinstance(entries, list):
        return {}
    out: dict[str, Grade] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        spot = int(entry.get("id", 0)) - 1
        role = str(entry.get("role", "")).strip().lower()
        if not (0 <= spot < len(batch)) or role not in LABELS:
            continue
        relevance = -2 if role == "unrelated" else int(entry.get("relevance", 0))
        out[batch[spot].arxiv_id] = Grade(role=role, relevance=relevance)
    return out


def keep(papers: list[Paper], grades: dict[str, Grade], drop: bool = True) -> list[Paper]:
    """
    Folds the verdict into the score, dropping what the reader called unrelated

    A paper the reader never saw keeps its score, so grading a slice can only reorder that slice
    and can never promote something from below it.

    Args:
        papers: The ranking the graph produced.
        grades: What the reader said.
        drop: Remove anything graded out rather than only demoting it.

    Returns:
        The reordered ranking.
    """
    out: list[Paper] = []
    for paper in papers:
        held = grades.get(paper.arxiv_id)
        if held is None:
            out.append(paper)
            continue
        if drop and held.relevance <= -2:
            continue
        out.append(paper.model_copy(update={"score": (paper.score or 0.0) * held.factor}))
    return sorted(out, key=lambda p: -(p.score or 0.0))
