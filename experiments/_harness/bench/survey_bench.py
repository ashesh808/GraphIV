"""
The 60-survey qrels bench: freeze a pool per survey, then sweep selection arms over it

A survey's answer key is its own reference list, filtered to the ids it mentions three times
The corpus is capped at the survey's month and the survey itself is blocklisted
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg

from graphiv.core.embed import embed_query
from graphiv.core.models import Edge, Landmark, PoolNode
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store, abs_yymm
from graphiv.generate.pipeline import (  # pyright: ignore[reportPrivateUsage]
    TIERS,
    _rank_graded,
    retrieve_rank,
)
from graphiv.retrieve.frontier import rank_landmarks_frontier
from graphiv.retrieve.grade import Grade
from graphiv.retrieve.pagerank import rank_landmarks_ppr
from graphiv.retrieve.topic_anchor import TopicTree
from graphiv.retrieve.trajectory import consensus_picks

from .._boot import HARNESS

HERE = HARNESS
THRESHOLDS = (1, 2, 3, 5)
RECENCY = 0.4
EMBED_MODE = "asym"


@dataclass
class Qrels:
    """
    A survey's answer key: reachable in-corpus references keyed by mention count
    """

    mentions: dict[str, int]
    n_raw: int

    def at(self, n: int) -> set[str]:
        """
        The references the survey mentions at least n times
        """
        return {a for a, c in self.mentions.items() if c >= n}


def qrels_for(store: Store, arxiv_id: str) -> Qrels:
    """
    Resolved references of the survey, dropped to those the capped store could return
    """
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        _ = cur.execute(
            """
            SELECT pc.arxiv_id, count(*) FROM paper ps
            JOIN citation c ON c.citing_id = ps.id AND c.cited_id IS NOT NULL
            JOIN paper pc ON pc.id = c.cited_id
            WHERE ps.arxiv_id = %s GROUP BY pc.arxiv_id
            """,
            (arxiv_id,),
        )
        rows: list[tuple[Any, ...]] = cur.fetchall()  # pyright: ignore[reportExplicitAny]
    raw = {str(a): int(n) for a, n in rows}
    return Qrels({a: n for a, n in raw.items() if store.admits(a)}, len(raw))


def recalls(got: set[str], q: Qrels) -> dict[str, float]:
    """
    Recall at each mention threshold, plus the size of the gold set behind it
    """
    out: dict[str, float] = {}
    for n in THRESHOLDS:
        gold = q.at(n)
        out[f"r@{n}"] = len(got & gold) / len(gold) if gold else 0.0
        out[f"n@{n}"] = float(len(gold))
    return out


def build_pool(
    s: dict[str, Any], tier: str
) -> tuple[
    dict[str, PoolNode], list[Edge], dict[str, Grade], Any, Qrels, int
]:  # pyright: ignore[reportExplicitAny]
    """
    Retrieve and grade once under the survey's cap, returning everything the arms reuse
    """
    yymm = str(s["yymm"])
    cap = abs_yymm(int(yymm[:2]), int(yymm[2:]))
    now = datetime(cap // 100, cap % 100, 28)
    n_pool, target, m, _ = TIERS[tier]
    qvec = embed_query(str(s["question"]), mode=EMBED_MODE)
    store = Store(
        PG_DSN, emb_space=EMBED_MODE, max_yymm=cap, exclude=frozenset({str(s["arxiv_id"])})
    )
    try:
        q = qrels_for(store, str(s["arxiv_id"]))
        p = retrieve_rank(
            store,
            qvec,
            str(s["question"]),
            TopicTree(),
            n_pool,
            target,
            m,
            "ppr",
            False,
            False,
            RECENCY,
            now,
            grade=True,
            fuse=True,
        )
    finally:
        store.close()
    return p.pool, p.edges, p.grades, p.fr, q, m


def leyline_on(
    base_rank: str,
    fused: dict[str, PoolNode],
    pool: dict[str, PoolNode],
    edges: list[Edge],
    grades: dict[str, Grade],
    fr: Any,  # pyright: ignore[reportExplicitAny]
    m: int,
    quota: int,
) -> list[Landmark]:
    """
    The shipped LeyLine construction with its PPR base swapped for any other ranker

        `rank_landmarks_trajectory` hardcodes PPR, so the frontier base needs its own call.
    """
    q = min(quota, max(0, m - 1))
    fn = rank_landmarks_ppr if base_rank == "ppr" else rank_landmarks_frontier
    base = fn(fused, edges, m - q, fr.frontier_year, fr.recent_floor, fr.now_year)
    base_ids = {lm.arxiv_id for lm in base}
    picks, _ = consensus_picks(edges, grades, base_ids, set(fused), q)
    indeg: dict[str, int] = {}
    for e in edges:
        indeg[e.dst] = indeg.get(e.dst, 0) + 1
    chosen = base + [
        Landmark(
            fused[a].arxiv_id,
            fused[a].title,
            fused[a].year,
            fused[a].category,
            fused[a].score,
            indeg.get(a, 0),
        )
        for a in picks
        if a in fused
    ]
    if len(chosen) < m:
        have = {lm.arxiv_id for lm in chosen}
        rest = {a: n for a, n in fused.items() if a not in have}
        for lm in fn(rest, edges, m - len(chosen), fr.frontier_year, fr.recent_floor, fr.now_year):
            chosen.append(lm)
    for lm in chosen:
        lm.score = pool[lm.arxiv_id].score
        g = grades.get(lm.arxiv_id)
        if g is not None:
            lm.role, lm.relevance = g.role, g.relevance
    return chosen[:m]


def arms(
    pool: dict[str, PoolNode],
    edges: list[Edge],
    grades: dict[str, Grade],
    fr: Any,
    m: int,  # pyright: ignore[reportExplicitAny]
) -> dict[str, list[Landmark]]:
    """
    Every selection arm over one frozen pool: the shipped rankers plus two LeyLine quota sweeps
    """
    out: dict[str, list[Landmark]] = {}
    for rank in ("ppr", "frontier", "indegree", "trajectory"):
        out[rank] = _rank_graded(pool, edges, m, rank, False, fr, grades, True)
    fused = {
        a: PoolNode(
            n.arxiv_id,
            n.title,
            n.year,
            n.category,
            n.score * (grades[a].relevance + 2) / 4 if a in grades else n.score,
        )
        for a, n in pool.items()
        if not (a in grades and grades[a].relevance <= -2)
    }
    for qz in (2, 8, 16, 40, m - 1):
        out[f"leyline-ppr-q{qz}"] = leyline_on("ppr", fused, pool, edges, grades, fr, m, qz)
        out[f"leyline-front-q{qz}"] = leyline_on("frontier", fused, pool, edges, grades, fr, m, qz)
    return out


def score(
    s: dict[str, Any], tier: str = "standard"
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """
    Full result record for one survey: pool metrics plus one row per selection arm
    """
    pool, edges, grades, fr, q, m = build_pool(s, tier)
    pool_ids = set(pool)
    rec: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
        "arxiv_id": s["arxiv_id"],
        "category": s["category"],
        "yymm": s["yymm"],
        "question": s["question"],
        "n_pool": len(pool),
        "n_edges": len(edges),
        "m": m,
        "qrels_raw": q.n_raw,
        "qrels_reachable": len(q.mentions),
        "leak": s["arxiv_id"] in pool_ids,
        "pool": recalls(pool_ids, q),
        "pool_ids": sorted(pool_ids),
        "qrels": q.mentions,
        "grades": {a: [g.role, g.relevance] for a, g in grades.items()},
        "arms": {},
    }
    for name, lms in arms(pool, edges, grades, fr, m).items():
        ids = {lm.arxiv_id for lm in lms}
        yrs = [lm.year for lm in lms if lm.year]
        roles: Counter[str] = Counter(lm.role for lm in lms if lm.role)
        rec["arms"][name] = {
            "ids": sorted(ids),
            **recalls(ids, q),
            "hit_rate": len(ids & set(q.mentions)) / len(ids) if ids else 0.0,
            "median_year": sorted(yrs)[len(yrs) // 2] if yrs else 0,
            "roles": dict(roles.most_common(4)),
        }
    return rec


if __name__ == "__main__":
    import sys

    battery: list[dict[str, Any]] = json.loads(
        (HERE / "data" / "battery.json").read_text()
    )  # pyright: ignore[reportExplicitAny]
    want = sys.argv[1] if len(sys.argv) > 1 else battery[0]["arxiv_id"]
    s = next(x for x in battery if x["arxiv_id"] == want)
    rec = score(s)
    _ = (HERE / "data" / f"result_{want}.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: v for k, v in rec.items() if k != "arms"}, indent=1))
    print(f"\n{'arm':<14} {'r@1':>6} {'r@2':>6} {'r@3':>6} {'r@5':>6} {'hit':>6} {'medyr':>6}")
    for name, a in rec["arms"].items():
        print(
            f"{name:<14} {a['r@1']:6.3f} {a['r@2']:6.3f} {a['r@3']:6.3f} {a['r@5']:6.3f} "
            f"{a['hit_rate']:6.3f} {a['median_year']:6d}"
        )
