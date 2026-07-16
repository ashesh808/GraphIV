"""Embed corpus papers that lack a vector (the post-.npy delta, e.g. 2026) -> paper_embedding.

The migration imported the frozen nomic .npy (2.92M, pre-2026); newer papers (all of 2026 + a few
2025) have metadata but no embedding, so phase-6 `frontier_pull` can't surface them (its vector
search only sees `paper_embedding`). This embeds those papers with the SAME nomic model + prompt +
"Title: ..\nAbstract: .." doc format the corpus used, and inserts into `paper_embedding` (the HNSW
index picks up new rows automatically). Resumable: only embeds papers still missing a vector.

    uv run python phases/phase-4/components/embed_delta.py
"""

from __future__ import annotations

import os

# reduce CUDA fragmentation for the MoE encoder (set before torch loads CUDA)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import time  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, LiteralString, cast  # noqa: E402

import psycopg  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
PG_DSN = os.environ.get("ARXIVKG_PG_DSN", f"host={REPO}/.pg port=5433 dbname=arxivkg")
MODEL = REPO / "model" / "nomic-embed-text-v2-moe"
PROMPT = "Instruct: classifying the research topic of a paper's abstract.\nQuery:"
LLM_ROUTER = "http://localhost:11434"
BATCH = 64  # nomic-v2-moe is memory-heavy; 512 OOMs a 24GB 3090 on long abstracts


def _free_router_vram() -> None:
    import urllib.request  # noqa: PLC0415

    try:
        _ = urllib.request.urlopen(f"{LLM_ROUTER}/router/restart", timeout=120)
    except Exception:  # noqa: BLE001
        pass


# (table, column, prompt, prompt_name, max_seq, batch) per embedding space. asym is the
# PROD space (embed_mode=asym); sym is kept for research/A-B. Each space delta-scans its
# own table, so the pass is independently resumable, a filled space is a no-op, and an
# EMPTY table makes this the from-zero corpus builder (asym @ seq 512 takes batch 512;
# sym @ seq 2048 OOMs past 64 on a 24GB 3090).
SPACES: tuple[tuple[str, str, str | None, str | None, int, int], ...] = (
    ("paper_embedding_asym", "embedding_asym", None, "passage", 512, 512),
    ("paper_embedding", "embedding", PROMPT, None, 2048, BATCH),
)


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
    import torch  # noqa: PLC0415
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    todo = {table: _missing(table) for table, _, _, _, _, _ in SPACES}
    for table, rows in todo.items():
        print(f"[embed_delta] {table}: {len(rows):,} papers missing", flush=True)
    if not any(todo.values()):
        return

    _free_router_vram()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[embed_delta] loading nomic on {dev} ...", flush=True)
    model = SentenceTransformer(str(MODEL), trust_remote_code=True, device=dev)

    for table, col, prompt, prompt_name, max_seq, bs in SPACES:
        rows = todo[table]
        if not rows:
            continue
        model.max_seq_length = max_seq
        t0 = time.time()
        done = 0
        with psycopg.connect(PG_DSN, autocommit=True) as c:
            for i in range(0, len(rows), bs):
                batch = rows[i : i + bs]
                docs = [f"Title: {t or ''}\nAbstract: {a or ''}" for _, t, a in batch]
                vecs = model.encode(
                    docs,
                    prompt=prompt,
                    prompt_name=prompt_name,
                    normalize_embeddings=True,
                    batch_size=bs,
                )
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
