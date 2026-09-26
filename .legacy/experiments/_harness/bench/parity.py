"""
Asserts the new selector registry reproduces the old rankers exactly, pool by pool

Any drift here silently invalidates the 02-05 table, so this runs before the old code goes
"""

from __future__ import annotations

import pickle
import sys
from typing import Any

from graphiv.core.models import Edge, Landmark, PoolNode
from graphiv.retrieve.api import Selection
from graphiv.retrieve.frontier import rank_landmarks_frontier
from graphiv.retrieve.grade import Grade, fused_score
from graphiv.retrieve.joint import rank_landmarks_joint
from graphiv.retrieve.pagerank import rank_landmarks_ppr
from graphiv.retrieve.recency import FrontierSpec
from graphiv.retrieve.select import NamedSelector
from graphiv.retrieve.subgraph import rank_landmarks
from graphiv.retrieve.trajectory import rank_landmarks_trajectory

from .._boot import HARNESS

POOLS = HARNESS / "pools"
ARMS = ("ppr", "frontier", "indegree", "trajectory", "joint")


def old(
    arm: str,
    pool: dict[str, PoolNode],
    edges: list[Edge],
    m: int,
    fr: FrontierSpec,
    grades: dict[str, Grade],
) -> list[str]:
    """
    The pre-refactor ranker, with the fusion `_rank_graded` used to apply before calling it
    """
    ranked = {
        a: PoolNode(n.arxiv_id, n.title, n.year, n.category, fused_score(n.score, grades.get(a)))
        for a, n in pool.items()
        if not (a in grades and grades[a].relevance <= -2)
    }
    fy, floor, now = fr.frontier_year, fr.recent_floor, fr.now_year
    out: list[Landmark]
    if arm == "indegree":
        out = rank_landmarks(ranked, edges, m)
    elif arm == "ppr":
        out = rank_landmarks_ppr(ranked, edges, m, fy, floor, now)
    elif arm == "frontier":
        out = rank_landmarks_frontier(ranked, edges, m, fy, floor, now)
    elif arm == "trajectory":
        out = rank_landmarks_trajectory(ranked, edges, m, fy, floor, now, grades)
    else:
        out = rank_landmarks_joint(ranked, edges, m, now, grades)
    return [lm.arxiv_id for lm in out]


def main() -> None:
    """
    Compare id lists arm by arm and print the first mismatch in each
    """
    same: dict[str, int] = {a: 0 for a in ARMS}
    drift: dict[str, list[str]] = {a: [] for a in ARMS}
    n = 0
    for p in sorted(POOLS.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        pool, edges, grades, fr, m = c["pool"], c["edges"], c["grades"], c["fr"], c["m"]
        n += 1
        sel = Selection(pool, edges, m, fr, grades)
        for arm in ARMS:
            before = old(arm, pool, edges, m, fr, grades)
            new = [lm.arxiv_id for lm in NamedSelector(arm).select(sel)]
            if before == new:
                same[arm] += 1
            else:
                shared = len(set(before) & set(new))
                drift[arm].append(f"{p.stem}: {shared}/{len(before)} shared")
    print(f"{n} pools\n")
    print(f"{'arm':<14} {'identical':>10} {'drifted':>9}")
    for arm in ARMS:
        print(f"{arm:<14} {same[arm]:>10} {len(drift[arm]):>9}")
    for arm in ARMS:
        if drift[arm]:
            print(f"\n{arm} first drifts:")
            for line in drift[arm][:5]:
                print(f"  {line}")


if __name__ == "__main__":
    sys.exit(main())
