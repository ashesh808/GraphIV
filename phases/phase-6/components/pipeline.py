"""P2+P4 — deep-research driver: question -> grounded, chronological literature report.

Pipeline: R1 retrieve (refined dual-graph pool + frontier-aware landmarks) -> R1.5 propose a
question-specific extraction schema -> R2 fill it per paper from full text (cached) -> R3
compose one long, chronological, grounded report. Effort knob trades breadth/depth vs latency.

    uv run python phases/phase-6/run.py "<question>" --set-effort standard
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from _common import LLM_ROUTER, NARRATOR_MODEL, PG_DSN
from compose_report import build_digest, compose
from extract import extract_many
from figures import figures_for
from frontier_rank import rank_landmarks_frontier
from llm import NO_THINK, chat_sync
from pagerank import rank_landmarks_ppr
from recency import FrontierSpec, detect_frontier
from retrieval_hybrid import hybrid_pool
from retrieval_refined import frontier_pull, refined_pool
from retrieve import embed_query, free_model
from store import Store
from schema import propose_schema
from subgraph import (
    Edge,
    Era,
    Landmark,
    PoolNode,
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
    "tiny": (200, 150, 30, False),
    "fast": (400, 280, 40, False),
    "standard": (400, 280, 80, True),
    "deep": (600, 360, 120, True),
}

# numeric effort 0-5 (a single master dial) -> (tier_key, max_rounds, critique_k, figures).
# string names alias to a level for back-compat; experiments still pass the tier strings directly.
EFFORT_ALIAS: dict[str, int] = {"fast": 1, "standard": 2, "deep": 4}
EFFORT_PROFILE: dict[int, tuple[str, int, int, bool]] = {
    0: ("tiny", 1, 0, False),
    1: ("fast", 1, 0, False),
    2: ("standard", 1, 0, False),
    3: ("standard", 2, 4, True),
    4: ("deep", 4, 4, True),
    5: ("deep", 6, 6, True),
}


def effort_profile(effort: str | int) -> tuple[str, int, int, bool]:
    """Map an effort level (0-5, or a fast/standard/deep alias) to its tier + deep-loop defaults."""
    lvl = (
        EFFORT_ALIAS[effort]
        if isinstance(effort, str) and effort in EFFORT_ALIAS
        else int(effort)
    )
    return EFFORT_PROFILE[max(0, min(5, lvl))]


def _slug(text: str) -> str:
    """Filesystem slug; a truncated slug gets a hash suffix so long questions sharing a
    48-char prefix (e.g. a fixed instruction template) cannot collide and overwrite."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) <= 48:
        return s or "topic"
    h = hashlib.sha1(text.encode()).hexdigest()[:8]
    return f"{s[:39]}-{h}"


def _free_router_vram() -> None:
    """Unload any resident router model so the in-process nomic embed has VRAM headroom."""
    import urllib.request

    try:
        _ = urllib.request.urlopen(f"{LLM_ROUTER}/router/restart", timeout=120)
    except Exception:  # noqa: BLE001
        pass


_HYDE_SYS = (
    "You write a single concise, realistic arXiv-style abstract (4-6 sentences) for a "
    "hypothetical foundational paper on the user's topic. Output ONLY the abstract text, "
    "no title, no preamble."
)


def hyde_query(question: str) -> str:
    """HyDE: an LLM writes a hypothetical abstract so the EMBEDDED query is doc-shaped
    ('Title: ..\\nAbstract: ..'), matching how the corpus was encoded. A bare topic phrase
    embeds poorly (it lexically collides with off-topic papers — 'diffusion' -> diffusing-media
    physics); the doc-shaped hypothetical lands among real abstracts. Falls back to the bare
    question on any LLM failure. Must run BEFORE the router VRAM is freed for the nomic embed.
    """
    try:
        text, _, _ = chat_sync(NARRATOR_MODEL, _HYDE_SYS, question, 0.5, 400, NO_THINK)
    except Exception:  # noqa: BLE001
        return question
    text = text.strip()
    return f"Title: {question}\nAbstract: {text}" if text else question


# recency-aware rankers take the topic-adaptive frontier; "indegree" is the bare ablation.
_RANKERS = {
    "ppr": rank_landmarks_ppr,  # personalized PageRank + frontier reservation
    "frontier": rank_landmarks_frontier,  # age-normalized in-degree + frontier reservation
}


@dataclass
class Pass:
    """One retrieval+rank result; shared by the single-pass run and the deep loop."""

    pool: dict[str, PoolNode]
    landmarks: list[Landmark]
    edges: list[Edge]
    eras: list[Era]
    spine: list[str]
    tens: list[Edge]
    leaf: str | None
    fr: FrontierSpec


def retrieve_rank(
    store: Store,
    qvec: list[float],
    question: str,
    tree: TopicTree,
    n_pool: int,
    target: int,
    m: int,
    rank: str,
    no_cluster: bool,
    no_graph: bool,
    recency: float,
    now: datetime,
    no_frontier_pull: bool = False,
) -> Pass:
    """Hybrid pool -> topic-adaptive frontier -> refined drill -> induce subgraph -> rank.

    The single source of the recency logic; both run() and deep_loop reuse it so the
    frontier handling never diverges between the single-pass and iterative paths.
    `no_frontier_pull` disables the leaf-independent recent-paper pull (ablation lever).
    """
    pool = hybrid_pool(store, qvec, question, n_pool)
    years0 = [n.year for n in pool.values() if n.year is not None]
    fr = detect_frontier(years0, now.year, now.month, m, recency)
    print(
        f"[research] frontier_year={fr.frontier_year} recent_floor={fr.recent_floor} "
        f"(now {now.year}-{now.month:02d})",
        flush=True,
    )
    leaf: str | None = None
    if not no_cluster:  # ablation: skip the topic-tree refinement
        pool, leaf, _ = refined_pool(
            store, qvec, pool, tree, fr.frontier_year, target=target
        )
    # leaf-independent frontier pull: the topic tree predates the delta, so the newest
    # papers have no leaf — vector-search them directly so 2025/2026 work can enter the pool.
    if not no_frontier_pull:
        front = frontier_pull(
            store, qvec, fr.frontier_year, want=max(40, fr.recent_floor)
        )
        n_front = sum(1 for a in front if a not in pool)
        pool.update(front)
        print(f"[research] frontier_pull added {n_front} recent papers", flush=True)
    else:
        print("[research] frontier_pull DISABLED (ablation)", flush=True)
    _ = augment_with_ancestors(store, pool, qvec, max_add=120, min_cosine=0.35)
    edges = [] if no_graph else induce_subgraph(store, list(pool))
    print(f"[research] pool {len(pool)} · edges {len(edges)} · leaf {leaf}", flush=True)
    if no_graph or rank == "indegree":
        landmarks = rank_landmarks(pool, edges, m)
    else:
        landmarks = _RANKERS[rank](
            pool, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year
        )
    eras = assign_eras(landmarks)
    spine = main_path(landmarks, edges)
    tens = tensions(landmarks, edges)
    return Pass(pool, landmarks, edges, eras, spine, tens, leaf, fr)


def rank_pool(
    store: Store,
    pool: dict[str, PoolNode],
    m: int,
    rank: str,
    no_graph: bool,
    fr: FrontierSpec,
) -> Pass:
    """Induce + rank an already-built pool (the deep loop's re-rank after gap expansion).

    Reuses the round-0 frontier `fr` so the topic frontier stays stable across rounds.
    """
    edges = [] if no_graph else induce_subgraph(store, list(pool))
    if no_graph or rank == "indegree":
        landmarks = rank_landmarks(pool, edges, m)
    else:
        landmarks = _RANKERS[rank](
            pool, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year
        )
    eras = assign_eras(landmarks)
    spine = main_path(landmarks, edges)
    tens = tensions(landmarks, edges)
    return Pass(pool, landmarks, edges, eras, spine, tens, None, fr)


def run(
    question: str,
    effort: str,
    rank: str = "ppr",
    no_cluster: bool = False,
    no_graph: bool = False,
    recency: float = 0.4,
    no_frontier_pull: bool = False,
    embed_mode: str = "sym",
    use_hyde: bool = True,
) -> dict[str, object]:
    n_pool, target, m, do_extract = TIERS[effort]
    print(
        f"[research] '{question}' effort={effort} rank={rank} recency={recency} "
        f"no_cluster={no_cluster} no_graph={no_graph} no_frontier_pull={no_frontier_pull} "
        f"embed={embed_mode} hyde={use_hyde}",
        flush=True,
    )

    # Query construction is format-dependent: HyDE shapes a doc-like query for the SYMMETRIC space
    # (a bare phrase embeds poorly there); the ASYMMETRIC space embeds the raw question with nomic's
    # native search_query prompt. Both the query and every store lookup use `embed_mode`.
    qtext = (
        hyde_query(question) if use_hyde else question
    )  # router LLM — before freeing VRAM
    _free_router_vram()  # reclaim VRAM from any resident LLM before loading nomic
    qvec = embed_query(qtext, mode=embed_mode)
    free_model()
    tree = TopicTree()
    now = datetime.now()
    store = Store(PG_DSN, emb_space=embed_mode)
    try:
        p = retrieve_rank(
            store,
            qvec,
            question,
            tree,
            n_pool,
            target,
            m,
            rank,
            no_cluster,
            no_graph,
            recency,
            now,
            no_frontier_pull,
        )
        pool, landmarks, edges = p.pool, p.landmarks, p.edges
        eras, spine, tens, fr = p.eras, p.spine, p.tens, p.fr
        abstracts = store.abstracts([lm.arxiv_id for lm in landmarks])
    finally:
        store.close()
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

    cfg = (
        f"{effort}-{rank}-r{recency}-{embed_mode}{'-hyde' if use_hyde else '-raw'}"
        f"{'-nocluster' if no_cluster else ''}{'-nograph' if no_graph else ''}"
        f"{'-nofpull' if no_frontier_pull else ''}"
    )
    out_dir = OUT / _slug(question) / cfg
    out_dir.mkdir(parents=True, exist_ok=True)
    frontier = sum(
        1 for lm in landmarks if lm.year is not None and lm.year >= fr.frontier_year
    )

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
        "recency": recency,
        "no_frontier_pull": no_frontier_pull,
        "embed_mode": embed_mode,
        "use_hyde": use_hyde,
        "config": cfg,
        "schema": schema.fields,
        "n_pool": len(pool),
        "n_landmarks": len(landmarks),
        "n_edges": len(edges),
        "frontier_year": fr.frontier_year,
        "frontier_count": frontier,
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
