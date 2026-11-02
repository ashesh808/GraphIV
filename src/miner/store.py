"""
The corpus reads mining needs, converted to the paper and citation objects it consumes

An edge is read induced on one set of papers, since a bridge only counts when both ends are held
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date
from typing import Any, cast

from src.core.schema import Edge, Paper
from src.storage.corpus import CorpusSource, open_corpus

LOG = logging.getLogger(__name__)


def as_vector(values: list[float]) -> str:
    """
    One embedding as the literal pgvector parses

    Args:
        values: The embedding.

    Returns:
        The literal.
    """
    return "[" + ",".join(f"{x:.6f}" for x in values) + "]"


def read_edges(dsn: CorpusSource, arxiv_ids: list[str]) -> list[Edge]:
    """
    Every labeled citation with both ends inside a named set

    Args:
        dsn: A libpq connection string or corpus adapter.
        arxiv_ids: The papers the subgraph is induced on.

    Returns:
        One entry per citation occurrence.
    """
    if not arxiv_ids:
        return []
    corpus = open_corpus(dsn)
    scored = getattr(corpus, "edge_records", None)
    if callable(scored):
        records = cast(
            list[tuple[str, str, str | None, str | None, float | None]], scored(arxiv_ids)
        )
        return [
            Edge(
                source=str(source),
                target=str(target),
                intent=str(intent or "background"),
                sentence=str(sentence or ""),
                intent_score=float(score) if score is not None else None,
            )
            for source, target, intent, sentence, score in records
        ]
    rows = corpus.edges(arxiv_ids)
    return [
        Edge(source=str(s), target=str(t), intent=str(i or "background"), sentence=str(sent or ""))
        for s, t, i, sent in rows
    ]


def read_cosines(dsn: CorpusSource, vector: list[float], arxiv_ids: list[str]) -> dict[str, float]:
    """
    Cosine of every named paper against one vector, in one round trip

    Args:
        dsn: A libpq connection string or corpus adapter.
        vector: What to measure against.
        arxiv_ids: The papers.

    Returns:
        One cosine per paper the store holds.
    """
    if not arxiv_ids:
        return {}
    rows = open_corpus(dsn).cosines(vector, arxiv_ids)
    return {str(a): float(c) for a, c in rows}


def read_papers(dsn: CorpusSource, vector: list[float], arxiv_ids: list[str]) -> list[Paper]:
    """
    Every column a Paper needs for a list of ids

    Args:
        dsn: A libpq connection string or corpus adapter.
        vector: The question embedding, which fills the cosine.
        arxiv_ids: The papers.

    Returns:
        One Paper per id the store holds.
    """
    if not arxiv_ids:
        return []
    rows = open_corpus(dsn).papers(vector, arxiv_ids)
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


def read_seed(dsn: CorpusSource, arxiv_id: str) -> tuple[Paper, list[float]] | None:
    """
    One paper and its stored vector, which is what a search seeded on that paper sends

    Args:
        dsn: A libpq connection string or corpus adapter.
        arxiv_id: The paper.

    Returns:
        The paper at a cosine of 1 and its vector, or None when the store holds no vector for it.
    """
    row = open_corpus(dsn).seed(arxiv_id)
    if row is None:
        return None
    a, t, abstract, when, vector = row
    paper = Paper(
        arxiv_id=str(a), title=str(t or ""), abstract=str(abstract or ""), date=when, cosine=1.0
    )
    return paper, [float(x) for x in vector]


def read_vectors(dsn: CorpusSource, arxiv_ids: list[str]) -> dict[str, list[float]]:
    """
    The stored vectors of several papers

    Args:
        dsn: A libpq connection string or corpus adapter.
        arxiv_ids: The papers.

    Returns:
        Each embedded paper's vector, keyed by its id.
    """
    rows = open_corpus(dsn).vectors(arxiv_ids)
    return {str(a): [float(x) for x in vector] for a, vector in rows}


def mean_vector(vectors: list[list[float]]) -> list[float]:
    """
    The unit mean of some vectors, which is what a search from a list of papers starts at

    Args:
        vectors: The vectors.

    Returns:
        Their normalized mean, empty when there are none.
    """
    if not vectors:
        return []
    mean = [sum(column) / len(vectors) for column in zip(*vectors, strict=True)]
    size = math.sqrt(sum(x * x for x in mean)) or 1.0
    return [x / size for x in mean]


def read_successors(
    dsn: CorpusSource,
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
        dsn: A libpq connection string or corpus adapter.
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
    rows = open_corpus(dsn).successors(vector, arxiv_ids, since, until, intents, floor)

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


def read_records(dsn: CorpusSource, arxiv_ids: list[str]) -> dict[str, dict[str, Any]]:
    """
    The columns a reader sees but a ranking never needs, which is what the dashboard shows

    Args:
        dsn: A libpq connection string or corpus adapter.
        arxiv_ids: The papers.

    Returns:
        One record per paper the store holds, with its topic tree path from the top level down,
        empty for a paper the tree has not placed.
    """
    if not arxiv_ids:
        return {}
    rows = open_corpus(dsn).records(arxiv_ids)
    return {
        str(a): {
            "title": " ".join(str(t or "").split()),
            "abstract": " ".join(str(b or "").split()),
            "date": str(d),
            "category": str(c or ""),
            "authors": " ".join(str(w or "").split()),
            "topic": [] if l0 is None else [str(g or ""), str(m or ""), str(f or "")],
            "topic_id": [] if l0 is None else [int(l0), int(cast(int, l1)), int(cast(int, l2))],
        }
        for a, t, b, d, c, w, l0, l1, l2, g, m, f in rows
    }
