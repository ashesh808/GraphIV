"""A3 smoke test: run the rewritten (pgvector/SQL) retrieve+rank end-to-end, NO LLM.

Exercises Store.vector_pool / lexical_pool / drill / recent_members / ancestors / edges_among
via the real pipeline.retrieve_rank path, then prints pool/edge/landmark stats so we can eyeball
that the SQL retrieval matches what Neo4j used to produce.

    uv run python scratchpad/smoke_retrieval.py "diffusion models for image generation"
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "phases" / "phase-6" / "components"))
sys.path.insert(0, str(_REPO / "phases"))

from _common import PG_DSN  # noqa: E402
from pipeline import _free_router_vram, hyde_query, retrieve_rank  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from store import Store  # noqa: E402
from topic_anchor import TopicTree  # noqa: E402


def main() -> None:
    q = sys.argv[1] if len(sys.argv) > 1 else "diffusion models for image generation"
    hyde = hyde_query(q)
    print(f"[smoke] hyde: {hyde[:140]}")
    _free_router_vram()
    t0 = time.time()
    qvec = embed_query(hyde)
    free_model()
    print(f"[smoke] embed {time.time() - t0:.1f}s  dim={len(qvec)}")

    store = Store(PG_DSN)
    tree = TopicTree()
    t0 = time.time()
    p = retrieve_rank(
        store, qvec, q, tree, 400, 280, 80, "ppr", False, False, 0.4, datetime.now()
    )
    print(f"[smoke] retrieve_rank {time.time() - t0:.1f}s")
    print(
        f"[smoke] pool={len(p.pool)} edges={len(p.edges)} landmarks={len(p.landmarks)} "
        f"leaf={p.leaf} frontier_year={p.fr.frontier_year} spine={len(p.spine)} tensions={len(p.tens)}"
    )
    print("[smoke] top landmarks:")
    for lm in p.landmarks[:12]:
        print(f"    {lm.year} indeg={lm.in_degree:<4} {lm.arxiv_id:<14} {lm.title[:60]}")
    store.close()


if __name__ == "__main__":
    main()
