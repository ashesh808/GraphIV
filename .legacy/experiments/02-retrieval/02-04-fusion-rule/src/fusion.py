"""
How to spend one budget of landmark slots across two signals that disagree

02-03 showed the citation graph and the reader are equally good and largely disjoint
This isolates the combining rule: no frontier reservation, no LeyLine quota, same slots
"""

from __future__ import annotations

import json
import pickle
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from graphiv.core.models import Edge, PoolNode
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.recency import age_norm_score

HERE = Path(__file__).parent
POOLS = HERE / "data" / "pools_fixed"
OUT = (
    HERE.parents[1] / "experiments" / "02-retrieval" / "02-04-fusion-rule" / "cache" / "fusion.json"
)
MENTION_FLOOR = 3
RRF_K = 60

Scores = dict[str, float]
Rule = Callable[[Scores, Scores, Scores], Scores]


def _pct(s: Scores) -> Scores:
    """
    Rank percentile, so a citation rate and a -2..2 grade can meet on one scale
    """
    order = sorted(s, key=lambda a: (-s[a], a))
    n = max(1, len(order) - 1)
    return {a: 1.0 - i / n for i, a in enumerate(order)}


def _rrf(*orders: Scores) -> Scores:
    out: Scores = {}
    for s in orders:
        for i, a in enumerate(sorted(s, key=lambda x: (-s[x], x))):
            out[a] = out.get(a, 0.0) + 1.0 / (RRF_K + i + 1)
    return out


def rules() -> dict[str, Rule]:
    """
    Every combining rule, each taking (citations per year, reader relevance, cosine)
    """
    r: dict[str, Rule] = {
        "graph only": lambda g, _v, _c: dict(g),
        "reader only": lambda _g, v, _c: dict(v),
        "cosine only": lambda _g, _v, c: dict(c),
        "multiply, cosine x grade": lambda _g, v, c: {a: c[a] * (v[a] + 2) / 4 for a in c},
        "multiply, graph x grade": lambda g, v, _c: {a: _pct(g)[a] * (v[a] + 2) / 4 for a in g},
        "rrf, graph + reader": lambda g, v, _c: _rrf(g, v),
        "rrf, all three": lambda g, v, c: _rrf(g, v, c),
        "grade first, graph breaks ties": lambda g, v, _c: {
            a: v[a] * 1000.0 + _pct(g)[a] for a in g
        },
    }
    for w in (0.35, 0.5, 0.65, 0.8):
        r[f"blend {w:g} graph"] = lambda g, v, _c, w=w: {
            a: w * _pct(g)[a] + (1 - w) * (v[a] + 2) / 4 for a in g
        }
    return r


def signals(
    pool: dict[str, PoolNode], edges: list[Edge], grades: dict[str, Grade], cap: int
) -> tuple[Scores, Scores, Scores]:
    """
    Citations per year, reader relevance and cosine for every paper in one pool
    """
    indeg: dict[str, int] = {}
    for e in edges:
        indeg[e.dst] = indeg.get(e.dst, 0) + 1
    g = {a: age_norm_score(indeg.get(a, 0), pool[a].year, cap) for a in pool}
    v = {a: float(grades[a].relevance) if a in grades else 0.0 for a in pool}
    c = {a: pool[a].score for a in pool}
    return g, v, c


def quota(g: Scores, v: Scores, n_graph: int, m: int) -> set[str]:
    """
    A hard split: `n_graph` slots by the graph, the rest by the reader, no interleaving
    """
    picked: list[str] = []
    for a in sorted(g, key=lambda x: (-g[x], x)):
        if len(picked) >= n_graph:
            break
        picked.append(a)
    have = set(picked)
    for a in sorted(v, key=lambda x: (-v[x], x)):
        if len(picked) >= m:
            break
        if a not in have:
            picked.append(a)
            have.add(a)
    return have


def main() -> None:
    """
    Score every combining rule on dev and test, against the single-signal and oracle bounds
    """
    found: dict[str, dict[str, int]] = {}
    gold_n = {"dev": 0, "test": 0}
    oracle = {"dev": 0, "test": 0}
    rs = rules()
    for p in sorted(POOLS.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        pool, edges, grades, fr, m = c["pool"], c["edges"], c["grades"], c["fr"], c["m"]
        sp = str(c["meta"].get("split", "dev"))
        qr = {a: int(n) for a, n in c["qrels"].items() if int(n) >= MENTION_FLOOR}
        inp = set(qr) & set(pool)
        gold_n[sp] += len(inp)
        oracle[sp] += min(m, len(inp))
        g, v, cos = signals(pool, edges, grades, int(fr.now_year))
        for name, rule in rs.items():
            sc = rule(g, v, cos)
            top = set(sorted(sc, key=lambda a: (-sc[a], a))[:m])
            found.setdefault(name, {"dev": 0, "test": 0})[sp] += len(top & inp)
        for n_graph in (20, 40, 60):
            name = f"quota {n_graph} graph / {m - n_graph} reader"
            found.setdefault(name, {"dev": 0, "test": 0})[sp] += len(quota(g, v, n_graph, m) & inp)
    best_single = max(found[k]["dev"] for k in ("graph only", "reader only"))
    head = oracle["dev"] - best_single
    print(f"gold in pool: dev {gold_n['dev']}, test {gold_n['test']}")
    print(f"oracle at the same budget: dev {oracle['dev']}, test {oracle['test']}")
    print(f"best single signal on dev: {best_single}, so the headroom is {head}\n")
    print(f"{'rule':<34} {'DEV':>5} {'TEST':>5} {'headroom taken':>15}")
    for name in sorted(found, key=lambda k: -found[k]["dev"]):
        d, t = found[name]["dev"], found[name]["test"]
        print(f"{name:<34} {d:>5} {t:>5} {(d - best_single) / head:>14.0%}")
    print(f"\n{'ORACLE':<34} {oracle['dev']:>5} {oracle['test']:>5} {1.0:>14.0%}")
    payload = {
        "gold_in_pool": gold_n,
        "oracle": oracle,
        "best_single_dev": best_single,
        "headroom_dev": head,
        "rules": [
            {"rule": k, "dev": found[k]["dev"], "test": found[k]["test"]}
            for k in sorted(found, key=lambda x: -found[x]["dev"])
        ],
    }
    _ = OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
