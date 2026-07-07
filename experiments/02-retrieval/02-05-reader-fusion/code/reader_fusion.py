"""experiment 02-05 — reader relevance fusion (the measure-gate for `--include-fuse`).

02-02 measured ~22% `unrelated` landmarks whose in-degree matches `core` (fame PPR can't see);
02-03's 0.35 ancestor floor removed the injection-side noise but left the ranking blind to
topical relevance. This measures the shipped reader-fusion lever: every landmark candidate is
graded (production `reader_grade`: 6-class role + relevance -2..2, cached by question-hash) and
ranking runs on `cosine x norm(rel)` with -2 excluded. Variants sweep the normalization:
  baseline  : cosine-only ranking (grades collected for labels, unused in ranking)
  fuse      : norm = (rel+2)/4 in [0,1]  — the ship candidate (production formula)
  fuse_mild : norm = 0.5 + 0.5*(rel+2)/4 in [0.5,1] — softer damping, no self-exclusion

Both sides of the tradeoff, per the measure-before-ship rule:
  - recall    : landmark_recall + spine_recall over the 3 gold topics (grader-independent —
                THE gate; fusion must not lose canonical/spine papers).
  - precision : relevance_rate = 1 - unrelated_frac over all 27 topics. CAVEAT: the labels come
                from the same grader that drives fusion, so precision gains are partly
                by-construction; report them, gate on recall.
  - composition: role fractions of the committed landmarks.

    uv run python experiments/02-retrieval/02-05-reader-fusion/run.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir
_REPO = _HERE.parents[4]  # code -> NN-slug -> 02-retrieval -> experiments -> repo
for _p in (
    str(_REPO / "experiments"),
    str(_REPO / "phases"),
    str(_REPO / "phases" / "phase-6" / "components"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _harness.topics import TOPICS, battery  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

from _common import PG_DSN  # noqa: E402
from pagerank import rank_landmarks_ppr  # noqa: E402
from pipeline import TIERS, _free_router_vram  # noqa: E402
from reader_grade import LABELS, Grade, candidates, grade_many  # noqa: E402
from recency import FrontierSpec, detect_frontier  # noqa: E402
from retrieval_hybrid import hybrid_pool  # noqa: E402
from retrieval_refined import frontier_pull  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from store import Store  # noqa: E402
from subgraph import (  # noqa: E402
    Edge,
    PoolNode,
    augment_with_ancestors,
    induce_subgraph,
)

RESULTS = _EXP / "results"

# (name, use fused ranking, norm floor: fused = cosine * (floor + (1-floor)*(rel+2)/4))
VARIANTS: list[tuple[str, bool, float]] = [
    ("baseline", False, 0.0),
    ("fuse", True, 0.0),
    ("fuse_mild", True, 0.5),
]


def _fused(cosine: float, g: Grade | None, floor: float) -> float:
    nr = ((g.relevance if g else 0) + 2) / 4.0
    return cosine * (floor + (1.0 - floor) * nr)


def committed_pool(
    store: Store, qvec: list[float], q: str
) -> tuple[dict[str, PoolNode], list[Edge], FrontierSpec, int]:
    """The shipped committed retrieval (fast tier), shared by every variant."""
    n_pool, _, m, _ = TIERS["fast"]
    now = datetime.now()
    pool = hybrid_pool(store, qvec, q, n_pool)
    fr = detect_frontier(
        [n.year for n in pool.values() if n.year is not None],
        now.year,
        now.month,
        m,
        0.4,
    )
    pool.update(frontier_pull(store, qvec, fr.frontier_year, want=60))
    _ = augment_with_ancestors(store, pool, qvec, max_add=120, min_cosine=0.35)
    edges = induce_subgraph(store, list(pool))
    return pool, edges, fr, m


def variant_landmarks(
    pool: dict[str, PoolNode],
    edges: list[Edge],
    fr: FrontierSpec,
    m: int,
    grades: dict[str, Grade],
    fuse: bool,
    floor: float,
) -> list[str]:
    rank_nodes = pool
    if fuse:
        rank_nodes = {}
        for a, n in pool.items():
            g = grades.get(a)
            if floor == 0.0 and g is not None and g.relevance <= -2:
                continue  # production self-exclusion (norm zeroes out anyway)
            rank_nodes[a] = PoolNode(
                n.arxiv_id, n.title, n.year, n.category, _fused(n.score, g, floor)
            )
    lms = rank_landmarks_ppr(
        rank_nodes, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year
    )
    return [lm.arxiv_id for lm in lms]


def run() -> None:
    keys = battery()
    gold = [k for k in keys if TOPICS[k].canonical]
    RESULTS.mkdir(parents=True, exist_ok=True)

    # stage 1: embed every topic once (nomic loaded once), keep pools on the CPU side.
    _free_router_vram()
    qvecs: dict[str, list[float]] = {}
    for key in keys:
        qvecs[key] = embed_query(TOPICS[key].query, mode="asym")
    free_model()

    # stage 2: retrieve + grade (production reader_grade, cache-amortized) + rank variants.
    import hashlib  # noqa: PLC0415

    sets: dict[str, dict[str, list[str]]] = {v[0]: {} for v in VARIANTS}
    all_grades: dict[str, dict[str, Grade]] = {}
    for key in keys:
        q = TOPICS[key].query
        store = Store(PG_DSN, emb_space="asym")
        try:
            pool, edges, fr, m = committed_pool(store, qvecs[key], q)
            indeg: dict[str, int] = {}
            for e in edges:
                indeg[e.dst] = indeg.get(e.dst, 0) + 1
            cand = candidates(pool, indeg, m)
            qhash = hashlib.sha1(q.encode()).hexdigest()[:12]
            abstracts = store.abstracts(cand)
            grades = asyncio.run(grade_many(q, qhash, pool, cand, abstracts))
        finally:
            store.close()
        all_grades[key] = grades
        for name, fuse, floor in VARIANTS:
            sets[name][key] = variant_landmarks(pool, edges, fr, m, grades, fuse, floor)
        n_bad = sum(1 for g in grades.values() if g.relevance <= -2)
        print(
            f"[{key}] graded {len(grades)}/{len(cand)} ({n_bad} at -2) · "
            + " ".join(f"{n}={len(sets[n][key])}" for n, _, _ in VARIANTS),
            flush=True,
        )

    # stage 3: score. Labels for committed landmarks come from the SAME grade cache; any
    # landmark that entered ungraded (outside the candidate set) counts as unlabeled.
    def rates(name: str) -> tuple[float, float, Counter[str]]:
        per_topic: list[float] = []
        comp: Counter[str] = Counter()
        n_lab = 0
        for k in keys:
            labs = [all_grades[k][a].role for a in sets[name][k] if a in all_grades[k]]
            labs = [r for r in labs if r in LABELS]
            comp.update(labs)
            n_lab += len(labs)
            if labs:
                per_topic.append(1 - labs.count("unrelated") / len(labs))
        rel = round(sum(per_topic) / len(per_topic), 3) if per_topic else 0.0
        unrel = round(comp["unrelated"] / n_lab, 3) if n_lab else 0.0
        return rel, unrel, comp

    def recall(name: str) -> tuple[float, float]:
        lmr: list[float] = []
        spr: list[float] = []
        for k in gold:
            chosen = {a.lower() for a in sets[name][k]}
            canon = {c.lower() for c in TOPICS[k].canonical}
            spine = {s.lower() for s in TOPICS[k].spine}
            lmr.append(len(canon & chosen) / len(canon) if canon else 0.0)
            spr.append(len(spine & chosen) / len(spine) if spine else 0.0)
        return round(sum(lmr) / len(lmr), 3), round(sum(spr) / len(spr), 3)

    report: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for name, fuse, floor in VARIANTS:
        rel, unrel, comp = rates(name)
        lm_rec, sp_rec = recall(name)
        total = sum(comp.values()) or 1
        report.append(
            {
                "variant": name,
                "fuse": fuse,
                "norm_floor": floor,
                "relevance_rate_27": rel,
                "unrelated_frac_27": unrel,
                "landmark_recall_gold3": lm_rec,
                "spine_recall_gold3": sp_rec,
                **{f"frac_{r}": round(comp[r] / total, 3) for r in LABELS},
            }
        )

    _ = (RESULTS / "metrics.json").write_text(json.dumps(report, indent=1))
    cols = [
        "variant",
        "relevance_rate_27",
        "unrelated_frac_27",
        "landmark_recall_gold3",
        "spine_recall_gold3",
        "frac_foundational",
        "frac_core",
        "frac_frontier",
        "frac_adjacent",
        "frac_survey",
        "frac_unrelated",
    ]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in report:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n")
    bar_chart(
        report,
        "variant",
        [
            ("relevance_rate_27", "Relevance rate (27, same-grader caveat)"),
            ("landmark_recall_gold3", "Landmark recall (3 gold)"),
            ("spine_recall_gold3", "Spine recall (3 gold)"),
            ("unrelated_frac_27", "Unrelated fraction (lower better)"),
        ],
        RESULTS / "ablation.png",
        title="Reader relevance fusion — cosine x norm(rel) ranking vs cosine-only",
    )
    print("\n" + "\n".join(md), flush=True)


if __name__ == "__main__":
    run()
