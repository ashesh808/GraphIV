"""
The set-coverage selectors on the survey benchmark, so 02-05 holds every proposed objective

They need pool embeddings, which is one fetch per survey and the only reason they run separately
Scored exactly like every other arm: fused pool, same slots, gold is three-or-more mentions
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path
from typing import Any

from graphiv.core.models import PoolNode
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store, abs_yymm
from graphiv.retrieve.landmarks import (
    select_facility,
    select_fused_topk,
    select_mmr,
    select_ppr,
    select_proportional,
)

HERE = Path(__file__).parent
POOLS = HERE / "data" / "pools_fixed"
OUT = HERE / "data" / "coverage_arms.json"
MENTION_FLOOR = 3


def main() -> None:
    """
    Score the four set-coverage objectives plus bare ppr and fused top-k
    """
    found: dict[str, dict[str, int]] = {}
    for p in sorted(POOLS.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        pool, edges, grades, m = c["pool"], c["edges"], c["grades"], c["m"]
        sp = str(c["meta"].get("split", "dev"))
        gold = {a for a, n in c["qrels"].items() if int(n) >= MENTION_FLOOR} & set(pool)
        fused = {
            a: PoolNode(
                n.arxiv_id,
                n.title,
                n.year,
                n.category,
                n.score * ((grades[a].relevance + 2) / 4 if a in grades else 1.0),
            )
            for a, n in pool.items()
            if not (a in grades and grades[a].relevance <= -2)
        }
        yymm = str(c["meta"]["yymm"])
        store = Store(PG_DSN, emb_space="asym", max_yymm=abs_yymm(int(yymm[:2]), int(yymm[2:])))
        embs = store.embeddings(list(fused))
        store.conn.close()
        arms = {
            "fused_topk": select_fused_topk(fused, m),
            "ppr_bare": select_ppr(fused, edges, m),
            "mmr": select_mmr(fused, embs, m),
            "facility": select_facility(fused, embs, m),
            "proportional": select_proportional(fused, embs, m),
        }
        for name, ids in arms.items():
            found.setdefault(name, {"dev": 0, "test": 0})[sp] += len(set(ids) & gold)
        print(f"{p.stem} done", flush=True)
    _ = OUT.write_text(json.dumps(found, indent=2), encoding="utf-8")
    print(f"\n{'arm':<16} {'DEV':>5} {'TEST':>5}")
    for k, v in sorted(found.items(), key=lambda kv: -kv[1]["dev"]):
        print(f"{k:<16} {v['dev']:>5} {v['test']:>5}")


if __name__ == "__main__":
    sys.exit(main())
