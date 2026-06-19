"""P2+P4 — deep-research driver: question -> grounded, chronological literature report.

Pipeline: R1 retrieve (refined dual-graph pool + frontier-aware landmarks) -> R1.5 propose a
question-specific extraction schema -> R2 fill it per paper from full text (cached) -> R3
compose one long, chronological, grounded report. Effort knob trades breadth/depth vs latency.

    uv run python phases/phase-6/run.py "<question>" --set-effort standard
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict
from pathlib import Path

from _common import LLM_ROUTER, NEO4J_DB, neo4j_driver
from compose_report import build_digest, compose
from extract import extract_many
from figures import figures_for
from frontier_rank import rank_landmarks_frontier
from pagerank import rank_landmarks_ppr
from retrieval_hybrid import hybrid_pool
from retrieval_refined import refined_pool
from retrieve import embed_query, fetch_abstracts, free_model
from schema import propose_schema
from subgraph import (
    assign_eras,
    augment_with_ancestors,
    induce_subgraph,
    main_path,
    rank_landmarks,
    tensions,
)
from topic_anchor import TopicTree

# Reports land under the phase's own output dir: phase-6/output/research/<slug>/<cfg>/.
OUT = Path(__file__).resolve().parents[1] / "output" / "research"
# effort -> (n_pool, drill target, landmark count m, run extraction?)
TIERS: dict[str, tuple[int, int, int, bool]] = {
    "fast": (400, 280, 40, False),
    "standard": (400, 280, 80, True),
    "deep": (600, 360, 120, True),
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "topic"


def _free_router_vram() -> None:
    """Unload any resident router model so the in-process nomic embed has VRAM headroom."""
    import urllib.request

    try:
        _ = urllib.request.urlopen(f"{LLM_ROUTER}/router/restart", timeout=120)
    except Exception:  # noqa: BLE001
        pass


_RANKERS = {
    "ppr": rank_landmarks_ppr,  # personalized PageRank + frontier reservation
    "frontier": rank_landmarks_frontier,  # in-degree + frontier reservation
    "indegree": rank_landmarks,  # pure in-degree (ablation: no frontier, no PPR)
}


def run(
    question: str,
    effort: str,
    rank: str = "ppr",
    no_cluster: bool = False,
    no_graph: bool = False,
) -> dict[str, object]:
    n_pool, target, m, do_extract = TIERS[effort]
    print(
        f"[research] '{question}' effort={effort} rank={rank} "
        f"no_cluster={no_cluster} no_graph={no_graph}",
        flush=True,
    )

    _free_router_vram()  # reclaim VRAM from any resident LLM before loading nomic
    qvec = embed_query(question)
    free_model()
    tree = TopicTree()
    leaf = None
    with neo4j_driver() as drv, drv.session(database=NEO4J_DB) as session:
        pool = hybrid_pool(session, qvec, question, n_pool)
        if not no_cluster:  # ablation: skip the topic-tree refinement
            pool, leaf, _ = refined_pool(session, qvec, pool, tree, target=target)
        _ = augment_with_ancestors(session, pool, qvec, max_add=120)
        # ablation: no_graph drops the citation subgraph (vector-only, no chronology).
        edges = [] if no_graph else induce_subgraph(session, list(pool))
        print(
            f"[research] pool {len(pool)} · edges {len(edges)} · leaf {leaf}",
            flush=True,
        )
    # no_graph -> no in-degree/PPR signal, so rank by similarity (sort pool by score).
    landmarks = (
        rank_landmarks(pool, edges, m) if no_graph else _RANKERS[rank](pool, edges, m)
    )
    eras = assign_eras(landmarks)
    spine = main_path(landmarks, edges)
    tens = tensions(landmarks, edges)

    abstracts = fetch_abstracts([lm.arxiv_id for lm in landmarks])
    # R1.5: schema from the question + a few top-landmark abstracts.
    samples = [
        f"Title: {lm.title}\nAbstract: {abstracts.get(lm.arxiv_id, '')[:400]}"
        for lm in landmarks[:6]
    ]
    schema = propose_schema(question, samples)
    print(f"[research] schema({schema.hash}): {schema.names()}", flush=True)

    extractions: dict[str, dict[str, str]] = {}
    if do_extract:
        print(
            f"[research] extracting {len(landmarks)} papers (full text) ...", flush=True
        )
        extractions = asyncio.run(
            extract_many(
                [(lm.arxiv_id, lm.title) for lm in landmarks], schema, abstracts
            )
        )
        print(f"[research] extracted {len(extractions)}/{len(landmarks)}", flush=True)

    digest = build_digest(
        question, landmarks, edges, eras, spine, tens, extractions, schema, abstracts
    )
    print("[research] composing report ...", flush=True)
    report, grounded, off_digest = compose(question, digest, set(pool))
    print(
        f"[research] report chars={len(report)} grounded={len(grounded)} "
        f"off_digest={len(off_digest)}",
        flush=True,
    )

    cfg = f"{effort}-{rank}{'-nocluster' if no_cluster else ''}{'-nograph' if no_graph else ''}"
    out_dir = OUT / _slug(question) / cfg
    out_dir.mkdir(parents=True, exist_ok=True)
    frontier = sum(1 for lm in landmarks if lm.year is not None and lm.year >= 2023)

    # P3: deep tier reads + embeds key figures (vision model) for the most-cited landmarks.
    figs: dict[str, dict[str, object]] = {}
    if effort == "deep":
        top = sorted(landmarks, key=lambda lm: -lm.in_degree)
        print(
            f"[research] reading figures for top {min(12, len(top))} papers ...",
            flush=True,
        )
        figs = asyncio.run(
            figures_for([(lm.arxiv_id, lm.title) for lm in top], out_dir, top_n=12)
        )
        print(f"[research] captioned {len(figs)} figures", flush=True)
        if figs:
            by_id = {lm.arxiv_id: lm for lm in landmarks}
            gal = ["\n\n---\n\n## Key Figures\n"]
            for aid, info in figs.items():
                title = by_id[aid].title if aid in by_id else aid
                gal.append(
                    f"**{title}** — arXiv:{aid} p.{info['page']}\n\n"
                    f"![{aid}]({info['file']})\n\n{info['caption']}\n"
                )
            report = report + "\n".join(gal)
    header = (
        f"# {question}\n\n*effort {effort} · pool {len(pool)} · landmarks {len(landmarks)} · "
        f"schema {schema.names()} · grounded {len(grounded)} · off-digest {len(off_digest)}*\n\n---\n\n"
    )
    _ = (out_dir / "report.md").write_text(header + report, encoding="utf-8")
    _ = (out_dir / "digest.txt").write_text(digest, encoding="utf-8")
    meta = {
        "question": question,
        "effort": effort,
        "rank": rank,
        "no_cluster": no_cluster,
        "no_graph": no_graph,
        "config": cfg,
        "schema": schema.fields,
        "n_pool": len(pool),
        "n_landmarks": len(landmarks),
        "n_edges": len(edges),
        "frontier_2023plus": frontier,
        "grounded": grounded,
        "off_digest": off_digest,
        "n_figures": len(figs),
        "figures": figs,
        "report_chars": len(report),
        "landmarks": [asdict(lm) for lm in landmarks],
    }
    _ = (out_dir / "run.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"[research] done -> {out_dir}/report.md", flush=True)
    return meta
