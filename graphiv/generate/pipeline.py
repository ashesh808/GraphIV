"""
The single-pass driver: a question in, a grounded chronological report out

Stages run retrieve, propose a schema, fill it per paper from full text, then compose
The effort dial trades breadth and depth against latency
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from graphiv.core.embed import embed_query
from graphiv.core.llm import NO_THINK, chat_sync
from graphiv.core.models import Edge, Era, Landmark, PoolNode
from graphiv.core.settings import NARRATOR_MODEL, OUTPUT_DIR, PG_DSN
from graphiv.core.store import Store, abs_yymm
from graphiv.generate.compose import build_digest, compose
from graphiv.generate.extract import extract_many
from graphiv.generate.figures import figure_block, figures_for, place_inline
from graphiv.generate.graph_viz import render_story
from graphiv.generate.narrate import linkify
from graphiv.generate.progress import StageTimer
from graphiv.generate.schema import propose_schema
from graphiv.generate.story import Story, build_story
from graphiv.retrieve.frontier import rank_landmarks_frontier
from graphiv.retrieve.grade import Grade, candidates, fused_score, grade_many
from graphiv.retrieve.hybrid import hybrid_pool
from graphiv.retrieve.pagerank import rank_landmarks_ppr
from graphiv.retrieve.recency import FrontierSpec, detect_frontier
from graphiv.retrieve.refined import frontier_pull, refined_pool
from graphiv.retrieve.subgraph import (
    assign_eras,
    augment_with_ancestors,
    induce_subgraph,
    main_path,
    rank_landmarks,
    tensions,
)
from graphiv.retrieve.topic_anchor import TopicTree
from graphiv.retrieve.trajectory import rank_landmarks_trajectory

# Reports land under <slug>/<cfg>/ inside the configured output dir
OUT = OUTPUT_DIR
# effort -> (n_pool, drill target, landmark count m, run extraction?)
TIERS: dict[str, tuple[int, int, int, bool]] = {
    "tiny": (200, 150, 30, False),
    "fast": (400, 280, 60, False),
    "standard": (400, 280, 80, True),
    "deep": (600, 360, 120, True),
}

# effort 0-5 maps to a tier, a round cap, a critique depth and figures

# a tier name aliases to a level, which is what the experiments pass
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
    """
    Map an effort level (0-5, or a fast/standard/deep alias) to its tier + deep-loop defaults
    """
    lvl = (
        EFFORT_ALIAS[effort] if isinstance(effort, str) and effort in EFFORT_ALIAS else int(effort)
    )
    return EFFORT_PROFILE[max(0, min(5, lvl))]


def _slug(text: str) -> str:
    """
    Filesystem slug; a truncated slug gets a hash suffix so long questions sharing a

        48-char prefix (e.g. a fixed instruction template) cannot collide and overwrite.
    """
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) <= 48:
        return s or "topic"
    h = hashlib.sha1(text.encode()).hexdigest()[:8]
    return f"{s[:39]}-{h}"


def _free_router_vram() -> None:
    """
    No-op kept for archived experiment code: the endpoint embed needs no VRAM handoff
    """


_HYDE_SYS = (
    "You write a single concise, realistic arXiv-style abstract (4-6 sentences) for a "
    "hypothetical foundational paper on the user's topic. Output ONLY the abstract text, "
    "no title, no preamble."
)


def hyde_query(question: str) -> str:
    """
    Write a hypothetical abstract so the embedded query is shaped like a document

    A bare topic phrase collides lexically with off-topic papers, while a hypothetical
    abstract lands among real ones; any LLM failure falls back to the bare question.
    """
    try:
        text, _, _ = chat_sync(NARRATOR_MODEL, _HYDE_SYS, question, 0.5, 400, NO_THINK)
    except Exception:  # noqa: BLE001
        return question
    text = text.strip()
    return f"Title: {question}\nAbstract: {text}" if text else question


# recency-aware rankers take the topic-adaptive frontier; "indegree" is the bare ablation
_RANKERS = {
    "ppr": rank_landmarks_ppr,  # personalized PageRank + frontier reservation
    "frontier": rank_landmarks_frontier,  # age-normalized in-degree + frontier reservation
}


@dataclass
class Pass:
    """
    One retrieval+rank result; shared by the single-pass run and the deep loop
    """

    pool: dict[str, PoolNode]
    landmarks: list[Landmark]
    edges: list[Edge]
    eras: list[Era]
    spine: list[str]
    tens: list[Edge]
    leaf: str | None
    fr: FrontierSpec
    grades: dict[str, Grade]
    story: Story


def _grade_pool(
    question: str,
    store: Store,
    pool: dict[str, PoolNode],
    edges: list[Edge],
    m: int,
    grades: dict[str, Grade],
) -> None:
    """
    Reader grading pass over the landmark candidates (cache-first, incremental)
    """
    qhash = hashlib.sha1(question.encode()).hexdigest()[:12]
    indeg: dict[str, int] = {}
    for e in edges:
        indeg[e.dst] = indeg.get(e.dst, 0) + 1
    cand = [a for a in candidates(pool, indeg, m) if a not in grades]
    if not cand:
        return
    abstracts = store.abstracts(cand)
    grades.update(asyncio.run(grade_many(question, qhash, pool, cand, abstracts)))
    n_bad = sum(1 for a in cand if grades.get(a) and grades[a].relevance <= -2)
    print(
        f"[research] graded {len(cand)} candidates ({n_bad} rated -2/unrelated)",
        flush=True,
    )


def _rank_graded(
    pool: dict[str, PoolNode],
    edges: list[Edge],
    m: int,
    rank: str,
    no_graph: bool,
    fr: FrontierSpec,
    grades: dict[str, Grade],
    fuse: bool,
) -> list[Landmark]:
    """
    Rank landmarks, optionally on the fused (cosine x graded-relevance) score

        With `fuse`, relevance -2 papers leave the ranking pool entirely (they remain in the
        caller's pool as graph connectors) and every candidate's seed score becomes fused.
        Returned landmarks always carry the original cosine in `.score` plus role/relevance.
    """
    rank_pool_nodes = pool
    if fuse and grades:
        rank_pool_nodes = {}
        for a, n in pool.items():
            g = grades.get(a)
            if g is not None and g.relevance <= -2:
                continue
            rank_pool_nodes[a] = PoolNode(
                n.arxiv_id, n.title, n.year, n.category, fused_score(n.score, g)
            )
    if no_graph or rank == "indegree":
        landmarks = rank_landmarks(rank_pool_nodes, edges, m)
    elif rank == "trajectory":
        landmarks = rank_landmarks_trajectory(
            rank_pool_nodes,
            edges,
            m,
            fr.frontier_year,
            fr.recent_floor,
            fr.now_year,
            grades,
        )
    else:
        landmarks = _RANKERS[rank](
            rank_pool_nodes, edges, m, fr.frontier_year, fr.recent_floor, fr.now_year
        )
    for lm in landmarks:
        lm.score = pool[lm.arxiv_id].score  # restore true cosine after fused ranking
        g = grades.get(lm.arxiv_id)
        if g is not None:
            lm.role, lm.relevance = g.role, g.relevance
    return landmarks


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
    grade: bool = False,
    fuse: bool = False,
    seed: str | None = None,
) -> Pass:
    """
    Hybrid pool -> topic-adaptive frontier -> refined drill -> induce subgraph ->

        (reader grade) -> rank -> story.

        The single source of the recency logic; both run() and deep_loop reuse it so the
        frontier handling never diverges between the single-pass and iterative paths.
        `no_frontier_pull` disables the leaf-independent recent-paper pull (ablation lever);
        `grade` runs the reader role/relevance pass; `fuse` ranks on cosine x graded relevance;
        `seed` force-injects one paper into the pool at top similarity.
    """
    pool = hybrid_pool(store, qvec, question, n_pool)
    if seed:
        meta = store.meta_for(seed)
        if meta is not None:
            title, year, cat, _ = meta
            pool[seed] = PoolNode(seed, title, year, cat, 1.0)
    years0 = [n.year for n in pool.values() if n.year is not None]
    fr = detect_frontier(years0, now.year, now.month, m, recency)
    print(
        f"[research] frontier_year={fr.frontier_year} recent_floor={fr.recent_floor} "
        f"(now {now.year}-{now.month:02d})",
        flush=True,
    )
    leaf: str | None = None
    if not no_cluster:  # ablation: skip the topic-tree refinement
        pool, leaf, _ = refined_pool(store, qvec, pool, tree, fr.frontier_year, target=target)
    # the tree predates the delta, so the newest papers are pulled by vector search instead
    if not no_frontier_pull:
        front = frontier_pull(store, qvec, fr.frontier_year, want=max(40, fr.recent_floor))
        n_front = sum(1 for a in front if a not in pool)
        pool.update(front)
        print(f"[research] frontier_pull added {n_front} recent papers", flush=True)
    else:
        print("[research] frontier_pull DISABLED (ablation)", flush=True)
    _ = augment_with_ancestors(store, pool, qvec, max_add=120, min_cosine=0.30)
    edges = [] if no_graph else induce_subgraph(store, list(pool))
    print(f"[research] pool {len(pool)} · edges {len(edges)} · leaf {leaf}", flush=True)
    grades: dict[str, Grade] = {}
    if grade:
        _grade_pool(question, store, pool, edges, m, grades)
    landmarks = _rank_graded(pool, edges, m, rank, no_graph, fr, grades, fuse)
    eras = assign_eras(landmarks)
    spine = main_path(landmarks, edges)
    tens = tensions(landmarks, edges)
    story = build_story(landmarks, edges, tens, pool)
    return Pass(pool, landmarks, edges, eras, spine, tens, leaf, fr, grades, story)


def rank_pool(
    store: Store,
    pool: dict[str, PoolNode],
    m: int,
    rank: str,
    no_graph: bool,
    fr: FrontierSpec,
    question: str = "",
    grades: dict[str, Grade] | None = None,
    grade: bool = False,
    fuse: bool = False,
) -> Pass:
    """
    Induce + rank an already-built pool (the deep loop's re-rank after gap expansion)

        Reuses the round-0 frontier `fr` so the topic frontier stays stable across rounds;
        incrementally grades any new (gap-expansion) candidates when `grade` is on.
    """
    edges = [] if no_graph else induce_subgraph(store, list(pool))
    grades = grades if grades is not None else {}
    if grade:
        _grade_pool(question, store, pool, edges, m, grades)
    landmarks = _rank_graded(pool, edges, m, rank, no_graph, fr, grades, fuse)
    eras = assign_eras(landmarks)
    spine = main_path(landmarks, edges)
    tens = tensions(landmarks, edges)
    story = build_story(landmarks, edges, tens, pool)
    return Pass(pool, landmarks, edges, eras, spine, tens, None, fr, grades, story)


def seed_slug(seed: str) -> str:
    """
    Filesystem-safe slug for a seed paper's arXiv id
    """
    return seed.replace("/", "_").replace(".", "")


def pick_figure_items(
    landmarks: list[Landmark],
    report: str,
    frontier_year: int,
    cap: int = 14,
) -> list[tuple[str, str]]:
    """
    Figure candidates: papers actually cited in the report, role-gated when graded

        (foundational/core/frontier with relevance >= 1), spine-fame alone no longer qualifies.
        Ordered frontier-first then by in-degree; ungraded landmarks pass the old gate (cited).
    """
    cited = [lm for lm in landmarks if f"arXiv:{lm.arxiv_id}" in report]
    ok: list[Landmark] = []
    for lm in cited:
        if lm.role is not None:
            if lm.role in ("foundational", "core", "frontier") and (
                lm.relevance is not None and lm.relevance >= 1
            ):
                ok.append(lm)
        else:
            ok.append(lm)
    ok.sort(
        key=lambda lm: (
            lm.year is not None and lm.year >= frontier_year,
            lm.in_degree,
            lm.score,
        ),
        reverse=True,
    )
    return [(lm.arxiv_id, lm.title) for lm in ok[:cap]]


def attach_figures(
    report: str, figs: dict[str, dict[str, object]], landmarks: list[Landmark]
) -> str:
    """
    Place figures inline after the first section citing them; leftovers in an end gallery
    """
    if not figs:
        return report
    titles = {lm.arxiv_id: lm.title for lm in landmarks}
    report, leftovers = place_inline(report, figs, titles)
    if leftovers:
        gal = ["\n\n---\n\n## Key Figures\n"]
        for aid in leftovers:
            gal.append(figure_block(aid, titles.get(aid, aid), figs[aid]))
        report = report + "\n".join(gal)
    return report


def write_pool(
    out_dir: Path,
    pool: dict[str, PoolNode],
    grades: dict[str, Grade],
    landmark_ids: set[str],
) -> None:
    """
    Persist the full retrieval pool (pool.json) so pool-cut vs selection-loss stays

        distinguishable post-hoc (the SimPO/KTO ambiguity: absent from landmarks, but was it
        ever retrieved?).
    """
    rows: list[dict[str, object]] = []
    for a, n in sorted(pool.items(), key=lambda kv: -kv[1].score):
        g = grades.get(a)
        rows.append(
            {
                "arxiv_id": a,
                "title": n.title,
                "year": n.year,
                "cosine": round(n.score, 4),
                "role": g.role if g else None,
                "relevance": g.relevance if g else None,
                "landmark": a in landmark_ids,
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    _ = (out_dir / "pool.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")


def graph_section(viz_meta: dict[str, object]) -> str:
    """
    The citation-graph block placed right after the report banner
    """
    return (
        "![citation graph](graph.png)\n\n"
        f"*The citation story graph behind this review — {viz_meta['nodes']} papers, "
        f"{viz_meta['edges']} intent-typed edges, {viz_meta['threads']} lineage threads "
        "(gold). Node size = in-topic citations, color = role. "
        "[Interactive version](graph.html).*\n\n---\n\n"
    )


def cap_spec(max_date: str, exclude: str) -> tuple[int | None, frozenset[str]]:
    """
    Parse the eval-mode retrieval cap: max_date 'YYMM' -> absolute YYYYMM, exclude csv -> set
    """
    md = max_date.strip()
    if md and (len(md) != 4 or not md.isdigit()):
        raise SystemExit(f"max_date must be YYMM (e.g. 2401), got: {max_date!r}")
    cap = abs_yymm(int(md[:2]), int(md[2:])) if md else None
    ids = frozenset(a.strip() for a in exclude.split(",") if a.strip())
    return cap, ids


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
    no_grade: bool = False,
    fuse: bool = False,
    seed: str | None = None,
    max_date: str = "",
    exclude: str = "",
) -> dict[str, object]:
    """
    Run the single pass end to end and return the run record
    """
    n_pool, target, m, do_extract = TIERS[effort]
    cap, excl = cap_spec(max_date, exclude)
    # a seed paper's own title and abstract are already doc-shaped, so they replace HyDE
    qtext = question
    if seed:
        s = Store(PG_DSN, emb_space=embed_mode)
        meta_row = s.meta_for(seed)
        s.close()
        if meta_row is None:
            raise SystemExit(f"seed arXiv id not in corpus: {seed}")
        qtext = f"Title: {meta_row[0]}\nAbstract: {meta_row[3]}"
        if not question.strip():
            question = f"the development of: {meta_row[0]}"
    print(
        f"[research] '{question}' effort={effort} rank={rank} recency={recency} "
        f"no_cluster={no_cluster} no_graph={no_graph} no_frontier_pull={no_frontier_pull} "
        f"embed={embed_mode} hyde={use_hyde} grade={not no_grade} fuse={fuse} seed={seed}",
        flush=True,
    )
    cfg = (
        f"{effort}-{rank}-r{recency}-{embed_mode}{'-hyde' if use_hyde else '-raw'}"
        f"{'-nocluster' if no_cluster else ''}{'-nograph' if no_graph else ''}"
        f"{'-nofpull' if no_frontier_pull else ''}{'-nograde' if no_grade else ''}"
        f"{'-fuse' if fuse else ''}{f'-seed{seed_slug(seed)}' if seed else ''}"
        f"{f'-cap{max_date}' if cap else ''}"
    )
    out_dir = OUT / _slug(question) / cfg
    timer = StageTimer(out_dir, question)
    grade = do_extract and not no_grade  # reader pass rides the extraction tiers

    """
    Query construction follows the space: the sym space needs a doc-shaped HyDE query
    The asym space embeds the raw question under its own search_query prompt
    Both the query and every store lookup read the same embed_mode
    """
    with timer.stage("embed"):
        if not seed and use_hyde:
            qtext = hyde_query(question)
        qvec = embed_query(qtext, mode=embed_mode)
    tree = TopicTree()
    # Capped eval runs also time-travel the clock so frontier detection sees the cap's world
    now = datetime(cap // 100, cap % 100, 28) if cap else datetime.now()
    store = Store(PG_DSN, emb_space=embed_mode, max_yymm=cap, exclude=excl)
    try:
        with timer.stage("retrieve+grade+rank"):
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
                grade=grade,
                fuse=fuse,
                seed=seed,
            )
        pool, landmarks, edges = p.pool, p.landmarks, p.edges
        eras, spine, tens, fr = p.eras, p.spine, p.tens, p.fr
        abstracts = store.abstracts([lm.arxiv_id for lm in landmarks])
    finally:
        store.close()
    # R1.5: schema from the question + a few top-landmark abstracts
    samples = [
        f"Title: {lm.title}\nAbstract: {abstracts.get(lm.arxiv_id, '')[:400]}"
        for lm in landmarks[:6]
    ]
    schema = propose_schema(question, samples)
    print(f"[research] schema({schema.hash}): {schema.names()}", flush=True)

    extractions: dict[str, dict[str, str]] = {}
    if do_extract:
        print(f"[research] extracting {len(landmarks)} papers (full text) ...", flush=True)
        with timer.stage("extract"):
            extractions = asyncio.run(
                extract_many([(lm.arxiv_id, lm.title) for lm in landmarks], schema, abstracts)
            )
        print(f"[research] extracted {len(extractions)}/{len(landmarks)}", flush=True)

    digest = build_digest(
        question,
        landmarks,
        edges,
        eras,
        spine,
        tens,
        extractions,
        schema,
        abstracts,
        story=p.story,
        pool=pool,
    )
    print("[research] composing report ...", flush=True)
    with timer.stage("compose"):
        report, grounded, off_digest = compose(question, digest, set(pool))
    print(
        f"[research] report chars={len(report)} grounded={len(grounded)} "
        f"off_digest={len(off_digest)}",
        flush=True,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    write_pool(out_dir, pool, p.grades, {lm.arxiv_id for lm in landmarks})
    frontier = sum(1 for lm in landmarks if lm.year is not None and lm.year >= fr.frontier_year)
    with timer.stage("viz"):
        viz_meta = render_story(question, landmarks, edges, p.story, pool, out_dir)

    # P3: deep tier reads + embeds key figures (vision model) for the report-cited landmarks
    figs: dict[str, dict[str, object]] = {}
    if effort == "deep":
        fig_items = pick_figure_items(landmarks, report, fr.frontier_year, cap=12)
        print(f"[research] reading figures for {len(fig_items)} papers ...", flush=True)
        with timer.stage("figures"):
            figs = asyncio.run(figures_for(fig_items, out_dir, top_n=len(fig_items)))
        print(f"[research] captioned {len(figs)} figures", flush=True)
        report = attach_figures(report, figs, landmarks)
    header = (
        f"# {question}\n\n*effort {effort} · pool {len(pool)} · landmarks {len(landmarks)} · "
        f"schema {schema.names()} · grounded {len(grounded)} · off-digest {len(off_digest)}*\n\n---\n\n"
    )
    body = graph_section(viz_meta) + report
    _ = (out_dir / "report.md").write_text(linkify(header + body), encoding="utf-8")
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
        "grade": grade,
        "fuse": fuse,
        "seed": seed,
        "max_date": max_date,
        "exclude": exclude,
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
        "graph": viz_meta,
        "report_chars": len(report),
        "timings": timer.timings(),
        "landmarks": [asdict(lm) for lm in landmarks],
    }
    _ = (out_dir / "run.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"[research] done -> {out_dir}/report.md", flush=True)
    return meta
