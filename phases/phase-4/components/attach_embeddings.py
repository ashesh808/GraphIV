"""Step 4 — attach reused nomic embeddings onto Paper nodes.

Reads the frozen row->arxiv_id list (out/emb_ids.npy) and the nomic vectors,
then batches `SET p.embedding` onto matching Paper nodes. Papers absent from the
current graph (the ~3% old-dump gap) simply don't match and are skipped.

Relies on the `paper_id` uniqueness constraint (created in import_neo4j.sh) so
each MATCH on arxiv_id is index-backed.
"""

from __future__ import annotations

import time

import numpy as np

from _common import (  # noqa: E402
    EMB_IDS_NPY,
    NEO4J_DB,
    NOMIC_NPY,
    neo4j_driver,
)

BATCH = 5_000
SET_EMB = (
    "UNWIND $rows AS r "
    "MATCH (p:Paper {arxiv_id: r.id}) "
    "SET p.embedding = r.vec "
    "RETURN count(*) AS n"
)


def main() -> None:
    ids = np.load(EMB_IDS_NPY, allow_pickle=True)
    emb = np.load(NOMIC_NPY, mmap_mode="r")
    assert len(ids) == emb.shape[0]
    total = len(ids)
    print(
        f"[attach] {total:,} vectors ({emb.shape[1]}D) to attach in batches of {BATCH}",
        flush=True,
    )

    matched = 0
    t0 = time.time()
    with neo4j_driver() as drv, drv.session(database=NEO4J_DB) as session:
        for start in range(0, total, BATCH):
            end = min(start + BATCH, total)
            chunk_ids = ids[start:end]
            chunk_vecs = emb[start:end].tolist()
            rows = [
                {"id": str(chunk_ids[i]), "vec": chunk_vecs[i]}
                for i in range(end - start)
            ]
            rec = session.run(SET_EMB, rows=rows).single()
            matched += int(rec["n"]) if rec else 0
            if end % 250_000 == 0 or end == total:
                rate = end / (time.time() - t0)
                print(
                    f"[attach] {end:,}/{total:,} sent, {matched:,} matched ({rate:,.0f}/s)",
                    flush=True,
                )
    print(f"[attach] done: {matched:,} nodes now carry an embedding", flush=True)
