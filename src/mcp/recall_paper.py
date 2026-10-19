"""
A description of what a paper did, found or argued into the papers that match it

A model writes the abstract such a paper would have, and the corpus is searched with that guess
The description is searched too, since the guess drifts toward whatever reading dominates a field
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

import psycopg

from src.core import llm
from src.core.schema import Paper, Query
from src.mcp.state import Handles
from src.retrieve.cosine import CosineRetriever

LOG = logging.getLogger(__name__)

POOL = 100
READ = 30
PICKS = 8
MAX_LIMIT = 50
ABSTRACT_CHARS = 400
REPLY_CHARS = 700
DETAILS = "SELECT arxiv_id, abstract, authors FROM papers WHERE arxiv_id = ANY(%s)"

GUESS = """Someone is looking for papers they describe below. Write the abstract such a paper most
likely has, in the style of an arXiv abstract, about 120 words.

Return json only, no preamble:
{{"abstract": "..."}}

THEY WANT: {request}
"""

PICK = """Someone is looking for papers they describe below. Pick the candidates that match, most
likely first, at most {picks}, and none when nothing fits.

Return json only, no preamble:
{{"ids": [3, 1]}}

THEY WANT: {request}

{body}
"""


def nearest(handles: Handles, text: str, cap: date | None) -> list[Paper]:
    """
    The papers closest to one text, best first

    Args:
        handles: The shared handles.
        text: What to search with.
        cap: The latest date a paper may carry.

    Returns:
        The pool.
    """
    query = Query(text=text, emb=handles.embed(text), max_date=cap)
    return CosineRetriever(handles.dsn).retrieve(query, POOL)


def interleave(first: list[Paper], second: list[Paper]) -> list[Paper]:
    """
    Two rankings taken in turn, each paper at its earlier place

    Args:
        first: One ranking.
        second: The other.

    Returns:
        The merged ranking.
    """
    seen: dict[str, Paper] = {}
    for pair in zip(first, second, strict=False):
        for paper in pair:
            seen.setdefault(paper.arxiv_id, paper)
    for paper in first + second:
        seen.setdefault(paper.arxiv_id, paper)
    return list(seen.values())


def picks_first(picked: list[Paper], pool: list[Paper]) -> list[Paper]:
    """
    The reader's picks in its order, then the rest of the pool, each paper once

    Args:
        picked: What the reader matched.
        pool: The whole ranking.

    Returns:
        The reply's order.
    """
    return list({p.arxiv_id: p for p in picked + pool}.values())


def recall_paper(
    handles: Handles,
    description: str,
    author: str = "",
    before: str = "",
    after: str = "",
    limit: int = 10,
) -> str:
    """
    The papers that match a description, the reader's picks first

    Args:
        handles: The shared handles.
        description: What the papers did, found or argued, in the caller's words.
        author: A surname or name the papers must list, empty for any.
        before: The latest date a paper may carry, iso.
        after: The earliest date a paper may carry, iso.
        limit: How many papers to return.

    Returns:
        One json row per paper, with whether the reader picked it.
    """
    cap = date.fromisoformat(before) if before else None
    floor = date.fromisoformat(after) if after else None
    guessed = llm.parse_json(handles.model.ask(GUESS.format(request=description), max_tokens=400))
    text = str((guessed or {}).get("abstract") or description)
    pool = interleave(nearest(handles, text, cap), nearest(handles, description, cap))
    pool = [p for p in pool if floor is None or p.date >= floor]
    with psycopg.connect(handles.dsn) as conn:
        meta = {
            str(a): (" ".join(str(ab or "").split()), str(au or ""))
            for a, ab, au in conn.execute(DETAILS, ([p.arxiv_id for p in pool],)).fetchall()
        }
    if author:
        pool = [p for p in pool if author.lower() in meta.get(p.arxiv_id, ("", ""))[1].lower()]
    head = pool[:READ]
    body = "\n\n".join(
        f"[{i + 1}] {' '.join(p.title.split())} ({p.date.year})\n"
        f"{meta.get(p.arxiv_id, ('', ''))[0][:ABSTRACT_CHARS]}"
        for i, p in enumerate(head)
    )
    reply = handles.model.ask(
        PICK.format(request=description, body=body, picks=PICKS), max_tokens=120
    )
    raw = (llm.parse_json(reply) or {}).get("ids", [])
    picked = (
        [head[i - 1] for i in raw if isinstance(i, int) and 1 <= i <= len(head)]
        if isinstance(raw, list)
        else []
    )
    chosen = {p.arxiv_id for p in picked}
    ranked = picks_first(picked, pool)
    LOG.info("recalled %d of %d for %r", len(chosen), len(pool), description[:60])
    out: list[dict[str, Any]] = [
        {
            "arxiv_id": p.arxiv_id,
            "title": " ".join(p.title.split()),
            "date": p.date.isoformat(),
            "matched": p.arxiv_id in chosen,
            "abstract": meta.get(p.arxiv_id, ("", ""))[0][:REPLY_CHARS],
            "url": f"https://arxiv.org/abs/{p.arxiv_id}",
        }
        for p in ranked[: max(1, min(MAX_LIMIT, limit))]
    ]
    return json.dumps(out, indent=2)
