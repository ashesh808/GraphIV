"""
Rewrite every frozen pool's node score to a true cosine against its own question

refined_pool left the hybrid survivors on an RRF scale while every later stage wrote a cosine
A fifth of each pool therefore sat about a hundred times too low and ranked last by default
"""

from __future__ import annotations

import math
import pickle
import sys
from pathlib import Path
from typing import Any

from graphiv.core.embed import embed_query
from graphiv.core.models import PoolNode
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store, abs_yymm

HERE = Path(__file__).parent
SRC = HERE / "data" / "pools"
DST = HERE / "data" / "pools_fixed"

EMBED_MODE = "asym"
RRF_MAX = 0.1


def cosines(store: Store, qvec: list[float], ids: list[str]) -> dict[str, float]:
    """
    Cosine of each paper against the query, read straight from the production space
    """
    qn = math.sqrt(sum(x * x for x in qvec)) or 1.0
    out: dict[str, float] = {}
    for aid, vec in store.embeddings(ids).items():
        vn = math.sqrt(sum(x * x for x in vec)) or 1.0
        out[aid] = sum(a * b for a, b in zip(qvec, vec, strict=True)) / (qn * vn)
    return out


def main() -> None:
    """
    Write a corrected copy of every pool and report how far the rescored papers moved
    """
    DST.mkdir(parents=True, exist_ok=True)
    n_fixed = n_total = n_missing = 0
    for p in sorted(SRC.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        meta: dict[str, Any] = c["meta"]  # pyright: ignore[reportExplicitAny]
        yymm = str(meta["yymm"])
        cap = abs_yymm(int(yymm[:2]), int(yymm[2:]))
        store = Store(
            PG_DSN,
            emb_space=EMBED_MODE,
            max_yymm=cap,
            exclude=frozenset({str(meta["arxiv_id"])}),
        )
        qvec = embed_query(str(meta["question"]), mode=EMBED_MODE)
        pool: dict[str, PoolNode] = c["pool"]
        cos = cosines(store, qvec, list(pool))
        store.conn.close()
        was_rrf = sum(1 for n in pool.values() if n.score < RRF_MAX)
        fixed: dict[str, PoolNode] = {}
        for a, n in pool.items():
            s = cos.get(a)
            if s is None:
                n_missing += 1
                s = n.score
            fixed[a] = PoolNode(n.arxiv_id, n.title, n.year, n.category, s)
        c["pool"] = fixed
        with (DST / p.name).open("wb") as fh:
            pickle.dump(c, fh)
        n_fixed += was_rrf
        n_total += len(pool)
        print(f"{p.stem}  {len(pool):>4} papers, {was_rrf:>3} were on the RRF scale", flush=True)
    print(f"\n{n_total} papers over {len(list(SRC.glob('*.pkl')))} pools")
    print(f"{n_fixed} were RRF-scored ({n_fixed / max(1, n_total):.1%}), now true cosine")
    print(f"{n_missing} had no embedding and kept their old score")


if __name__ == "__main__":
    sys.exit(main())
