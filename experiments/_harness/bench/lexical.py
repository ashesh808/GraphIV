"""
An OR-based lexical retriever, since the shipped plainto_tsquery arm matches nothing

plainto_tsquery ANDs every term, so a 20-word question never matches a title
This is also the BM25-style flat baseline the LitSearch protocol compares against
"""

from __future__ import annotations

import re
from typing import Any

from graphiv.core.models import PoolNode
from graphiv.core.store import Store

STOP = {
    "what",
    "which",
    "how",
    "are",
    "the",
    "and",
    "for",
    "with",
    "used",
    "does",
    "their",
    "them",
    "that",
    "this",
    "these",
    "those",
    "from",
    "into",
    "across",
    "various",
    "different",
    "recent",
    "can",
    "its",
    "his",
    "her",
    "they",
    "have",
    "has",
    "been",
    "was",
    "were",
    "using",
    "based",
    "between",
    "among",
    "over",
    "under",
    "about",
    "when",
    "where",
    "why",
    "who",
    "whom",
    "than",
    "such",
    "some",
    "any",
    "all",
    "both",
    "each",
    "more",
    "most",
    "other",
    "there",
    "here",
}


def terms(query: str) -> list[str]:
    """
    Content words of a question, lowercased, stopwords and short tokens dropped
    """
    ws = re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", query.lower().replace("-", " "))
    return [w for w in dict.fromkeys(ws) if w not in STOP][:16]


def lexical_or(store: Store, query: str, k: int) -> list[PoolNode]:
    """
    Top-`k` titles by ts_rank against the OR of the query's content words
    """
    ts = terms(query)
    if not ts:
        return []
    tsq = " | ".join(ts)
    rows: list[tuple[Any, ...]] = store.conn.execute(  # pyright: ignore[reportExplicitAny]
        "SELECT m.arxiv_id, m.title, m.year, m.primary_category, "
        "ts_rank(to_tsvector('english', coalesce(m.title, '')), q) AS r "
        "FROM paper_meta m, to_tsquery('english', %s) q "
        "WHERE to_tsvector('english', coalesce(m.title, '')) @@ q "
        "ORDER BY r DESC LIMIT %s",
        (tsq, k),
    ).fetchall()
    return [
        PoolNode(str(r[0]), str(r[1] or ""), r[2], r[3], float(r[4]))
        for r in rows
        if store.admits(str(r[0]))
    ]
