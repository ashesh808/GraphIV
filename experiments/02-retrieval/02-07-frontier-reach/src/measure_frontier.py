"""
What the frontier reservation buys and what it costs, swept as a size

02-04's best rule drops the reservation entirely, which wins coverage and loses the newest work
This sweeps the reserved slot count so the trade is a curve rather than an on-off claim
"""

from __future__ import annotations

import json
import pickle
import statistics
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from _harness.bench.joint_selector import assemble

from graphiv.core.models import Edge, PoolNode
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.recency import age_norm_score

HERE = Path(__file__).parent
POOLS = HERE / "data" / "pools_fixed"
OUT = HERE.parents[1] / "experiments" / "02-retrieval" / "02-07-frontier-reach" / "cache"

MENTION_FLOOR = 3
W_GRAPH = 0.65
FLOORS = (0, 8, 16, 24, 32, 48)


def _pct(s: dict[str, float]) -> dict[str, float]:
    order = sorted(s, key=lambda a: (-s[a], a))
    n = max(1, len(order) - 1)
    return {a: 1.0 - i / n for i, a in enumerate(order)}


def joint_score(
    pool: dict[str, PoolNode], edges: list[Edge], grades: dict[str, Grade], cap: int
) -> dict[str, float]:
    """
    The shipped joint score, so the reservation is the only thing this experiment varies
    """
    indeg: dict[str, int] = {}
    for e in edges:
        indeg[e.dst] = indeg.get(e.dst, 0) + 1
    g = _pct({a: age_norm_score(indeg.get(a, 0), pool[a].year, cap) for a in pool})
    return {
        a: W_GRAPH * g[a]
        + (1 - W_GRAPH) * ((float(grades[a].relevance) if a in grades else 0.0) + 2) / 4
        for a in pool
    }


def main() -> None:
    """
    Sweep the reserved slot count and report coverage against how new the picks are
    """
    arms: dict[str, dict[str, Any]] = {}  # pyright: ignore[reportExplicitAny]
    gold_n = {"dev": 0, "test": 0}
    for p in sorted(POOLS.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        pool, edges, grades, fr, m = c["pool"], c["edges"], c["grades"], c["fr"], c["m"]
        sp = str(c["meta"].get("split", "dev"))
        gold = {a for a, n in c["qrels"].items() if int(n) >= MENTION_FLOOR} & set(pool)
        gold_n[sp] += len(gold)
        cap = int(fr.now_year)
        sc = joint_score(pool, edges, grades, cap)
        cases: list[tuple[str, int, bool]] = [("no reservation", 0, False)]
        cases += [(f"reserve {f} slots", f, True) for f in FLOORS if f > 0]
        cases.append((f"shipped adaptive floor ({fr.recent_floor})", fr.recent_floor, True))
        for name, floor, reserve in cases:
            key = "shipped adaptive floor" if name.startswith("shipped") else name
            lms = assemble(
                sc,
                pool,
                edges,
                grades,
                replace(fr, recent_floor=floor),
                m,
                quota=0,
                reserve=reserve,
            )
            ages = [cap - lm.year for lm in lms if lm.year]
            a = arms.setdefault(key, {"dev": 0, "test": 0, "ages": [], "fresh": 0, "n": 0})
            a[sp] += len({lm.arxiv_id for lm in lms} & gold)
            a["ages"].extend(float(x) for x in ages)  # pyright: ignore[reportAny]
            a["fresh"] += sum(1 for x in ages if x <= 1)
            a["n"] += len(ages)
    rows = [
        {
            "arm": k,
            "dev": v["dev"],
            "test": v["test"],
            "median age": statistics.median(v["ages"]),  # pyright: ignore[reportAny]
            "within 1 year": v["fresh"],
            "share within 1 year": round(v["fresh"] / max(1, v["n"]), 4),
        }
        for k, v in arms.items()
    ]
    rows.sort(key=lambda r: -int(r["dev"]))
    OUT.mkdir(parents=True, exist_ok=True)
    _ = (OUT / "frontier_reach.json").write_text(
        json.dumps({"gold_in_pool": gold_n, "arms": rows}, indent=2), encoding="utf-8"
    )
    print(f"gold in pool: dev {gold_n['dev']}, test {gold_n['test']}\n")
    print(f"{'arm':<32} {'DEV':>5} {'TEST':>5} {'med age':>8} {'<=1yr':>7} {'share':>7}")
    for r in rows:
        print(
            f"{r['arm']:<32} {r['dev']:>5} {r['test']:>5} {r['median age']:>8.1f} "
            f"{r['within 1 year']:>7} {r['share within 1 year']:>7.1%}"
        )


if __name__ == "__main__":
    sys.exit(main())
