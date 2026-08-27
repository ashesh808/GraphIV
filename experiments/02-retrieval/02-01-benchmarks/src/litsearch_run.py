"""
Run GraphIV's retrieval channels over the LitSearch queries that map into our corpus

LitSearch is a known-item task, mean 1.07 gold papers per query, so recall@5 is its metric
Three arms isolate what the fusion buys: dense alone, lexical alone, and the shipped hybrid
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from graphiv.core.embed import embed_query
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store, abs_yymm
from graphiv.retrieve.hybrid import hybrid_pool

HERE = Path(__file__).parent
SRC = HERE / "external" / "litsearch_mapped.jsonl"
KS = (5, 20, 80, 400)
CAP = abs_yymm(24, 7)  # LitSearch released 2024-07; nothing after it existed for its authors


def ranked(store: Store, q: str, qvec: list[float], arm: str, n: int) -> list[str]:
    """
    One arm's ranked id list for a query, longest k first so every cutoff reads off it
    """
    if arm == "dense":
        vec = store.vector_pool(qvec, n)
        return sorted(vec, key=lambda a: vec[a].score, reverse=True)
    if arm == "lexical":
        return [x.arxiv_id for x in store.lexical_pool(q, n)]
    pool = hybrid_pool(store, qvec, q, n)
    return sorted(pool, key=lambda a: pool[a].score, reverse=True)


def main(capped: bool, limit: int) -> None:
    """
    Score each arm at every cutoff over the usable queries and print the recall table
    """
    rows: list[dict[str, Any]] = [
        json.loads(x) for x in SRC.read_text().splitlines() if x.strip()
    ]  # pyright: ignore[reportExplicitAny]
    usable = [r for r in rows if r["gold_arxiv_ids"]][:limit]
    arms = ("dense", "lexical", "hybrid")
    hits: dict[str, dict[int, int]] = {a: {k: 0 for k in KS} for a in arms}
    tot = 0
    store = Store(PG_DSN, emb_space="asym", max_yymm=CAP if capped else None)
    t0 = time.time()
    try:
        for i, r in enumerate(usable, 1):
            q = str(r["query"])
            gold = set(r["gold_arxiv_ids"])
            qvec = embed_query(q, mode="asym")
            tot += 1
            for a in arms:
                order = ranked(store, q, qvec, a, max(KS))
                for k in KS:
                    if gold & set(order[:k]):
                        hits[a][k] += 1
            if i % 50 == 0:
                print(f"  {i}/{len(usable)}  {time.time() - t0:.0f}s", flush=True)
    finally:
        store.close()
    print(
        f"\nLitSearch, {tot} queries with at least one gold paper in our corpus, "
        f"corpus {'capped at 2024-07' if capped else 'uncapped (3.10M)'}\n"
    )
    print(f"{'arm':<10} " + " ".join(f"{'R@' + str(k):>8}" for k in KS))
    for a in arms:
        print(f"{a:<10} " + " ".join(f"{hits[a][k] / tot:>8.3f}" for k in KS))


if __name__ == "__main__":
    main(
        "--capped" in sys.argv,
        int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 10**6,
    )
