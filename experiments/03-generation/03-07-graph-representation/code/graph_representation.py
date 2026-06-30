"""experiment 03-07 — Graph representation: how to serialize the citation subgraph into the LLM.

Not a solved problem — each encoding trades token cost, parseability, structure fidelity, and
narrative bias. Same subgraph, same per-node content (id/year/title/abstract held CONSTANT); only
the STRUCTURE encoding varies. Six encodings of the nodes + typed directed edges:
  flat_list      : papers chronological, each with incident relations inline (≈ the current digest).
  adjacency_list : a node table + per-paper out-neighbours grouped by intent.
  dot            : a node table + a Graphviz `digraph { A -> B [type=...] }` block.
  subtree        : the lineage tree (parent = most-recent older cited) nested + non-tree edges.
  json           : {"nodes":[...], "edges":[...]} structured object.
  matrix         : a node table (P0..Pn) + an adjacency MATRIX of edge-type initials.

Each digest is composed by Gemma-4-26B-Code, then scored two ways: the absolute 4-axis judge
(grounding/coverage/lineage/coherence, @T=0) AND an order-debiased PAIRWISE judge vs the flat_list
baseline (sharper than the coarse integer scale). Plus grounded-citation rate and REAL prompt-token
cost. No roles / no era-spine overlays here — this isolates the graph-encoding axis. Naming
(id vs alias), per-node content (abstract vs extracted fields), and overlays (roles/era/spine) are
the follow-on axes to layer in via the same cache (see README).

    uv run python experiments/03-generation/03-07-graph-representation/run.py            # deep-panel (8)
    uv run python experiments/03-generation/03-07-graph-representation/run.py diffusion  # one topic
"""

from __future__ import annotations

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
from llm import NO_THINK, chat_sync  # noqa: E402
from narrate import check_citations  # noqa: E402
from pagerank import rank_landmarks_ppr  # noqa: E402
from pipeline import TIERS, _free_router_vram  # noqa: E402
from recency import detect_frontier  # noqa: E402
from retrieval_hybrid import hybrid_pool  # noqa: E402
from retrieval_refined import frontier_pull  # noqa: E402
from retrieve import embed_query, free_model  # noqa: E402
from subgraph import Edge, Landmark, augment_with_ancestors, induce_subgraph  # noqa: E402  # fmt: skip
from store import Store  # noqa: E402

HERE = _EXP
NARRATOR = "Gemma-4-26B-Code"
BASELINE = "flat_list"
REPS = ["flat_list", "adjacency_list", "dot", "subtree", "json", "matrix"]
INTENT_INI = {
    "extends": "E",
    "uses": "U",
    "compares": "C",
    "critiques": "K",
    "motivates": "M",
    "background": "B",
}

_SYS = (
    "You are a research analyst writing a thorough, chronological literature review answering the "
    "user's question, grounded ONLY in the provided GRAPH of papers. Nodes are papers (arXiv id, "
    "year, title, abstract); directed edges are typed citations (extends/uses/compares/critiques/"
    "motivates/background; the edge points citing -> cited).\n"
    "- Tell the development as a story: origins -> key advances -> current frontier, inferring "
    "order from the years and the citation edges.\n"
    "- For every claim cite the paper as arXiv:<id>. Use the abstracts for specifics. Never invent "
    "an id or a fact not in the graph.\n"
    "- Use the edges to connect papers (what builds on what) and to surface tensions/open problems "
    "(compare/critique/motivate edges). Organize with headers; be specific."
)
_FMT_HINT = {
    "flat_list": "The graph is a chronological list of papers; each lists its outgoing/incoming citations.",
    "adjacency_list": "The graph is a node table plus an adjacency list (each paper -> the papers it cites, by intent).",
    "dot": "The graph is a node table plus a Graphviz DOT digraph; 'A -> B' means A cites B.",
    "subtree": "The graph is a nested lineage tree (a paper is placed under the paper it cites) plus non-tree citations.",
    "json": "The graph is a JSON object with a 'nodes' array and a typed 'edges' array.",
    "matrix": "The graph is a node table (P0..Pn) plus an adjacency matrix; row cites col, cell = edge-type initial.",
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


def _yr(lm: Landmark) -> str:
    return str(lm.year) if lm.year is not None else "?"


def _parents(lms: list[Landmark], edges: list[Edge]) -> dict[str, str | None]:
    by = {lm.arxiv_id: lm for lm in lms}
    indeg: dict[str, int] = defaultdict(int)
    cites: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e.src in by and e.dst in by:
            cites[e.src].append(e.dst)
            indeg[e.dst] += 1
    parent: dict[str, str | None] = {}
    for a, lm in by.items():
        ya = lm.year or 0
        cands = [d for d in cites[a] if (by[d].year or 0) <= ya and d != a]
        parent[a] = (
            max(cands, key=lambda d: ((by[d].year or 0), indeg[d])) if cands else None
        )
    for a in list(parent):
        seen: set[str] = set()
        cur: str | None = a
        while cur is not None:
            if cur in seen:
                parent[a] = None
                break
            seen.add(cur)
            cur = parent[cur]
    return parent


def enc(rep: str, lms: list[Landmark], edges: list[Edge], absd: dict[str, str]) -> str:
    nodes = sorted(lms, key=lambda lm: (lm.year or 0, lm.arxiv_id))
    ids = [lm.arxiv_id for lm in nodes]
    by = {lm.arxiv_id: lm for lm in nodes}

    def snip(a: str) -> str:
        return (absd.get(a) or "").strip().replace("\n", " ")[:280]

    def head(lm: Landmark) -> str:
        return f'arXiv:{lm.arxiv_id} ({_yr(lm)}) "{lm.title}"'

    if rep == "flat_list":
        out: list[str] = ["PAPERS (chronological):"]
        for lm in nodes:
            a = lm.arxiv_id
            outs = [
                f"{e.intent or 'cites'}->arXiv:{e.dst}" for e in edges if e.src == a
            ]
            ins = [
                f"arXiv:{e.src} {e.intent or 'cites'}->" for e in edges if e.dst == a
            ]
            out += [
                head(lm),
                f"  abstract: {snip(a)}",
                f"  cites: {'; '.join(outs) or '(none)'}",
                f"  cited-by: {'; '.join(ins) or '(none)'}",
            ]
        return "\n".join(out)

    if rep == "adjacency_list":
        out = ["NODES:"] + [f"{head(lm)} :: {snip(lm.arxiv_id)}" for lm in nodes]
        out += ["", "ADJACENCY (each paper -> papers it cites, grouped by intent):"]
        for a in ids:
            grp: dict[str, list[str]] = defaultdict(list)
            for e in edges:
                if e.src == a:
                    grp[e.intent or "cites"].append(e.dst)
            parts = [f"{k}[{', '.join(v)}]" for k, v in grp.items()]
            out.append(f"arXiv:{a}: {' '.join(parts) or '(no out-citations in-graph)'}")
        return "\n".join(out)

    if rep == "dot":
        out = ["NODES:"] + [f"{head(lm)} :: {snip(lm.arxiv_id)}" for lm in nodes]
        out += ["", "DOT (digraph; A -> B means A cites B):", "digraph G {"]
        out += [
            f'  "{e.src}" -> "{e.dst}" [type={e.intent or "cites"}];' for e in edges
        ]
        out.append("}")
        return "\n".join(out)

    if rep == "subtree":
        parent = _parents(nodes, edges)
        kids: dict[str, list[str]] = defaultdict(list)
        for a, p in parent.items():
            if p is not None:
                kids[p].append(a)
        roots = [a for a in ids if parent.get(a) is None]
        tree_e = {(a, p) for a, p in parent.items() if p is not None}
        out = [
            "LINEAGE TREE (a paper is nested under the paper it cites; deeper = newer):"
        ]

        def walk(a: str, d: int) -> None:
            out.append(f"{'  ' * d}- {head(by[a])} :: {snip(a)}")
            for c in sorted(kids.get(a, []), key=lambda c: (by[c].year or 0, c)):
                walk(c, d + 1)

        for r in sorted(roots, key=lambda r: (by[r].year or 0, r)):
            walk(r, 0)
        out += ["", "NON-TREE CITATIONS (edges not shown by the nesting):"]
        extra = [
            f"  arXiv:{e.src} -> arXiv:{e.dst} [{e.intent or 'cites'}]"
            for e in edges
            if (e.src, e.dst) not in tree_e
        ]
        out += extra or ["  (none)"]
        return "\n".join(out)

    if rep == "json":
        obj = {
            "nodes": [
                {
                    "id": lm.arxiv_id,
                    "year": lm.year,
                    "title": lm.title,
                    "abstract": snip(lm.arxiv_id),
                }
                for lm in nodes
            ],
            "edges": [
                {"src": e.src, "dst": e.dst, "intent": e.intent, "polarity": e.polarity}
                for e in edges
            ],
        }
        return json.dumps(obj, indent=1)

    pk = {a: f"P{i}" for i, a in enumerate(ids)}  # matrix
    cell: dict[tuple[str, str], str] = {}
    for e in edges:
        if e.src in pk and e.dst in pk:
            cell[(e.src, e.dst)] = INTENT_INI.get(e.intent or "", "x")
    out = ["NODES (Pk = arXiv id):"]
    out += [f"{pk[lm.arxiv_id]} = {head(lm)} :: {snip(lm.arxiv_id)}" for lm in nodes]
    out += [
        "",
        "ADJACENCY MATRIX (row cites col; E=extends U=uses C=compares K=critiques "
        "M=motivates B=background, .=none):",
        "    " + " ".join(f"{pk[a]:>3}" for a in ids),
    ]
    for r in ids:
        out.append(
            f"{pk[r]:>3} " + " ".join(f"{cell.get((r, c), '.'):>3}" for c in ids)
        )
    return "\n".join(out)


def _cache() -> sqlite3.Connection:
    (HERE / "results" / "runs").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(HERE / "results" / "runs" / "cache.db")
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS compose (topic TEXT, rep TEXT, report TEXT, "
        "ptok INT, PRIMARY KEY(topic, rep))"
    )
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS judged (topic TEXT, rep TEXT, js TEXT, "
        "PRIMARY KEY(topic, rep))"
    )
    _ = conn.execute(
        "CREATE TABLE IF NOT EXISTS paired (topic TEXT, rep TEXT, js TEXT, "
        "PRIMARY KEY(topic, rep))"
    )
    conn.commit()
    return conn


def run(_use_cache: bool = True) -> None:
    keys = sys.argv[1:] or deep_panel()
    keys = [k for k in keys if k in TOPICS]
    out = HERE / "results"
    out.mkdir(parents=True, exist_ok=True)

    # stage 1: retrieve + build all digests (nomic once).
    digests: dict[str, dict[str, str]] = {}
    pools: dict[str, set[str]] = {}
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
        pools[key] = {lm.arxiv_id for lm in lms}
        digests[key] = {rep: enc(rep, lms, edges, absd) for rep in REPS}
        print(f"[retrieve] {key}: {len(lms)} nodes {len(edges)} edges", flush=True)
    free_model()

    conn = _cache()
    # stage 2a: compose (Gemma-4-26B-Code loaded).
    for key in keys:
        for rep in REPS:
            if conn.execute(
                "SELECT 1 FROM compose WHERE topic=? AND rep=?", (key, rep)
            ).fetchone():
                continue
            user = (
                f"Write the literature review answering: {TOPICS[key].query}\n\n"
                f"FORMAT: {_FMT_HINT[rep]}\n\nGRAPH:\n{digests[key][rep]}"
            )
            report, ptok, _ = chat_sync(
                NARRATOR, _SYS, user, 0.4, 3500, extra_body=NO_THINK
            )
            _ = conn.execute(
                "INSERT INTO compose VALUES (?,?,?,?)", (key, rep, report, ptok)
            )
            conn.commit()
            print(f"[compose] {key}/{rep}: {len(report)}c prompt={ptok}tok", flush=True)

    def report_of(key: str, rep: str) -> str:
        row: tuple[str] = conn.execute(
            "SELECT report FROM compose WHERE topic=? AND rep=?", (key, rep)
        ).fetchone()
        return row[0]

    # stage 2b: absolute judge (Gemma-4-26B loaded) + pairwise vs baseline.
    for key in keys:
        canon = list(TOPICS[key].canonical)
        for rep in REPS:
            if not conn.execute(
                "SELECT 1 FROM judged WHERE topic=? AND rep=?", (key, rep)
            ).fetchone():
                rep_txt = report_of(key, rep)
                grounded, off = check_citations(rep_txt, pools[key])
                j = judge_report(TOPICS[key].query, rep_txt, canon, passes=1)
                j["grounded_frac"] = round(
                    len(grounded) / max(1, len(grounded) + len(off)), 3
                )
                _ = conn.execute(
                    "INSERT INTO judged VALUES (?,?,?)", (key, rep, json.dumps(j))
                )
                conn.commit()
            if rep == BASELINE:
                continue
            if not conn.execute(
                "SELECT 1 FROM paired WHERE topic=? AND rep=?", (key, rep)
            ).fetchone():
                pj = judge_pairwise(
                    TOPICS[key].query,
                    report_of(key, rep),
                    report_of(key, BASELINE),
                    canon,
                )
                _ = conn.execute(
                    "INSERT INTO paired VALUES (?,?,?)", (key, rep, json.dumps(pj))
                )
                conn.commit()
                print(f"[judge] {key}/{rep}: pairwise vs {BASELINE} = {pj}", flush=True)

    # aggregate.
    ptoks = {
        (k, r): int(p)
        for k, r, p in conn.execute("SELECT topic, rep, ptok FROM compose")
    }
    rows: list[dict[str, Any]] = []
    for rep in REPS:
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
        if rep != BASELINE:  # pairwise net vs baseline on 'overall' (wins - losses)/n
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
            agg["pair_wins"] = w
            agg["pair_losses"] = loss
            agg["pair_net"] = round((w - loss) / len(pjs), 3)
        else:
            agg["pair_wins"] = agg["pair_losses"] = 0
            agg["pair_net"] = 0.0
        rows.append(agg)
    conn.close()

    (out / "metrics.json").write_text(json.dumps(rows, indent=1))
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
        "pair_wins",
        "pair_losses",
        "pair_net",
    ]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    (out / "metrics.md").write_text("\n".join(md) + "\n")
    bar_chart(
        rows,
        "rep",
        [
            ("overall", "Judge overall (1-5)"),
            ("lineage", "Lineage (1-5)"),
            ("pair_net", "Pairwise net vs flat_list"),
            ("prompt_tokens", "Prompt tokens (lower better)"),
        ],
        out / "ablation.png",
        title=f"Graph representation into the LLM — {len(keys)} topics (baseline=flat_list)",
    )
    print("\n" + "\n".join(md), flush=True)


if __name__ == "__main__":
    run()
