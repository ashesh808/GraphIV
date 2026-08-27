"""
Embed LitSearch's index universe exactly as their kv dict defines it

Their index is keyed by document text, so 64183 rows collapse to 57657 distinct keys
Retrieval can only ever return the corpusid their dict kept for each key
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

B = Path("/mnt/Vault-Storage/research/arxiv/benchmarks/litsearch")
PREFIX = "search_document: "
MAX_SEQ = 512
BATCH = 32
SKIPPED: list[int] = []


def _embed_split(batch: list[str], base: int = 0) -> list[list[float]]:
    """
    Halve on a 400, and give a document the server will never accept a zero vector
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
    Embed every distinct index key and save the matrix beside its corpusid list
    """
    c = cast(Any, pd).read_parquet(
        B / "corpus_clean", columns=["corpusid", "title", "abstract"]
    )  # pyright: ignore[reportExplicitAny]
    kv: dict[str, int] = {}
    for cid, t, a in zip(
        c["corpusid"], c["title"], c["abstract"], strict=True
    ):  # pyright: ignore[reportAny]
        kv[f"Title: {t}\nAbstract: {a}"] = int(cid)  # pyright: ignore[reportAny]
    texts, ids = list(kv), list(kv.values())
    print(f"{len(texts)} distinct index keys", flush=True)

    out = B / "exact_embeddings.npy"
    meta = B / "exact_meta.json"
    mat = np.zeros((len(texts), 768), dtype=np.float32)
    start = 0
    if meta.exists() and out.exists():
        st: dict[str, Any] = json.loads(meta.read_text())  # pyright: ignore[reportExplicitAny]
        if int(st.get("n_total", 0)) == len(texts):
            start, mat = int(st["done"]), np.load(out)
            print(f"resuming at {start}", flush=True)

    t0 = time.time()
    for i in range(start, len(texts), BATCH):
        b = texts[i : i + BATCH]
        mat[i : i + len(b)] = np.array(_embed_split(b, i), dtype=np.float32)
        if (i // BATCH) % 40 == 0 or i + BATCH >= len(texts):
            np.save(out, mat)
            _ = meta.write_text(json.dumps({"done": i + len(b), "n_total": len(texts)}))
            r = (i + len(b) - start) / max(1e-6, time.time() - t0)
            print(
                f"  {i + len(b)}/{len(texts)} {r:.0f}/s eta {(len(texts) - i) / max(r, 1e-6) / 60:.1f}m",
                flush=True,
            )

    np.save(out, mat)
    _ = (B / "exact_ids.json").write_text(json.dumps(ids))
    _ = meta.write_text(
        json.dumps(
            {
                "done": len(texts),
                "n_total": len(texts),
                "skipped": SKIPPED,
                "prefix": PREFIX,
                "max_seq": MAX_SEQ,
            }
        )
    )
    print(f"done in {(time.time() - t0) / 60:.1f}m, skipped {len(SKIPPED)}", flush=True)


if __name__ == "__main__":
    main()
