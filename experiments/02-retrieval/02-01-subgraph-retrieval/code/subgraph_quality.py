"""experiment 02-01 — subgraph retrieval quality (the retrieval step in isolation).

The committed subgraph-retrieval recipe (hybrid pool -> ancestor augmentation -> induce citation
subgraph -> Personalized-PageRank landmark ranking) is locked; this experiment measures HOW GOOD
it is at the one thing it does: recovering a field's canonical landmark papers as a bounded,
connected, on-topic citation subgraph. NO LLM, NO compose, NO judge — retrieval level only.

Per gold topic, over a single shared candidate pool, three Stage-4 selectors are scored:
  - induce  : the committed method — PPR-rank the pool to m landmarks.
  - pcst    : Prize-Collecting Steiner Tree on the top-m relevant nodes (G-Retriever, 2402.07630).
  - dsa_bfs : similarity-aware BFS from the top-cosine seeds (DynaGRAG, 2412.18644).
(pcst needs the `pcst_fast` wheel; run `uv run --with pcst_fast …` to include it, else it is skipped.)

Metrics (per topic, averaged per method):
  - pool_recall      : canonical found in the candidate POOL  (the retrieval CEILING).
  - landmark_recall  : canonical surfaced into the m LANDMARKS (the headline number).
  - spine_recall     : foundational-lineage ids surfaced into the landmarks.
  - connectivity     : largest-connected-component fraction of the chosen subgraph.
  - mean_cosine      : mean query-cosine of the chosen nodes (topical-drift proxy).

    uv run --with pcst_fast python experiments/02-retrieval/02-01-subgraph-retrieval/run.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, LiteralString, cast

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

from _harness.topics import TOPICS, GoldTopic  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

import numpy as np  # noqa: E402

from _common import PG_DSN  # noqa: E402
from pagerank import rank_landmarks_ppr  # noqa: E402
from pipeline import TIERS, _free_router_vram  # noqa: E402
from recency import FrontierSpec, detect_frontier  # noqa: E402
from retrieval_hybrid import hybrid_pool  # noqa: E402
from retrieval_refined import frontier_pull  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from store import Store  # noqa: E402
from subgraph import Edge, PoolNode, augment_with_ancestors, induce_subgraph  # noqa: E402  # fmt: skip

try:
    import pcst_fast  # noqa: F401  # pyright: ignore[reportMissingImports]

    HAVE_PCST: bool = True
except ImportError:
    HAVE_PCST = False

RESULTS = _EXP / "results"
GOLD = [k for k in TOPICS if TOPICS[k].canonical]  # only topics with a canonical set
SEEDS, BFS_DEPTH, FANOUT, GATE = 6, 4, 8, 0.45


# --- shared candidate pool ---------------------------------------------------
def candidate(
    store: Store, qvec: list[float], q: str
) -> tuple[dict[str, PoolNode], FrontierSpec, int]:
    """The committed Stage-1..3 pool: hybrid pool + frontier pull + ancestor augmentation."""
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
    _ = augment_with_ancestors(store, pool, qvec, max_add=120)
    return pool, fr, m


def cosine(store: Store, qvec: list[float], ids: list[str]) -> dict[str, float]:
    """True query-cosine per pool id (the shared PCST/BFS prize), one round-trip."""
    v = "[" + ",".join(repr(float(x)) for x in qvec) + "]"
    q = (  # noqa: S608  # emb_col/emb_table are internal constants, not user input
        f"SELECT arxiv_id, 1 - ({store.emb_col} <=> %s::halfvec) "
        f"FROM {store.emb_table} WHERE arxiv_id = ANY(%s)"
    )
    rows: list[tuple[Any, ...]] = store.conn.execute(
        cast(LiteralString, q), (v, ids)
    ).fetchall()
    return {str(a): float(s) for a, s in rows}


# --- the three Stage-4 selectors ---------------------------------------------
def m_induce(
    pool: dict[str, PoolNode], edges: list[Edge], m: int, fr: FrontierSpec
) -> list[str]:
    lms = rank_landmarks_ppr(
        pool, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year
    )
    return [lm.arxiv_id for lm in lms]


def m_pcst(
    pool: dict[str, PoolNode], edges: list[Edge], prize: dict[str, float], m: int
) -> list[str]:
    import pcst_fast  # pyright: ignore[reportMissingImports]

    ids = list(pool)
    idx = {a: i for i, a in enumerate(ids)}
    e = np.array(
        [[idx[x.src], idx[x.dst]] for x in edges if x.src in idx and x.dst in idx],
        dtype=np.int64,
    )
    if len(e) == 0:
        return ids[: min(m, len(ids))]
    pr_raw = np.array([max(0.0, prize.get(a, 0.0)) for a in ids], dtype=float)
    thresh = float(
        np.sort(pr_raw)[::-1][min(m, len(pr_raw) - 1)]
    )  # prize only the top-m relevant
    pr = np.where(pr_raw > thresh, pr_raw, 0.0)
    pos = pr_raw[pr_raw > thresh]
    cost = float(0.4 * (pos.mean() if len(pos) else 0.3))
    costs = np.full(len(e), cost, dtype=float)
    verts, _ = pcst_fast.pcst_fast(e, pr, costs, -1, 1, "gw", 0)
    return [ids[int(i)] for i in verts]


def m_dsa_bfs(
    pool: dict[str, PoolNode], edges: list[Edge], prize: dict[str, float], m: int
) -> list[str]:
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        adj[e.src].append(e.dst)
        adj[e.dst].append(e.src)
    seeds = [
        a for a in sorted(prize, key=lambda a: -prize.get(a, 0.0))[:SEEDS] if a in pool
    ]
    visited: set[str] = set(seeds)
    dq: deque[tuple[str, int]] = deque((s, 0) for s in seeds)
    while dq and len(visited) < m:
        u, d = dq.popleft()
        if d >= BFS_DEPTH:
            continue
        nbrs = sorted(set(adj[u]) - visited, key=lambda a: -prize.get(a, 0.0))
        for a in [n for n in nbrs if prize.get(n, 0.0) >= GATE][:FANOUT]:
            visited.add(a)
            dq.append((a, d + 1))
            if len(visited) >= m:
                break
    return list(visited)


# --- metrics -----------------------------------------------------------------
def largest_cc_frac(chosen: list[str], edges: list[Edge]) -> float:
    """Fraction of chosen nodes in the largest connected component of the induced sub-edges."""
    cs = set(chosen)
    if not cs:
        return 0.0
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        if e.src in cs and e.dst in cs:
            adj[e.src].add(e.dst)
            adj[e.dst].add(e.src)
    seen: set[str] = set()
    best = 0
    for s in cs:
        if s in seen:
            continue
        comp: set[str] = set()
        st = [s]
        while st:
            u = st.pop()
            if u in comp:
                continue
            comp.add(u)
            st.extend(adj[u] - comp)
        seen |= comp
        best = max(best, len(comp))
    return round(best / len(cs), 3)


def score(
    chosen: list[str],
    pool_ids: set[str],
    edges: list[Edge],
    prize: dict[str, float],
    topic: GoldTopic,
) -> dict[str, Any]:
    cs = {a.lower() for a in chosen}
    pl = {a.lower() for a in pool_ids}
    canon = {c.lower() for c in topic.canonical}
    spine = {s.lower() for s in topic.spine}
    sub = [e for e in edges if e.src in set(chosen) and e.dst in set(chosen)]
    return {
        "n_landmarks": len(chosen),
        "n_edges": len(sub),
        "pool_recall": round(len(canon & pl) / len(canon), 3) if canon else None,
        "landmark_recall": round(len(canon & cs) / len(canon), 3) if canon else None,
        "spine_recall": round(len(spine & cs) / len(spine), 3) if spine else None,
        "connectivity": largest_cc_frac(chosen, edges),
        "mean_cosine": (
            round(float(np.mean([prize.get(a, 0.0) for a in chosen])), 3)
            if chosen
            else 0.0
        ),
    }


# --- latex tables (for report/report.tex) ------------------------------------
def _write_tex(agg: list[dict[str, Any]]) -> None:
    committed = next(a for a in agg if a["method"] == "induce")
    macros = [
        f"\\newcommand{{\\rcLandmark}}{{{committed['landmark_recall']}}}",
        f"\\newcommand{{\\rcPool}}{{{committed['pool_recall']}}}",
        f"\\newcommand{{\\rcSpine}}{{{committed['spine_recall']}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n")
    show = [
        ("pool_recall", "pool rec."),
        ("landmark_recall", "landmark rec."),
        ("spine_recall", "spine rec."),
        ("connectivity", "conn."),
        ("mean_cosine", "cosine"),
    ]
    lines = [
        "\\begin{tabular}{lrrrrr}",
        "\\toprule",
        "method & " + " & ".join(c[1] for c in show) + " \\\\",
        "\\midrule",
    ]
    for a in agg:
        name = a["method"].replace("_", r"\_") + (
            " (committed)" if a["method"] == "induce" else ""
        )
        lines.append(
            name + " & " + " & ".join(str(a.get(c[0], "")) for c in show) + " \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(lines) + "\n")


# --- driver ------------------------------------------------------------------
def run(_use_cache: bool = True) -> None:
    methods = ["induce"] + (["pcst"] if HAVE_PCST else []) + ["dsa_bfs"]
    if not HAVE_PCST:
        print(
            "[02-01] pcst_fast not installed — skipping the PCST baseline "
            "(run with `uv run --with pcst_fast …` to include it)",
            flush=True,
        )
    _free_router_vram()
    raw: list[dict[str, Any]] = []
    for key in GOLD:
        topic = TOPICS[key]
        qv = embed_query(
            topic.query, mode="asym"
        )  # committed: asymmetric space, raw query
        store = Store(PG_DSN, emb_space="asym")
        try:
            pool, fr, m = candidate(store, qv, topic.query)
            edges = induce_subgraph(store, list(pool))
            prize = cosine(store, qv, list(pool))
        finally:
            store.close()
        pool_ids = set(pool)
        print(f"[{key}] pool={len(pool)} edges={len(edges)}", flush=True)
        sel: dict[str, list[str]] = {"induce": m_induce(pool, edges, m, fr)}
        if HAVE_PCST:
            sel["pcst"] = m_pcst(pool, edges, prize, m)
        sel["dsa_bfs"] = m_dsa_bfs(pool, edges, prize, m)
        for method in methods:
            chosen = sel[method]
            row = {
                "topic": key,
                "method": method,
                **score(chosen, pool_ids, edges, prize, topic),
            }
            raw.append(row)
            print(
                f"   {method:8s} lm_rec={row['landmark_recall']} pool_rec={row['pool_recall']} "
                f"spine={row['spine_recall']} conn={row['connectivity']} "
                f"cos={row['mean_cosine']}",
                flush=True,
            )
    free_model()

    # aggregate per method (mean over gold topics)
    keys = [
        "pool_recall",
        "landmark_recall",
        "spine_recall",
        "connectivity",
        "mean_cosine",
        "n_landmarks",
        "n_edges",
    ]
    agg: list[dict[str, Any]] = []
    for method in methods:
        rows = [r for r in raw if r["method"] == method]
        a: dict[str, Any] = {"method": method, "n_topics": len(rows)}
        for k in keys:
            vals = [r[k] for r in rows if r[k] is not None]
            a[k] = round(float(np.mean(vals)), 3) if vals else None
        agg.append(a)

    out = RESULTS
    out.mkdir(parents=True, exist_ok=True)
    _ = (out / "metrics_raw.json").write_text(json.dumps(raw, indent=1))
    _ = (out / "metrics.json").write_text(json.dumps(agg, indent=1))
    cols = ["method", "n_topics", *keys]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for a in agg:
        md.append("| " + " | ".join(str(a.get(c, "")) for c in cols) + " |")
    _ = (out / "metrics.md").write_text("\n".join(md) + "\n")
    _write_tex(agg)
    bar_chart(
        agg,
        "method",
        [
            ("landmark_recall", "Landmark recall (headline)"),
            ("pool_recall", "Pool recall (ceiling)"),
            ("spine_recall", "Spine recall"),
            ("connectivity", "Connectivity"),
        ],
        out / "ablation.png",
        title=f"Subgraph retrieval over {len(GOLD)} gold topics — committed=induce/PPR",
    )
    print(
        f"\n[done] {out}/metrics.md + ablation.png  ({len(GOLD)} gold topics)",
        flush=True,
    )


if __name__ == "__main__":
    run()
