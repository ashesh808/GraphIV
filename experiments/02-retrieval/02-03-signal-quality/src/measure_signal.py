"""
Which pool signal actually predicts that the survey cited the paper

Runs on the 60 frozen pools, so gold membership replaces a model grading its own retrieval
It also measures the score-scale split the pool carries out of refined_pool
"""

from __future__ import annotations

import pickle
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from graphiv.core.models import Edge, PoolNode
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.recency import age_norm_score

HERE = Path(__file__).parent
POOLS = HERE / "data" / (sys.argv[1] if len(sys.argv) > 1 else "pools")

MENTION_FLOOR = 3
# hybrid_pool leaves RRF scores near 1/60, every later stage writes a cosine, so this splits them
RRF_MAX = 0.1


def signals(
    pool: dict[str, PoolNode], edges: list[Edge], grades: dict[str, Grade], cap: int
) -> dict[str, dict[str, float]]:
    """
    Per-paper value of every signal a selector could rank on
    """
    indeg: dict[str, int] = {}
    for e in edges:
        indeg[e.dst] = indeg.get(e.dst, 0) + 1
    return {
        "in-degree": {a: float(indeg.get(a, 0)) for a in pool},
        "citations per year": {a: age_norm_score(indeg.get(a, 0), pool[a].year, cap) for a in pool},
        "pool score (cosine)": {a: pool[a].score for a in pool},
        "reader relevance": {a: float(grades[a].relevance) if a in grades else 0.0 for a in pool},
    }


def top_k(scores: dict[str, float], k: int) -> set[str]:
    """
    The k highest-scoring ids, ties broken by id so the set is deterministic
    """
    return set(sorted(scores, key=lambda a: (-scores[a], a))[:k])


def main() -> None:
    """
    Print gold rate by signal decile, precision at the landmark budget, and the scale split
    """
    hits: Counter[str] = Counter()
    deciles: dict[str, list[list[float]]] = {}
    scale = {"rrf": [0, 0], "cosine": [0, 0]}
    scale_grade: dict[str, list[float]] = {"rrf": [], "cosine": []}
    n_pool = n_gold = n_budget = 0
    pair = {"both": 0, "graph only": 0, "reader only": 0, "neither": 0}
    for p in sorted(POOLS.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        pool, edges, grades, fr, m = c["pool"], c["edges"], c["grades"], c["fr"], c["m"]
        gold = {a for a, n in c["qrels"].items() if int(n) >= MENTION_FLOOR}
        in_pool = gold & set(pool)
        n_pool += len(pool)
        n_gold += len(in_pool)
        n_budget += m
        sig = signals(pool, edges, grades, int(fr.now_year))
        for name, sc in sig.items():
            hits[name] += len(top_k(sc, m) & in_pool)
            order = sorted(sc, key=lambda a: -sc[a])
            rows = deciles.setdefault(name, [[] for _ in range(10)])
            for i, a in enumerate(order):
                d = min(9, i * 10 // max(1, len(order)))
                rows[d].append(1.0 if a in in_pool else 0.0)
        g_top = top_k(sig["citations per year"], m)
        r_top = top_k(sig["reader relevance"], m)
        for a in in_pool:
            in_g, in_r = a in g_top, a in r_top
            key = (
                "both"
                if in_g and in_r
                else "graph only" if in_g else "reader only" if in_r else "neither"
            )
            pair[key] += 1
        for a, n in pool.items():
            key = "rrf" if n.score < RRF_MAX else "cosine"
            scale[key][0] += 1
            scale[key][1] += 1 if a in in_pool else 0
            if a in grades:
                scale_grade[key].append(float(grades[a].relevance))
    print(f"60 pools, {n_pool} papers, {n_gold} of them gold, budget {n_budget} slots\n")
    base = n_gold / n_pool
    print(f"{'signal':<22} {'gold in top-m':>14} {'precision':>10} {'lift':>6}")
    print(f"{'(base rate)':<22} {'':>14} {base:>9.1%} {1.0:>6.1f}")
    for name, got in hits.most_common():
        pr = got / n_budget
        print(f"{name:<22} {got:>14} {pr:>9.1%} {pr / base:>6.1f}")
    print(f"\n{'signal':<22} " + " ".join(f"d{i + 1:<4}" for i in range(10)))
    for name, rows in deciles.items():
        cells = " ".join(f"{statistics.mean(r) if r else 0:>5.1%}" for r in rows)
        print(f"{name:<22} {cells}")
    print("\nwhere the gold sits, graph top-m against reader top-m")
    for k, v in pair.items():
        print(f"  {k:<12} {v:>4} gold papers ({v / max(1, n_gold):>5.1%})")
    union = pair["both"] + pair["graph only"] + pair["reader only"]
    print(f"  either one  {union:>4} gold papers ({union / max(1, n_gold):>5.1%})")
    print("\nscore scale the pool actually carries")
    for key in ("rrf", "cosine"):
        n, g = scale[key]
        rel = statistics.mean(scale_grade[key]) if scale_grade[key] else 0.0
        print(
            f"  {key:<7} {n:>6} papers ({n / n_pool:>5.1%})  gold {g:>4} ({g / max(1, n):>5.1%})"
            f"  mean reader relevance {rel:>5.2f}"
        )


if __name__ == "__main__":
    sys.exit(main())
