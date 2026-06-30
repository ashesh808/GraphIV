"""experiment 03-07 (phase 2) — orthogonal axes on the adjacency_list winner.

Phase 1 settled the STRUCTURE axis (adjacency_list wins, modestly). Phase 2 layers the other axes
onto that winner and re-judges vs the same flat_list baseline:
  adj_roles            : nodes tagged [foundational/core/frontier/peripheral] (from the exp-15 cache).
  adj_extracted        : per-node content = full-text extracted schema fields (not the abstract).
  adj_alias            : nodes labelled [D1].. + an id table (cite the arXiv id from the table).
  adj_roles_extracted  : roles + extracted together (the likely production digest).

Same cache (results/runs/cache.db) so the flat_list baseline + adjacency_list reports are reused;
roles come free from 02-02's judge cache; extraction is cached in extract_cache.db. Judged
the same two ways: absolute 4-axis + order-debiased pairwise vs flat_list. Writes
results/metrics_phase2.{json,md} + ablation_phase2.png.

    uv run python experiments/03-generation/03-07-graph-representation/run.py --phase2
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir
_REPO = _HERE.parents[4]  # code -> NN-slug -> 03-generation -> experiments -> repo
for _p in (
    str(_REPO / "experiments"),
    str(_REPO / "phases"),
    str(_REPO / "phases" / "phase-6" / "components"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _harness.judge import judge_pairwise, judge_report  # noqa: E402
from _harness.topics import TOPICS, deep_panel  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

from _common import PG_DSN  # noqa: E402
from extract import extract_many  # noqa: E402
from llm import NO_THINK, chat_sync  # noqa: E402
from narrate import check_citations  # noqa: E402
from pagerank import rank_landmarks_ppr  # noqa: E402
from pipeline import TIERS, _free_router_vram  # noqa: E402
from recency import detect_frontier  # noqa: E402
from retrieval_hybrid import hybrid_pool  # noqa: E402
from retrieval_refined import frontier_pull  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from schema import propose_schema  # noqa: E402
from subgraph import Edge, Landmark, augment_with_ancestors, induce_subgraph  # noqa: E402  # fmt: skip
from store import Store  # noqa: E402

HERE = _EXP
NARRATOR = "Gemma-4-26B-Code"
BASELINE = "flat_list"
CONFIGS = ["adj_roles", "adj_extracted", "adj_alias", "adj_roles_extracted"]
ROWS = ["flat_list", "adjacency_list", *CONFIGS]
JUDGE_CACHE = (
    _REPO
    / "experiments"
    / "02-retrieval"
    / "02-02-relevance-judge"
    / "cache"
    / "judge_cache.db"
)
CACHE = HERE / "results" / "runs" / "cache.db"

_SYS = (
    "You are a research analyst writing a thorough, chronological literature review answering the "
    "user's question, grounded ONLY in the provided GRAPH of papers. Nodes are papers (arXiv id, "
    "year, title, content); directed edges are typed citations (extends/uses/compares/critiques/"
    "motivates/background; the edge points citing -> cited).\n"
    "- Tell the development as a story: origins -> key advances -> current frontier, inferring "
    "order from the years and the citation edges.\n"
    "- For every claim cite the paper as arXiv:<id>. Use the per-node content for specifics. Never "
    "invent an id or a fact not in the graph.\n"
    "- Use the edges to connect papers (what builds on what) and to surface tensions/open problems "
    "(compare/critique/motivate edges). Organize with headers; be specific."
)
_FMT = {
    "adj_roles": "Node table (each paper tagged [foundational/core/frontier/peripheral]) + adjacency list by intent.",
    "adj_extracted": "Node table (each paper has extracted fields) + adjacency list by intent.",
    "adj_alias": "Papers labelled [D1].. with arXiv ids in the node table; CITE THE ARXIV ID. Node table + adjacency list by intent.",
    "adj_roles_extracted": "Node table (role tag + extracted fields per paper) + adjacency list by intent.",
}


def retrieve(
    store: Store, qvec: list[float], q: str
) -> tuple[list[Landmark], list[Edge]]:
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
    edges = induce_subgraph(store, list(pool))
    lms = rank_landmarks_ppr(
        pool, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year
    )
    keep = {lm.arxiv_id for lm in lms}
    return lms, [e for e in edges if e.src in keep and e.dst in keep]


def roles_for(topic: str, aids: list[str]) -> dict[str, str]:
    if not JUDGE_CACHE.exists():
        return {}
    conn = sqlite3.connect(JUDGE_CACHE)
    rows: list[tuple[str, str]] = conn.execute(
        "SELECT arxiv_id, label FROM judge WHERE topic=?", (topic,)
    ).fetchall()
    conn.close()
    m = {a: lab for a, lab in rows}
    return {a: m.get(a, "") for a in aids}


def adj_encode(
    lms: list[Landmark],
    edges: list[Edge],
    content: dict[str, str],
    roles: dict[str, str] | None,
    alias: bool,
) -> str:
    nodes = sorted(lms, key=lambda lm: (lm.year or 0, lm.arxiv_id))
    al = {lm.arxiv_id: f"D{i + 1}" for i, lm in enumerate(nodes)}

    def ref(a: str) -> str:
        return al[a] if alias else f"arXiv:{a}"

    out: list[str] = ["NODES:"]
    for lm in nodes:
        a = lm.arxiv_id
        yr = lm.year if lm.year is not None else "?"
        role = f" [{roles[a]}]" if roles and roles.get(a) else ""
        idp = f"{al[a]} = arXiv:{a}" if alias else f"arXiv:{a}"
        out.append(f'{idp} ({yr}){role} "{lm.title}" :: {(content.get(a) or "")[:280]}')
    out += ["", "ADJACENCY (each paper -> papers it cites, grouped by intent):"]
    for lm in nodes:
        a = lm.arxiv_id
        grp: dict[str, list[str]] = defaultdict(list)
        for e in edges:
            if e.src == a:
                grp[e.intent or "cites"].append(ref(e.dst))
        parts = [f"{k}[{', '.join(v)}]" for k, v in grp.items()]
        out.append(f"{ref(a)}: {' '.join(parts) or '(no out-citations in-graph)'}")
    return "\n".join(out)


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(CACHE)


def run(_use_cache: bool = True) -> None:
    keys = [k for k in sys.argv[1:] if k in TOPICS] or deep_panel()
    out = HERE / "results"

    # stage 1: retrieve (nomic once) -> lms/edges/abstracts/roles per topic.
    data: dict[str, dict[str, Any]] = {}
    _free_router_vram()
    for key in keys:
        q = TOPICS[key].query
        qv = embed_query(q, mode="asym")
        store = Store(PG_DSN, emb_space="asym")
        try:
            lms, edges = retrieve(store, qv, q)
            absd = store.abstracts([lm.arxiv_id for lm in lms])
        finally:
            store.close()
        aids = [lm.arxiv_id for lm in lms]
        data[key] = {
            "lms": lms,
            "edges": edges,
            "abs": absd,
            "roles": roles_for(key, aids),
            "pool": set(aids),
        }
        print(
            f"[retrieve] {key}: {len(lms)} nodes {len(edges)} edges "
            f"(roles cached: {sum(1 for a in aids if data[key]['roles'].get(a))})",
            flush=True,
        )
    free_model()

    # stage 2: extraction (schema [26B-Code] + per-paper fields [26B]); cached in extract_cache.db.
    for key in keys:
        q = TOPICS[key].query
        d = data[key]
        lms: list[Landmark] = d["lms"]
        absd: dict[str, str] = d["abs"]
        samples = [
            f'{lm.title}\n{(absd.get(lm.arxiv_id) or "")[:500]}' for lm in lms[:6]
        ]
        sch = propose_schema(q, samples)
        ext = asyncio.run(
            extract_many([(lm.arxiv_id, lm.title) for lm in lms], sch, absd)
        )
        d["ext"] = {
            a: "; ".join(f"{k}: {v}" for k, v in f.items() if v and v.lower() != "n/a")
            for a, f in ext.items()
        }
        print(
            f"[extract] {key}: {len(ext)}/{len(lms)} papers, schema={sch.names()}",
            flush=True,
        )

    # build the 4 digests per topic.
    digests: dict[str, dict[str, str]] = {}
    for key in keys:
        d = data[key]
        lms, edges = d["lms"], d["edges"]
        absd, roles, ext = d["abs"], d["roles"], d["ext"]
        digests[key] = {
            "adj_roles": adj_encode(lms, edges, absd, roles, False),
            "adj_extracted": adj_encode(lms, edges, ext, None, False),
            "adj_alias": adj_encode(lms, edges, absd, None, True),
            "adj_roles_extracted": adj_encode(lms, edges, ext, roles, False),
        }

    conn = _conn()
    # stage 3: compose (26B-Code).
    for key in keys:
        for cfg in CONFIGS:
            if conn.execute(
                "SELECT 1 FROM compose WHERE topic=? AND rep=?", (key, cfg)
            ).fetchone():
                continue
            user = (
                f"Write the literature review answering: {TOPICS[key].query}\n\n"
                f"FORMAT: {_FMT[cfg]}\n\nGRAPH:\n{digests[key][cfg]}"
            )
            rep_txt, ptok, _ = chat_sync(
                NARRATOR, _SYS, user, 0.4, 3500, extra_body=NO_THINK
            )
            _ = conn.execute(
                "INSERT INTO compose VALUES (?,?,?,?)", (key, cfg, rep_txt, ptok)
            )
            conn.commit()
            print(
                f"[compose] {key}/{cfg}: {len(rep_txt)}c prompt={ptok}tok", flush=True
            )

    def report_of(key: str, rep: str) -> str:
        row: tuple[str] = conn.execute(
            "SELECT report FROM compose WHERE topic=? AND rep=?", (key, rep)
        ).fetchone()
        return row[0]

    # stage 4: judge absolute + pairwise vs flat_list (26B).
    for key in keys:
        canon = list(TOPICS[key].canonical)
        for cfg in CONFIGS:
            if not conn.execute(
                "SELECT 1 FROM judged WHERE topic=? AND rep=?", (key, cfg)
            ).fetchone():
                txt = report_of(key, cfg)
                grounded, off = check_citations(txt, data[key]["pool"])
                j = judge_report(TOPICS[key].query, txt, canon, passes=1)
                j["grounded_frac"] = round(
                    len(grounded) / max(1, len(grounded) + len(off)), 3
                )
                _ = conn.execute(
                    "INSERT INTO judged VALUES (?,?,?)", (key, cfg, json.dumps(j))
                )
                conn.commit()
            if not conn.execute(
                "SELECT 1 FROM paired WHERE topic=? AND rep=?", (key, cfg)
            ).fetchone():
                pj = judge_pairwise(
                    TOPICS[key].query,
                    report_of(key, cfg),
                    report_of(key, BASELINE),
                    canon,
                )
                _ = conn.execute(
                    "INSERT INTO paired VALUES (?,?,?)", (key, cfg, json.dumps(pj))
                )
                conn.commit()
                print(f"[judge] {key}/{cfg}: pairwise vs {BASELINE} = {pj}", flush=True)

    # aggregate the 6 rows of interest (phase-1 flat_list + adjacency_list reused from cache).
    ptoks = {
        (k, r): int(p)
        for k, r, p in conn.execute("SELECT topic, rep, ptok FROM compose")
    }
    rows: list[dict[str, Any]] = []
    for rep in ROWS:
        js = [
            json.loads(
                conn.execute(
                    "SELECT js FROM judged WHERE topic=? AND rep=?", (k, rep)
                ).fetchone()[0]
            )
            for k in keys
        ]
        agg: dict[str, Any] = {"rep": rep, "n": len(js)}
        for ax in (
            "grounding",
            "coverage",
            "lineage",
            "coherence",
            "overall",
            "grounded_frac",
        ):
            agg[ax] = round(sum(float(j[ax]) for j in js) / len(js), 3)
        agg["prompt_tokens"] = round(sum(ptoks[(k, rep)] for k in keys) / len(keys))
        if rep == BASELINE:
            agg["pair_net"] = 0.0
        else:
            pjs = [
                json.loads(
                    conn.execute(
                        "SELECT js FROM paired WHERE topic=? AND rep=?", (k, rep)
                    ).fetchone()[0]
                )
                for k in keys
            ]
            w = sum(1 for p in pjs if p["overall"] == "A")
            loss = sum(1 for p in pjs if p["overall"] == "B")
            agg["pair_net"] = round((w - loss) / len(pjs), 3)
            agg["pair_wtl"] = f"{w}/{len(pjs) - w - loss}/{loss}"
        rows.append(agg)
    conn.close()

    (out / "metrics_phase2.json").write_text(json.dumps(rows, indent=1))
    cols = [
        "rep",
        "n",
        "overall",
        "grounding",
        "coverage",
        "lineage",
        "coherence",
        "grounded_frac",
        "prompt_tokens",
        "pair_net",
        "pair_wtl",
    ]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        md.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    (out / "metrics_phase2.md").write_text("\n".join(md) + "\n")
    bar_chart(
        rows,
        "rep",
        [
            ("overall", "Judge overall (1-5)"),
            ("lineage", "Lineage (1-5)"),
            ("pair_net", "Pairwise net vs flat_list"),
            ("prompt_tokens", "Prompt tokens"),
        ],
        out / "ablation_phase2.png",
        title=f"Phase 2 — axes on adjacency_list — {len(keys)} topics (baseline=flat_list)",
    )
    print("\n" + "\n".join(md), flush=True)


if __name__ == "__main__":
    run()
