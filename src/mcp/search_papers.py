"""
Plain cosine against the corpus, which is how a title becomes an id

Nothing here scores the citation graph, so this is the escape hatch and never the main path
"""

from __future__ import annotations

import json
from datetime import date

from src.core.schema import Query
from src.mcp.state import Handles
from src.retrieve.cosine import CosineRetriever

MAX_LIMIT = 100


def search_papers(
    handles: Handles, text: str, limit: int = 20, before: str = "", after: str = ""
) -> str:
    """
    The papers nearest one piece of text, best first

    Args:
        handles: The shared handles.
        text: What to search for.
        limit: How many papers to return.
        before: The latest date a paper may carry, iso.
        after: The earliest date a paper may carry, iso.

    Returns:
        One json row per paper.
    """
    cap = date.fromisoformat(before) if before else None
    floor = date.fromisoformat(after) if after else None
    query = Query(text=text, emb=handles.embed(text), max_date=cap)
    found = CosineRetriever(handles.dsn).retrieve(query, max(1, min(MAX_LIMIT, limit)))
    return json.dumps(
        [
            {
                "arxiv_id": p.arxiv_id,
                "title": " ".join(p.title.split()),
                "date": p.date.isoformat(),
                "cosine": round(p.cosine or 0.0, 4),
                "url": f"https://arxiv.org/abs/{p.arxiv_id}",
            }
            for p in found
            if floor is None or p.date >= floor
        ],
        indent=2,
    )
