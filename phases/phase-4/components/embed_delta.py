"""Embed corpus papers that lack a vector (the post-.npy delta, e.g. 2026) -> paper_embedding.

The migration imported the frozen nomic .npy (2.92M, pre-2026); newer papers (all of 2026 + a few
2025) have metadata but no embedding, so phase-6 `frontier_pull` can't surface them (its vector
search only sees `paper_embedding`). This embeds those papers with the SAME nomic model + prompt +
"Title: ..\nAbstract: .." doc format the corpus used, and inserts into `paper_embedding` (the HNSW
index picks up new rows automatically). Resumable: only embeds papers still missing a vector.

Embedding runs through the llama.cpp embedding endpoint (`llama-embed` unit, nomic-embed-text-v2-moe
GGUF, GRAPHIV_EMBED_API overridable) — verified cosine >0.999 vs the SentenceTransformer the corpus
was built with. Docs are token-truncated via the server's /tokenize to reproduce the per-space
max_seq truncation the SentenceTransformer applied (asym 512, sym 2048).

    uv run python phases/phase-4/components/embed_delta.py
"""

from __future__ import annotations

import json
import math
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, LiteralString, cast

import psycopg

REPO = Path(__file__).resolve().parents[3]
PG_DSN = os.environ.get("ARXIVKG_PG_DSN", f"host={REPO}/.pg port=5433 dbname=arxivkg")
EMBED_API = os.environ.get("GRAPHIV_EMBED_API", "http://127.0.0.1:11435")
EMBED_MODEL_NAME = "nomic-embed-text-v2-moe"
PROMPT = "Instruct: classifying the research topic of a paper's abstract.\nQuery:"

# (table, column, prompt_prefix, max_seq, batch) per embedding space. asym is the PROD space
# (embed_mode=asym); sym is kept for research/A-B. Each space delta-scans its own table, so the
# pass is independently resumable, a filled space is a no-op, and an EMPTY table makes this the
# from-zero corpus builder. max_seq mirrors the SentenceTransformer truncation each space was
# built with.
SPACES: tuple[tuple[str, str, str, int, int], ...] = (
    ("paper_embedding_asym", "embedding_asym", "search_document: ", 512, 128),
    ("paper_embedding", "embedding", PROMPT, 2048, 64),
)


def _post(
    path: str, payload: dict[str, Any], timeout: float = 600.0
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    req = urllib.request.Request(
        f"{EMBED_API}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)  # pyright: ignore[reportAny]


def _truncate(text: str, max_seq: int) -> str:
    """Token-truncate to max_seq incl. the 2 special tokens (ST truncation semantics)."""
    toks: list[int] = _post("/tokenize", {"content": text, "add_special": False})[
        "tokens"
    ]
    if len(toks) <= max_seq - 2:
        return text
    return _post("/detokenize", {"tokens": toks[: max_seq - 2]})["content"]


def embed_endpoint(texts: list[str], prefix: str, max_seq: int) -> list[list[float]]:
    """Embed prefixed+truncated docs via /v1/embeddings; returns L2-normalized vectors."""
    inputs = [_truncate(prefix + t, max_seq) for t in texts]
    payload = _post("/v1/embeddings", {"model": EMBED_MODEL_NAME, "input": inputs})
    rows: list[dict[str, Any]] = sorted(  # pyright: ignore[reportExplicitAny]
        payload["data"], key=lambda d: int(d["index"])  # pyright: ignore[reportAny]
    )
    out: list[list[float]] = []
    for row in rows:
        vec = [float(x) for x in row["embedding"]]  # pyright: ignore[reportAny]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        out.append([x / norm for x in vec])
    return out


def _missing(table: str) -> list[tuple[Any, ...]]:  # pyright: ignore[reportExplicitAny]
    with psycopg.connect(PG_DSN) as c:
        rows: list[tuple[Any, ...]] = c.execute(
            cast(
                LiteralString,
                "SELECT m.arxiv_id, m.title, m.abstract FROM paper_meta m "
                f"LEFT JOIN {table} e USING (arxiv_id) "
                "WHERE e.arxiv_id IS NULL AND m.title IS NOT NULL",
            )
        ).fetchall()
    return rows


def run() -> None:
    todo = {table: _missing(table) for table, _, _, _, _ in SPACES}
    for table, rows in todo.items():
        print(f"[embed_delta] {table}: {len(rows):,} papers missing", flush=True)
    if not any(todo.values()):
        return

    for table, col, prefix, max_seq, bs in SPACES:
        rows = todo[table]
        if not rows:
            continue
        t0 = time.time()
        done = 0
        with psycopg.connect(PG_DSN, autocommit=True) as c:
            for i in range(0, len(rows), bs):
                batch = rows[i : i + bs]
                docs = [f"Title: {t or ''}\nAbstract: {a or ''}" for _, t, a in batch]
                vecs = embed_endpoint(docs, prefix, max_seq)
                with c.cursor().copy(
                    cast(LiteralString, f"COPY {table} (arxiv_id, {col}) FROM STDIN")
                ) as cp:
                    for (aid, _t, _a), v in zip(batch, vecs):
                        cp.write_row(
                            [aid, "[" + ",".join("%.5g" % float(x) for x in v) + "]"]
                        )
                done += len(batch)
                if i % (bs * 20) == 0:
                    rate = done / max(1e-6, time.time() - t0)
                    print(
                        f"[embed_delta] {table} {done:,}/{len(rows):,} ({rate:.0f}/s)",
                        flush=True,
                    )
        print(
            f"[embed_delta] {table} done {done:,} in {time.time() - t0:.0f}s",
            flush=True,
        )


if __name__ == "__main__":
    run()
