"""
Age of the papers LeyLine itself contributes, isolated from the PPR base it rides on

The shipped quota is 8 slots out of 80, so a whole-list age profile dilutes the effect 10 to 1
This measures only the consensus picks, against the base they displaced and the pool at large
"""

from __future__ import annotations

import pickle
import statistics
import sys
from pathlib import Path
from typing import Any

from graphiv.retrieve.pagerank import rank_landmarks_ppr
from graphiv.retrieve.trajectory import QUOTA, consensus_picks

HERE = Path(__file__).parent
CACHE = HERE / "data" / (sys.argv[1] if len(sys.argv) > 1 else "pools")


def main() -> None:
    """
    Print median age and gold hit rate for the LeyLine picks against three references
    """
    ley: list[float] = []
    displaced: list[float] = []
    magnets: list[float] = []
    allpool: list[float] = []
    ley_gold = ley_n = disp_gold = disp_n = 0
    for p in sorted(CACHE.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        pool, edges, grades, fr, m = c["pool"], c["edges"], c["grades"], c["fr"], c["m"]
        qrels = c["qrels"]
        cap = int(fr.now_year)
        fused = {a: n for a, n in pool.items() if not (a in grades and grades[a].relevance <= -2)}
        base = rank_landmarks_ppr(fused, edges, m, fr.frontier_year, fr.recent_floor, cap)
        keep = {lm.arxiv_id for lm in base[: m - QUOTA]}
        picks, _ = consensus_picks(edges, grades, keep, set(fused), QUOTA)
        for lm in base[m - QUOTA : m]:
            displaced.append(float(cap - lm.year))
            disp_n += 1
            disp_gold += 1 if lm.arxiv_id in qrels else 0
        for a in picks:
            ley.append(float(cap - pool[a].year))
            ley_n += 1
            ley_gold += 1 if a in qrels else 0
        magnets.extend(
            float(cap - pool[a].year) for a, g in grades.items() if g.relevance >= 2 and a in pool
        )
        allpool.extend(float(cap - n.year) for n in pool.values() if n.year)
    print(f"{'set':<26} {'n':>6} {'median age':>11} {'mean age':>9} {'gold hit':>9}")
    print(
        f"{'LeyLine picks':<26} {ley_n:>6} {statistics.median(ley):>11.1f} "
        f"{statistics.mean(ley):>9.2f} {ley_gold / max(1, ley_n):>8.1%}"
    )
    print(
        f"{'the PPR slots they took':<26} {disp_n:>6} {statistics.median(displaced):>11.1f} "
        f"{statistics.mean(displaced):>9.2f} {disp_gold / max(1, disp_n):>8.1%}"
    )
    print(
        f"{'magnet set (rel >= 2)':<26} {len(magnets):>6} {statistics.median(magnets):>11.1f} "
        f"{statistics.mean(magnets):>9.2f}"
    )
    print(
        f"{'whole pool':<26} {len(allpool):>6} {statistics.median(allpool):>11.1f} "
        f"{statistics.mean(allpool):>9.2f}"
    )


if __name__ == "__main__":
    main()
