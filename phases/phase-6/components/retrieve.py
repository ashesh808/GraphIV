"""Query embedding for phase-6 retrieval.

Loads the nomic model, encodes a query into the document embedding space, and frees the model so
VRAM can be handed back to the LLM. The query MUST use the same nomic model + prompt prefix the
documents were encoded with (see `_common.NOMIC_PROMPT`). Documents were encoded as
"Title: {t}\nAbstract: {a}"; `pipeline.hyde_query` shapes the query into that form (HyDE) before
calling `embed_query`, so a bare topic phrase doesn't drift to lexical look-alikes.

(Graph/vector fetches now live in `store.py` over Postgres+pgvector; this module is only the
embedding model bridge.)
"""

from __future__ import annotations

from typing import Any

from _common import NOMIC_MAX_SEQ, NOMIC_MODEL, NOMIC_PROMPT  # noqa: E402

_MODEL: Any = None


def _get_model() -> Any:
    """Lazy-load the nomic SentenceTransformer onto CUDA (cached)."""
    global _MODEL
    if _MODEL is None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[retrieve] loading nomic on {device} ...", flush=True)
        _MODEL = SentenceTransformer(
            str(NOMIC_MODEL), trust_remote_code=True, device=device
        )
        _MODEL.max_seq_length = NOMIC_MAX_SEQ
    return _MODEL


def free_model() -> None:
    """Release the embedding model + CUDA cache (to hand VRAM back to Gemma)."""
    global _MODEL
    if _MODEL is not None:
        import torch

        del _MODEL
        _MODEL = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def embed_query(text: str) -> list[float]:
    """Encode a query into the document embedding space (normalized, 768D)."""
    vec = _get_model().encode(
        [text],
        prompt=NOMIC_PROMPT,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]
    return [float(x) for x in vec]
