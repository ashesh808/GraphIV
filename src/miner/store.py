"""
Every statement this package sends to the store, so no other module opens a connection

An edge is read induced on one set of papers, since a bridge only counts when both ends are held
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

import psycopg

from src.core.schema import Edge, Paper

LOG = logging.getLogger(__name__)

EDGES = """
SELECT source_id, target_id, intent, sentence
FROM citations
WHERE stage = 1 AND source_id = ANY(%s) AND target_id = ANY(%s) AND target_id IS NOT NULL
"""

COSINES = """
SELECT arxiv_id, 1 - (embed_full <=> %s::halfvec)
FROM papers WHERE arxiv_id = ANY(%s) AND stage >= 3
"""

SUCCESSORS = """
SELECT c.source_id, c.target_id, c.intent, c.sentence, p.date, p.title, p.abstract,
       1 - (p.embed_full <=> %s::halfvec)
FROM citations c JOIN papers p ON p.arxiv_id = c.source_id
WHERE c.stage = 1 AND c.target_id = ANY(%s) AND c.intent = ANY(%s)
  AND c.intent_score >= %s AND p.date > %s AND p.date <= %s AND p.stage >= 3
"""

PAPERS = """
SELECT arxiv_id, title, abstract, date, 1 - (embed_full <=> %s::halfvec)
FROM papers WHERE arxiv_id = ANY(%s) AND stage >= 3
"""

RECORDS = """
SELECT arxiv_id, title, abstract, date, primary_category, authors
FROM papers WHERE arxiv_id = ANY(%s)
"""


def as_vector(values: list[float]) -> str:
    """
    One embedding as the literal pgvector parses

    Args:
        values: The embedding.

    Returns:
        The literal.
    """
    return "[" + ",".join(f"{x:.6f}" for x in values) + "]"


def read_edges(dsn: str, arxiv_ids: list[str]) -> list[Edge]:
    """
    Every labeled citation with both ends inside a named set

    Args:
        dsn: libpq connection string.
        arxiv_ids: The papers the subgraph is induced on.

    Returns:
        One entry per citation occurrence.
    """
    if not arxiv_ids:
        return []
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(EDGES, (arxiv_ids, arxiv_ids)).fetchall()
    return [
        Edge(source=str(s), target=str(t), intent=str(i or "background"), sentence=str(sent or ""))
        for s, t, i, sent in rows
    ]


def read_cosines(dsn: str, vector: list[float], arxiv_ids: list[str]) -> dict[str, float]:
    """
    Cosine of every named paper against one vector, in one round trip

    Args:
        dsn: libpq connection string.
        vector: What to measure against.
        arxiv_ids: The papers.

    Returns:
        One cosine per paper the store holds.
    """
    if not arxiv_ids:
        return {}
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(COSINES, (as_vector(vector), arxiv_ids)).fetchall()
    return {str(a): float(c) for a, c in rows}


def read_papers(dsn: str, vector: list[float], arxiv_ids: list[str]) -> list[Paper]:
    """
    Every column a Paper needs for a list of ids

    Args:
        dsn: libpq connection string.
        vector: The question embedding, which fills the cosine.
        arxiv_ids: The papers.

    Returns:
        One Paper per id the store holds.
    """
    if not arxiv_ids:
        return []
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(PAPERS, (as_vector(vector), arxiv_ids)).fetchall()
    return [
        Paper(
            arxiv_id=str(a),
            title=str(t or ""),
            abstract=str(abstract or ""),
            date=when,
            cosine=float(cosine),
        )
        for a, t, abstract, when, cosine in rows
    ]


def read_successors(
    dsn: str,
    vector: list[float],
    arxiv_ids: list[str],
    since: date,
    until: date,
    intents: tuple[str, ...],
    floor: float,
) -> dict[str, tuple[Paper, dict[str, str], list[str]]]:
    """
    Papers from a window that take a position on a named set, with what they said

    A paper declares itself here by citing the set, so nothing too recent to have been cited of
    its own is missed.

    Args:
        dsn: libpq connection string.
        vector: The question embedding, which holds a successor to what was asked.
        arxiv_ids: The set being cited.
        since: The earliest a successor may be dated.
        until: The date the whole run is capped at.
        intents: Which labels count as taking a position.
        floor: The lowest classifier score an edge may carry.

    Returns:
        Per citing paper, the paper, which of the set it reached with which intent, and sentences.
    """
    if not arxiv_ids:
        return {}
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            SUCCESSORS,
            (as_vector(vector), arxiv_ids, list(intents), floor, since, until),
        ).fetchall()

    targets: dict[str, dict[str, str]] = defaultdict(dict)
    sentences: dict[str, list[str]] = defaultdict(list)
    papers: dict[str, Paper] = {}
    for source, target, intent, sentence, when, title, abstract, cosine in rows:
        key = str(source)
        targets[key][str(target)] = str(intent)
        if sentence:
            sentences[key].append(str(sentence))
        papers[key] = Paper(
            arxiv_id=key,
            title=str(title or ""),
            abstract=str(abstract or ""),
            date=when,
            cosine=float(cosine),
        )
    return {key: (papers[key], held, sentences[key]) for key, held in targets.items()}


def read_records(dsn: str, arxiv_ids: list[str]) -> dict[str, dict[str, str]]:
    """
    The columns a reader sees but a ranking never needs, which is what the dashboard shows

    Args:
        dsn: libpq connection string.
        arxiv_ids: The papers.

    Returns:
        One record per paper the store holds.
    """
    if not arxiv_ids:
        return {}
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(RECORDS, (arxiv_ids,)).fetchall()
    return {
        str(a): {
            "title": " ".join(str(t or "").split()),
            "abstract": " ".join(str(b or "").split()),
            "date": str(d),
            "category": str(c or ""),
            "authors": " ".join(str(w or "").split()),
        }
        for a, t, b, d, c, w in rows
    }
