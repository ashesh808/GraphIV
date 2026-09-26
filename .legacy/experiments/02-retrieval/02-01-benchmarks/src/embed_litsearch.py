"""
Embed the LitSearch corpus into our production asymmetric space

It reuses embed_corpus.embed_endpoint unchanged, so nothing about the encoding differs
The prefix, the truncation and the normalization all match our own index
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError

import numpy as np
import pandas as pd  # pyright: ignore[reportMissingTypeStubs]

from graphiv.preprocess.embed_corpus import embed_endpoint

BASE = Path("/mnt/Vault-Storage/research/arxiv/benchmarks/litsearch")
PREFIX = "search_document: "
MAX_SEQ = 512
BATCH = 32
CKPT = 40


SKIPPED: list[int] = []


def _embed_split(batch: list[str], base: int = 0) -> list[list[float]]:
    """
    Embed a batch, halving it on a 400, which is either an oversized token total or

        a document of PDF-extraction garbage that the server will not accept at any size.
        A rejected single document gets a zero vector, so it is simply never retrieved.
    """
    try:
        return embed_endpoint(batch, PREFIX, MAX_SEQ)
    except HTTPError:
        if len(batch) == 1:
            SKIPPED.append(base)
            return [[0.0] * 768]
        h = len(batch) // 2
        return _embed_split(batch[:h], base) + _embed_split(batch[h:], base + h)


def main() -> None:
    """
    Embed every document with an abstract, checkpointing so the run resumes
    """
    df = cast(Any, pd).read_parquet(BASE / "corpus.parquet")  # pyright: ignore[reportExplicitAny]
    df = df[df["abstract"].str.len() > 0].reset_index(drop=True)  # pyright: ignore[reportAny]
    ids = [int(x) for x in df["corpusid"].tolist()]  # pyright: ignore[reportAny]
    docs = [
        f"Title: {t or ''}\nAbstract: {a or ''}"
        for t, a in zip(
            df["title"].tolist(), df["abstract"].tolist(), strict=True
        )  # pyright: ignore[reportAny]
    ]
    print(f"{len(docs)} documents to embed", flush=True)

    out = BASE / "embeddings_asym.npy"
    meta = BASE / "embeddings_meta.json"
    start = 0
    mat = np.zeros((len(docs), 768), dtype=np.float32)
    if meta.exists() and out.exists():
        state: dict[str, Any] = json.loads(meta.read_text())  # pyright: ignore[reportExplicitAny]
        if int(state.get("n_total", 0)) == len(docs):
            start = int(state["done"])
            mat = np.load(out)
            print(f"resuming at {start}", flush=True)

    t0 = time.time()
    for i in range(start, len(docs), BATCH):
        batch = docs[i : i + BATCH]
        mat[i : i + len(batch)] = np.array(_embed_split(batch, i), dtype=np.float32)
        if (i // BATCH) % CKPT == 0 or i + BATCH >= len(docs):
            np.save(out, mat)
            _ = meta.write_text(json.dumps({"done": i + len(batch), "n_total": len(docs)}))
            rate = (i + len(batch) - start) / max(1e-6, time.time() - t0)
            eta = (len(docs) - i - len(batch)) / max(1e-6, rate)
            print(f"  {i + len(batch)}/{len(docs)}  {rate:.0f}/s  eta {eta / 60:.1f}m", flush=True)

    np.save(out, mat)
    _ = (BASE / "embedding_ids.json").write_text(json.dumps(ids))
    _ = meta.write_text(
        json.dumps(
            {
                "done": len(docs),
                "n_total": len(docs),
                "prefix": PREFIX,
                "max_seq": MAX_SEQ,
                "model": "nomic-embed-text-v2-moe",
                "space": "asym",
            }
        )
    )
    _ = (BASE / "embedding_skipped.json").write_text(json.dumps(SKIPPED))
    print(f"done {len(docs)} in {(time.time() - t0) / 60:.1f}m -> {out}", flush=True)
    print(f"skipped {len(SKIPPED)} unembeddable documents", flush=True)


if __name__ == "__main__":
    main()
