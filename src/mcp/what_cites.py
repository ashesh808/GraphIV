"""
Who took a position on one paper, and the sentence they used to take it

This is the labeled half of the citation graph, which nothing outside this corpus offers
"""

from __future__ import annotations

import json

from src.mcp.state import Handles
from src.storage.corpus import open_corpus

STANCE = ("extends", "critiques", "compares")
MIN_SCORE = 0.60
SENTENCE_CHARS = 300
MAX_LIMIT = 100


def what_cites(
    handles: Handles,
    arxiv_id: str,
    intents: list[str] | None = None,
    since: str = "",
    limit: int = 20,
) -> str:
    """
    Every paper that cited one paper with a position, newest first

    Args:
        handles: The shared handles.
        arxiv_id: The paper being cited.
        intents: Which labels to return, defaulting to the three that state a position.
        since: The earliest date a citer may carry, iso, no floor when empty.
        limit: How many citers to return.

    Returns:
        One json row per citer.
    """
    wanted = [i for i in (intents or []) if i] or list(STANCE)
    floor = since or None
    rows = open_corpus(handles.dsn).citing_papers(
        arxiv_id, wanted, MIN_SCORE, floor, max(1, min(MAX_LIMIT, limit))
    )
    return json.dumps(
        [
            {
                "arxiv_id": str(a),
                "title": " ".join(str(t or "").split()),
                "date": str(when),
                "intent": str(intent),
                "sentence": str(sentence or "")[:SENTENCE_CHARS],
                "url": f"https://arxiv.org/abs/{a}",
            }
            for a, intent, sentence, when, t in rows
        ],
        indent=2,
    )
