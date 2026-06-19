"""Step 2 — recover the embedding row -> arxiv_id mapping.

The old `embeddings.py` ran `SELECT id, ... FROM publication` with NO ORDER BY,
then saved embeddings row-aligned to that scan. SQLite returns rows in rowid
order for an unordered full scan, so re-running `SELECT id FROM publication`
on the *same* old db reproduces the exact order. We freeze that id list to
`out/emb_ids.npy` so the npy<->arxiv_id alignment is explicit and auditable.
"""

from __future__ import annotations

import sqlite3

import numpy as np

from _common import (  # noqa: E402
    EMB_IDS_NPY,
    EMB_ROWS,
    NOMIC_NPY,
    OUT_DIR,
    OLD_SQLITE,
)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{OLD_SQLITE}?mode=ro", uri=True)
    try:
        ids = [row[0] for row in conn.execute("SELECT id FROM publication")]
    finally:
        conn.close()
    print(f"[emb_map] {len(ids):,} ids from {OLD_SQLITE.name}", flush=True)

    emb = np.load(NOMIC_NPY, mmap_mode="r")
    print(f"[emb_map] npy shape={emb.shape} dtype={emb.dtype}", flush=True)

    assert (
        len(ids) == emb.shape[0] == EMB_ROWS
    ), f"row mismatch: ids={len(ids)} npy={emb.shape[0]} expected={EMB_ROWS}"

    ids_arr = np.array(ids, dtype=object)
    np.save(EMB_IDS_NPY, ids_arr)
    print(f"[emb_map] froze {len(ids_arr):,} ids -> {EMB_IDS_NPY}", flush=True)
    print(f"[emb_map] sample: {ids[:3]} ... {ids[-2:]}", flush=True)
