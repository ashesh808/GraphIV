"""
Query embedding against the llama-embed endpoint, which owns the model

A query must carry the same prompt prefix its documents were encoded with, or recall collapses
The sym space pairs with a HyDE-shaped query, the asym space with the raw question
"""

from __future__ import annotations

import json
import math
import urllib.request
from typing import Any

from graphiv.core.settings import EMBED_API, EMBED_MODEL_NAME, NOMIC_PROMPT

ASYM_QUERY_PROMPT = "search_query: "


def embed_texts(texts: list[str], timeout: float = 120.0) -> list[list[float]]:
    """
    POST prefixed texts to the endpoint's /v1/embeddings; returns L2-normalized vectors
    """
    req = urllib.request.Request(
        f"{EMBED_API}/v1/embeddings",
        data=json.dumps({"model": EMBED_MODEL_NAME, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload: dict[str, Any] = json.load(r)  # pyright: ignore[reportExplicitAny]
    rows: list[dict[str, Any]] = sorted(  # pyright: ignore[reportExplicitAny]
        payload["data"], key=lambda d: int(d["index"])  # pyright: ignore[reportAny]
    )
    out: list[list[float]] = []
    for row in rows:
        vec = [float(x) for x in row["embedding"]]  # pyright: ignore[reportAny]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        out.append([x / norm for x in vec])
    return out


def free_model() -> None:
    """
    No-op kept for archived experiment code: embedding now lives in the llama-embed server
    """


def embed_query(text: str, mode: str = "sym") -> list[float]:
    """
    Encode a query into a 768D embedding space (normalized)

        `mode="sym"` uses the symmetric Instruct prompt the corpus was encoded with, pair it with a
        HyDE-shaped `text` (the production default). `mode="asym"` uses nomic's native asymmetric
        `search_query:` prompt; pair it with the raw question and the `embedding_asym` column, no
        HyDE needed.
    """
    prefix = ASYM_QUERY_PROMPT if mode == "asym" else NOMIC_PROMPT
    return embed_texts([prefix + text])[0]
