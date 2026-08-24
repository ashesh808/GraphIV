"""
Paper-list quality under a low cap, across four landmark sets

The pool and the digest are identical in every arm, so only the selected set differs
Metrics pair the direct counts with a compose judge and a pairwise comparison
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from _harness.digest import adjacency_digest  # noqa: E402
from _harness.judge import (  # noqa: E402  # fmt: skip
    ROLE_LABELS,
    judge_pairwise,
    judge_report,
    role_judge,
)
from _harness.retrieval import retrieve_subgraph  # noqa: E402
from _harness.topics import TOPICS, deep_panel  # noqa: E402
from _harness.viz import bar_chart  # noqa: E402

from graphiv.core.embed import embed_query, free_model
from graphiv.core.llm import NO_THINK, chat_sync
from graphiv.core.models import Edge, Landmark
from graphiv.core.store import Store
from graphiv.generate.extract import extract_many
from graphiv.generate.narrate import check_citations
from graphiv.generate.pipeline import _free_router_vram
from graphiv.generate.schema import propose_schema
from graphiv.retrieve.pagerank import rank_landmarks_ppr

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]

CACHE = _EXP / "cache"
RESULTS = _EXP / "results"
PG_DSN = f"host={_REPO}/.pg port=5433 dbname=arxivkg"
NARRATOR = "Gemma-4-26B-Code"
ARMS = ("fixed40", "gate40", "llm40", "llm_dyn")
GATE, CAND, CAP40, CAPDYN = 0.35, 100, 40, 60
TODAY = datetime.now().strftime("%Y-%m-%d")
ROLE_CACHE = (
    _REPO / "experiments" / "02-retrieval" / "02-02-relevance-judge" / "cache" / "judge_cache.db"
)

_SYS = (
    "Write a thorough chronological literature review answering the question, grounded ONLY in the "
    "provided GRAPH (papers + typed citation edges). Origins -> advances -> frontier; cite every "
    "claim as arXiv:<id>; use the per-node content for specifics; never invent. Use headers."
)


def _among(edges: list[Edge], ids: set[str]) -> list[Edge]:
    return [e for e in edges if e.src in ids and e.dst in ids]


def _role(conn: sqlite3.Connection, topic: str, lm: Landmark, abstract: str) -> str:
    row: tuple[str] | None = conn.execute(
        "SELECT label FROM judge WHERE topic=? AND arxiv_id=?", (topic, lm.arxiv_id)
    ).fetchone()
    if row is not None:
        return row[0]
    label = role_judge(
        f"(Today is {TODAY}.) {TOPICS[topic].query}",
        lm.arxiv_id,
        lm.title,
        lm.year,
        abstract,
    )
    _ = conn.execute("INSERT INTO judge VALUES (?,?,?,?)", (topic, lm.arxiv_id, label, "(selexp)"))
    conn.commit()
    return label


def _cache() -> sqlite3.Connection:
    CACHE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE / "cache.db")
    for ddl in (
        "CREATE TABLE IF NOT EXISTS compose (topic TEXT, arm TEXT, report TEXT, ptok INT, PRIMARY KEY(topic, arm))",
        "CREATE TABLE IF NOT EXISTS judged (topic TEXT, arm TEXT, js TEXT, PRIMARY KEY(topic, arm))",
        "CREATE TABLE IF NOT EXISTS paired (topic TEXT, arm TEXT, js TEXT, PRIMARY KEY(topic, arm))",
    ):
        _ = conn.execute(ddl)
    conn.commit()
    return conn


def run() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    keys = [k for k in (sys.argv[1:] or deep_panel()) if k in TOPICS]
    gold = {k for k in keys if TOPICS[k].canonical}
    data: dict[str, dict[str, Any]] = {}

    _free_router_vram()
    for k in keys:
        q = TOPICS[k].query
        qv = embed_query(q, mode="asym")
        store = Store(PG_DSN, emb_space="asym")
        try:
            ung = retrieve_subgraph(store, qv, q, gate=0.0, m=40)
            gat = retrieve_subgraph(store, qv, q, gate=GATE, m=40)
            fr = ung.frontier
            cand = rank_landmarks_ppr(
                ung.pool,
                ung.pool_edges,
                CAND,
                fr.frontier_year,
                fr.recent_floor,
                fr.now_year,
            )
            ids = {lm.arxiv_id for lm in cand} | {lm.arxiv_id for lm in gat.landmarks}
            absd = store.abstracts(list(ids))
        finally:
            store.close()
        data[k] = {
            "cand": cand,
            "gate40": gat.landmarks,
            "edges_u": ung.pool_edges,
            "edges_g": gat.pool_edges,
            "abs": absd,
            "by_id": {lm.arxiv_id: lm for lm in (*cand, *gat.landmarks)},
        }
        print(f"[retrieve] {k}: cand={len(cand)} gate40={len(gat.landmarks)}", flush=True)
    free_model()

    rc = sqlite3.connect(ROLE_CACHE)
    for k in keys:
        d = data[k]
        labels = {lm.arxiv_id: _role(rc, k, lm, d["abs"].get(lm.arxiv_id, "")) for lm in d["cand"]}
        for lm in d["gate40"]:
            labels.setdefault(lm.arxiv_id, _role(rc, k, lm, d["abs"].get(lm.arxiv_id, "")))
        d["labels"] = labels
        kept = [lm for lm in d["cand"] if labels.get(lm.arxiv_id) != "unrelated"]
        d["sets"] = {
            "fixed40": d["cand"][:CAP40],
            "gate40": d["gate40"],
            "llm40": kept[:CAP40],
            "llm_dyn": kept[:CAPDYN],
        }
        print(f"[role] {k}: kept {len(kept)}/{len(d['cand'])}", flush=True)
    rc.close()

    for k in keys:
        d = data[k]
        ids = {lm.arxiv_id for a in ARMS for lm in d["sets"][a]}
        sch = propose_schema(
            TOPICS[k].query,
            [
                f'{d["by_id"][i].title}\n{(d["abs"].get(i) or "")[:500]}'
                for i in list(ids)
                if i in d["by_id"]
            ][:6],
        )
        ext = asyncio.run(
            extract_many(
                [(i, d["by_id"][i].title if i in d["by_id"] else "") for i in ids],
                sch,
                d["abs"],
            )
        )
        d["ext"] = {
            a: "; ".join(f"{x}: {v}" for x, v in f.items() if v and v.lower() != "n/a")
            for a, f in ext.items()
        }
        print(f"[extract] {k}: {len(ext)} papers", flush=True)

    conn = _cache()
    for k in keys:
        d = data[k]
        for arm in ARMS:
            if conn.execute("SELECT 1 FROM compose WHERE topic=? AND arm=?", (k, arm)).fetchone():
                continue
            lms = d["sets"][arm]
            edges = d["edges_g"] if arm == "gate40" else d["edges_u"]
            dig = adjacency_digest(lms, _among(edges, {lm.arxiv_id for lm in lms}), d["ext"])
            rep, ptok, _ = chat_sync(
                NARRATOR,
                _SYS,
                f"Write the literature review answering: {TOPICS[k].query}\n\nGRAPH:\n{dig}",
                0.0,
                3500,
                extra_body=NO_THINK,
            )
            _ = conn.execute("INSERT INTO compose VALUES (?,?,?,?)", (k, arm, rep, ptok))
            conn.commit()
            print(f"[compose] {k}/{arm}: n={len(lms)}", flush=True)

    def rep_of(k: str, arm: str) -> str:
        return conn.execute(
            "SELECT report FROM compose WHERE topic=? AND arm=?", (k, arm)
        ).fetchone()[0]

    for k in keys:
        q_dated = f"(Today is {TODAY}.) {TOPICS[k].query}"
        canon = list(TOPICS[k].canonical)
        pool_ids = {lm.arxiv_id for a in ARMS for lm in data[k]["sets"][a]}
        for arm in ARMS:
            if not conn.execute(
                "SELECT 1 FROM judged WHERE topic=? AND arm=?", (k, arm)
            ).fetchone():
                rep = rep_of(k, arm)
                g, off = check_citations(rep, pool_ids)
                j = judge_report(q_dated, rep, canon, passes=1)
                j["grounded_frac"] = round(len(g) / max(1, len(g) + len(off)), 3)
                _ = conn.execute("INSERT INTO judged VALUES (?,?,?)", (k, arm, json.dumps(j)))
                conn.commit()
            if (
                arm != "fixed40"
                and not conn.execute(
                    "SELECT 1 FROM paired WHERE topic=? AND arm=?", (k, arm)
                ).fetchone()
            ):
                pj = judge_pairwise(q_dated, rep_of(k, arm), rep_of(k, "fixed40"), canon)
                _ = conn.execute("INSERT INTO paired VALUES (?,?,?)", (k, arm, json.dumps(pj)))
                conn.commit()

    def recall(lms: list[Landmark], k: str) -> tuple[float, float]:
        ch = {lm.arxiv_id.lower() for lm in lms}
        cn = {c.lower() for c in TOPICS[k].canonical}
        sp = {s.lower() for s in TOPICS[k].spine}
        return (
            len(cn & ch) / len(cn) if cn else 0.0,
            len(sp & ch) / len(sp) if sp else 0.0,
        )

    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        cnt = [len(data[k]["sets"][arm]) for k in keys]
        prec, span = [], []
        for k in keys:
            labs = [
                x
                for x in (data[k]["labels"].get(lm.arxiv_id) for lm in data[k]["sets"][arm])
                if x in ROLE_LABELS
            ]
            prec.append(1 - labs.count("unrelated") / len(labs) if labs else 0.0)
            span.append(1.0 if "foundational" in labs and "frontier" in labs else 0.0)
        lmr = [recall(data[k]["sets"][arm], k)[0] for k in gold]
        spr = [recall(data[k]["sets"][arm], k)[1] for k in gold]
        js = [
            json.loads(
                conn.execute("SELECT js FROM judged WHERE topic=? AND arm=?", (k, arm)).fetchone()[
                    0
                ]
            )
            for k in keys
        ]
        jm = {
            ax: round(sum(float(j[ax]) for j in js) / len(js), 3)
            for ax in ("grounding", "coverage", "lineage", "overall", "grounded_frac")
        }
        if arm == "fixed40":
            pn = 0.0
        else:
            pj = [
                json.loads(
                    conn.execute(
                        "SELECT js FROM paired WHERE topic=? AND arm=?", (k, arm)
                    ).fetchone()[0]
                )
                for k in keys
            ]
            w = sum(1 for p in pj if p["overall"] == "A")
            pn = round((w - sum(1 for p in pj if p["overall"] == "B")) / len(pj), 2)
        rows.append(
            {
                "arm": arm,
                "count": round(sum(cnt) / len(cnt), 1),
                "recall": round(sum(lmr) / len(lmr), 3) if lmr else 0.0,
                "spine": round(sum(spr) / len(spr), 3) if spr else 0.0,
                "precision": round(sum(prec) / len(prec), 3),
                "lineage_span": round(sum(span) / len(span), 3),
                **jm,
                "pair_net": pn,
            }
        )
    conn.close()

    (RESULTS).mkdir(parents=True, exist_ok=True)
    _ = (RESULTS / "metrics.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    cols = [
        "arm",
        "count",
        "recall",
        "spine",
        "precision",
        "lineage_span",
        "grounding",
        "coverage",
        "overall",
        "lineage",
        "grounded_frac",
        "pair_net",
    ]
    md = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    md.append(
        f"\n_{len(keys)} topics (gold-{len(gold)} for recall); validated axes grounding+coverage; lineage asterisked; judges date-injected._"
    )
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    tex = [
        "\\begin{tabular}{lrrrrrr}",
        "\\toprule",
        "arm & count & recall & precision & coverage & overall & pair \\\\",
        "\\midrule",
    ]
    for r in rows:
        tex.append(
            f"{r['arm'].replace('_', '-')} & {r['count']} & {r['recall']} & {r['precision']} & {r['coverage']} & {r['overall']} & {r['pair_net']} \\\\"
        )
    tex += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    bar_chart(
        rows,
        "arm",
        [
            ("recall", "Recall (gold)"),
            ("precision", "Precision"),
            ("coverage", "Coverage (judge)"),
            ("pair_net", "Pairwise net vs fixed40"),
        ],
        RESULTS / "ablation.png",
        title="Landmark selection — filter beats fixed cap",
    )
    print("\n" + "\n".join(md), flush=True)
