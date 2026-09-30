"""
Every statement this package sends to the store, so no other module opens a connection

An edge is read induced on one set of papers, since a bridge only counts when both ends are held
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from typing import Any

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

SEED = """
SELECT arxiv_id, title, abstract, date, embed_full::vector::real[]
FROM papers WHERE arxiv_id = %s AND stage >= 3
"""

RECORDS = """
SELECT p.arxiv_id, p.title, p.abstract, p.date, p.primary_category, p.authors,
       t.level_0, t.level_1, t.level_2, g.name, m.name, l.name
FROM papers p
LEFT JOIN topic_tree t ON t.arxiv_id = p.arxiv_id AND t.stage = 1
LEFT JOIN topic_names g ON g.level_0 = t.level_0 AND g.level_1 IS NULL
LEFT JOIN topic_names m ON m.level_0 = t.level_0 AND m.level_1 = t.level_1 AND m.level_2 IS NULL
LEFT JOIN topic_names l
  ON l.level_0 = t.level_0 AND l.level_1 = t.level_1 AND l.level_2 = t.level_2
WHERE p.arxiv_id = ANY(%s)
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


def read_seed(dsn: str, arxiv_id: str) -> tuple[Paper, list[float]] | None:
    """
    One paper and its stored vector, which is what a search seeded on that paper sends

    Args:
        dsn: libpq connection string.
        arxiv_id: The paper.

    Returns:
        The paper at a cosine of 1 and its vector, or None when the store holds no vector for it.
    """
    with psycopg.connect(dsn) as conn:
        row = conn.execute(SEED, (arxiv_id,)).fetchone()
    if row is None:
        return None
    a, t, abstract, when, vector = row
    paper = Paper(
        arxiv_id=str(a), title=str(t or ""), abstract=str(abstract or ""), date=when, cosine=1.0
    )
    return paper, [float(x) for x in vector]


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


def read_records(dsn: str, arxiv_ids: list[str]) -> dict[str, dict[str, Any]]:
    """
    The columns a reader sees but a ranking never needs, which is what the dashboard shows

    Args:
        dsn: libpq connection string.
        arxiv_ids: The papers.

    Returns:
        One record per paper the store holds, with its topic tree path from the top level down,
        empty for a paper the tree has not placed.
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
            "topic": [] if l0 is None else [str(g or ""), str(m or ""), str(f or "")],
            "topic_id": [] if l0 is None else [int(l0), int(l1), int(l2)],
        }
        for a, t, b, d, c, w, l0, l1, l2, g, m, f in rows
    }
