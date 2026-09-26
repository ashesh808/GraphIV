"""
Lifting the rel >= 2 ceiling on the LeyLine consensus walk

Shipped, only rel >= 2 papers seed the walk and only they can be collected off a thread
This sweeps both limits independently over the 60 frozen pools, scored on the 8 quota slots
"""

from __future__ import annotations

import pickle
import random
import statistics
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Any

from graphiv.core.models import Edge
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.pagerank import rank_landmarks_ppr
from graphiv.retrieve.trajectory import GAMMA, MAX_LINEAGES, QUOTA, SEEDS, Adj, _adjacency

HERE = Path(__file__).parent
CACHE = HERE / "data" / (sys.argv[1] if len(sys.argv) > 1 else "pools")


def _reachable(adj: Adj, w: dict[str, float]) -> dict[str, float]:
    radj: Adj = {}
    for u, cs in adj.items():
        for c in cs:
            radj.setdefault(c, []).append(u)
    r: dict[str, float] = {}
    for src, ws in w.items():
        if ws <= 0:
            continue
        seen = {src}
        dq: deque[str] = deque([src])
        while dq:
            v = dq.popleft()
            r[v] = r.get(v, 0.0) + ws
            for p in radj.get(v, ()):
                if p not in seen:
                    seen.add(p)
                    dq.append(p)
    return r


def _lineage(
    root: str,
    adj: Adj,
    w: dict[str, float],
    r: dict[str, float],
    rng: random.Random,
    collect_all: bool,
) -> dict[str, float]:
    """
    One forward thread from `root`, returning the nodes it collects and their weight

        With `collect_all`, every node the thread touches is collectable, so a paper the
        reader graded below the magnet floor can still be picked for sitting on the line.
    """
    visited, collected = {root}, dict[str, float]()
    stack = [root]
    while stack:
        n = stack.pop()
        if w.get(n, 0.0) > 0:
            collected[n] = w[n]
        elif collect_all:
            collected[n] = 0.0
        cps = [(c, r.get(c, 0.0)) for c in adj.get(n, ()) if r.get(c, 0.0) > 0]
        if not cps:
            continue
        keyed = sorted(((rng.random() ** (1.0 / wt), c) for c, wt in cps), reverse=True)
        for _, c in keyed[:1]:
            if c not in visited:
                visited.add(c)
                stack.append(c)
    return collected


def picks_for(
    edges: list[Edge],
    grades: dict[str, Grade],
    exclude: set[str],
    pool_ids: set[str],
    quota: int,
    floor: int,
    collect_all: bool,
) -> list[str]:
    """
    The shipped consensus walk with the magnet floor and the collection filter both open
    """
    w0 = {
        a: (g.relevance + 2) / 4
        for a, g in grades.items()
        if g.relevance >= floor and a in pool_ids and a not in exclude
    }
    if not w0 or quota <= 0:
        return []
    adj = _adjacency(edges)
    freq: Counter[str] = Counter()
    for seed in range(SEEDS):
        rng = random.Random(seed)
        w = dict(w0)
        picked: list[str] = []
        for _ in range(MAX_LINEAGES):
            if len(picked) >= quota * 3:
                break
            r = _reachable(adj, w)
            cand = [n for n in r if r[n] > 0]
            if not cand:
                break
            root = max(cand, key=lambda n: r[n])
            collected = _lineage(root, adj, w, r, rng, collect_all)
            if not collected:
                break
            for a in sorted(collected, key=lambda x: -collected[x]):
                if a not in set(picked) and a not in exclude:
                    picked.append(a)
                w[a] = w.get(a, 0.0) * GAMMA
        freq.update(picked)
    ranked = sorted(freq, key=lambda a: (-freq[a], -w0.get(a, 0.0), a))
    return [a for a in ranked if a in pool_ids and a not in exclude][:quota]


ARMS: list[tuple[str, int, bool]] = [
    ("shipped (rel>=2, magnets only)", 2, False),
    ("rel>=1, magnets only", 1, False),
    ("rel>=0, magnets only", 0, False),
    ("rel>=2, any node on thread", 2, True),
    ("rel>=1, any node on thread", 1, True),
    ("rel>=0, any node on thread", 0, True),
]


def main() -> None:
    """
    Gold hit rate, age and full-list gold count for each ceiling setting, dev then test
    """
    stats: dict[str, dict[str, Any]] = {  # pyright: ignore[reportExplicitAny]
        n: {"hit": 0, "n": 0, "age": [], "gold": {"dev": 0, "test": 0}} for n, _, _ in ARMS
    }
    base_hit = base_n = 0
    base_age: list[float] = []
    base_gold = {"dev": 0, "test": 0}
    for p in sorted(CACHE.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        pool, edges, grades, fr, m = c["pool"], c["edges"], c["grades"], c["fr"], c["m"]
        qrels, sp = c["qrels"], str(c["meta"].get("split", "dev"))
        cap = int(fr.now_year)
        fused = {a: n for a, n in pool.items() if not (a in grades and grades[a].relevance <= -2)}
        base = rank_landmarks_ppr(fused, edges, m, fr.frontier_year, fr.recent_floor, cap)
        keep = [lm.arxiv_id for lm in base[: m - QUOTA]]
        kept = set(keep)
        for lm in base[m - QUOTA : m]:
            base_age.append(float(cap - lm.year))
            base_n += 1
            base_hit += 1 if lm.arxiv_id in qrels else 0
        base_gold[sp] += len({lm.arxiv_id for lm in base} & set(qrels))
        for name, floor, call in ARMS:
            picks = picks_for(edges, grades, kept, set(fused), QUOTA, floor, call)
            s = stats[name]
            for a in picks:
                s["age"].append(float(cap - pool[a].year))
                s["n"] += 1
                s["hit"] += 1 if a in qrels else 0
            s["gold"][sp] += len((kept | set(picks)) & set(qrels))
    print(f"{'arm':<32} {'picks':>6} {'gold hit':>9} {'med age':>8} {'DEV':>6} {'TEST':>6}")
    print(
        f"{'PPR slots the quota takes':<32} {base_n:>6} "
        f"{base_hit / max(1, base_n):>8.1%} {statistics.median(base_age):>8.1f} "
        f"{base_gold['dev']:>6} {base_gold['test']:>6}"
    )
    for name, _, _ in ARMS:
        s = stats[name]
        med = statistics.median(s["age"]) if s["age"] else 0.0  # pyright: ignore[reportAny]
        print(
            f"{name:<32} {s['n']:>6} {s['hit'] / max(1, s['n']):>8.1%} {med:>8.1f} "
            f"{s['gold']['dev']:>6} {s['gold']['test']:>6}"
        )


if __name__ == "__main__":
    sys.exit(main())
