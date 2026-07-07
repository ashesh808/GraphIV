"""Judge-driven deep-research loop (the deep tier's control flow).

Round 0 retrieves + grades (reader role/relevance per candidate) + ranks + composes a draft.
Then each round a thinking judge (-code) reads the draft and either declares it SATURATED or
returns concrete gap queries; the loop embeds those gaps, retrieves more papers, merges them,
incrementally grades the newcomers, re-ranks (growing the landmark budget), and recomposes.
The JUDGE owns termination — `max_rounds` is only an upper cap. Before the final compose, the
top papers get a full-PDF critique (`critique_k`) folded into the digest. Emits report.md +
report.tex + graph.png/graph.html + papers.json + run.json (with stage timings) + the judge
transcript; report.pdf is attempted best-effort via latexmk.

VRAM is sequenced for one 3090: free the router LLM before each nomic embed, free nomic
before each Gemma stage (grade / extract / compose / judge / critique), exactly as the
single-pass path does.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from _common import PG_DSN
from compose_report import build_digest, compose_skeleton
from critique import critique_many
from extract import extract_many
from figures import figures_for
from graph_viz import render_story
from judge import Verdict, judge_report, retrieval_context
from latex_report import to_tex
from long_compose import compose_long
from narrate import linkify
from pipeline import (
    OUT,
    TIERS,
    _free_router_vram,
    _slug,
    attach_figures,
    graph_section,
    hyde_query,
    pick_figure_items,
    rank_pool,
    retrieve_rank,
    seed_slug,
    write_pool,
)
from reader_grade import Grade, summarize_many
from retrieval_refined import refined_pool
from retrieve import embed_query, free_model
from run_progress import StageTimer
from store import Store
from schema import Schema, propose_schema
from story_graph import Story
from subgraph import Edge, Era, Landmark, PoolNode
from topic_anchor import TopicTree

GAP_POOL = 150  # per-gap retrieval breadth
M_GROW = 40  # landmark budget growth per round (broaden coverage)
M_MAX = 260  # hard cap on landmark count


def _embed_gaps(
    gaps: list[str], embed_mode: str = "sym"
) -> list[tuple[str, list[float]]]:
    """Embed gap queries in one nomic load, then free it (hand VRAM back to Gemma)."""
    _free_router_vram()
    out = [(g, embed_query(g, mode=embed_mode)) for g in gaps]
    free_model()
    return out


_GAP_ID = re.compile(r"arXiv:\s?([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5})", re.IGNORECASE)


def _split_gaps(gaps: list[str]) -> tuple[list[str], list[str]]:
    """Judge gaps -> (paper ids, textual queries). Ids skip re-retrieval entirely."""
    ids: list[str] = []
    queries: list[str] = []
    for g in gaps:
        found = _GAP_ID.findall(g)
        ids.extend(found)
        rest = _GAP_ID.sub("", g).strip(" ,;:-")
        if rest and not found:
            queries.append(g)
        elif rest and len(rest) > 12:
            queries.append(rest)
    return ids, queries


def _inject_gap_ids(store: Store, pool: dict[str, PoolNode], ids: list[str]) -> int:
    """Force-add judge-named papers (corpus-verified — a named id may be hallucinated)."""
    added = 0
    for aid in ids:
        if aid in pool:
            continue
        meta = store.meta_for(aid)
        if meta is None:
            continue
        title, year, cat, _ = meta
        pool[aid] = PoolNode(aid, title, year, cat, 0.85)
        added += 1
    return added


def _expand(
    store: Store,
    pool: dict[str, PoolNode],
    gap_vecs: list[tuple[str, list[float]]],
    tree: TopicTree,
    frontier_year: int,
) -> int:
    """Merge gap-query retrievals into the master pool (dedup, keep best score). Returns added."""
    from retrieval_hybrid import hybrid_pool

    from retrieval_refined import frontier_pull

    before = len(pool)
    for gq, gv in gap_vecs:
        gp = hybrid_pool(store, gv, gq, GAP_POOL)
        gp, _, _ = refined_pool(store, gv, gp, tree, frontier_year, target=GAP_POOL)
        gp.update(frontier_pull(store, gv, frontier_year, want=30))  # leaf-less recent
        for aid, node in gp.items():
            cur = pool.get(aid)
            if cur is None or node.score > cur.score:
                pool[aid] = node
    return len(pool) - before


def _digest_with_critiques(base_digest: str, critiques: dict[str, str]) -> str:
    if not critiques:
        return base_digest
    parts = [base_digest, "", "DEEP CRITIQUES (full-text peer review of key papers):"]
    for aid, txt in critiques.items():
        parts.append(f"arXiv:{aid}:\n{txt}")
    return "\n".join(parts)


def _fill_and_compose(
    store: Store,
    question: str,
    landmarks: list[Landmark],
    edges: list[Edge],
    eras: list[Era],
    spine: list[str],
    tens: list[Edge],
    schema: Schema,
    pool: dict[str, PoolNode],
    story: Story,
    extractions: dict[str, dict[str, str]],
    critiques: dict[str, str],
) -> tuple[str, str, list[str], list[str]]:
    """Extract (cached) -> digest (+critiques) -> SKELETON draft. Returns
    (digest, skeleton, grounded, off_digest).

    The in-loop draft's only reader is the judge, so it is a cheap per-section skeleton —
    the old monolithic 14k-token compose degenerated into repetition at pool ~1700, and the
    judge then produced garbage gaps. The deliverable is always compose_long."""
    abstracts = store.abstracts([lm.arxiv_id for lm in landmarks])
    new_ext = asyncio.run(
        extract_many([(lm.arxiv_id, lm.title) for lm in landmarks], schema, abstracts)
    )
    extractions.update(new_ext)
    base = build_digest(
        question,
        landmarks,
        edges,
        eras,
        spine,
        tens,
        extractions,
        schema,
        abstracts,
        story=story,
        pool=pool,
    )
    digest = _digest_with_critiques(base, critiques)
    report, grounded, off = compose_skeleton(
        question, landmarks, extractions, schema, abstracts, set(pool)
    )
    return digest, report, grounded, off


def _papers_json(
    landmarks: list[Landmark],
    grades: dict[str, Grade],
    summaries: dict[str, str],
    authors: dict[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for lm in landmarks:
        g = grades.get(lm.arxiv_id)
        rows.append(
            {
                "arxiv_id": lm.arxiv_id,
                "title": lm.title,
                "year": lm.year,
                "authors": authors.get(lm.arxiv_id),
                "url": f"https://arxiv.org/abs/{lm.arxiv_id}",
                "category": lm.category,
                "cosine": round(lm.score, 4),
                "role": lm.role,
                "relevance": lm.relevance,
                "reason": g.reason if g else None,
                "in_degree": lm.in_degree,
                "era": lm.era,
                "summary": summaries.get(lm.arxiv_id),
            }
        )
    return rows


def _coverage_misses(
    question: str, report: str, landmarks: list[Landmark]
) -> list[str]:
    """Landmarks whose title shares a question-NAMED entity yet went uncited — the
    hard-failure class. Entities = acronym-like tokens (>=2 uppercase letters: DPO, GRPO,
    JEPA, KV) — plain capitalized or hyphenated words are too generic and flood the list.
    """
    terms = {
        w.strip(",.()-:;").lower()
        for w in question.split()
        if sum(c.isupper() for c in w) >= 2
    }
    if not terms:
        return []
    out: list[str] = []
    for lm in landmarks:
        if f"arXiv:{lm.arxiv_id}" in report:
            continue
        title_words = {w.strip(",.()-:").lower() for w in lm.title.split()}
        if terms & title_words:
            out.append(lm.arxiv_id)
    return out


def _compile_pdf(out_dir: Path) -> bool:
    """Best-effort report.pdf via latexmk (present in the dev shell); never fails the run."""
    try:
        r = subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-quiet", "report.tex"],
            cwd=out_dir,
            capture_output=True,
            timeout=300,
        )
        ok = (out_dir / "report.pdf").exists()
        if not ok:
            print(f"[deep] latexmk exit {r.returncode}, no pdf", flush=True)
        return ok
    except Exception as e:  # noqa: BLE001
        print(f"[deep] pdf compile skipped: {type(e).__name__}", flush=True)
        return False


def run_deep(
    question: str,
    effort: str,
    rank: str = "ppr",
    no_cluster: bool = False,
    no_graph: bool = False,
    recency: float = 0.4,
    max_rounds: int = 4,
    critique_k: int = 8,
    figures: bool = True,
    no_frontier_pull: bool = False,
    out_root: Path | None = None,
    embed_mode: str = "sym",
    use_hyde: bool = True,
    no_grade: bool = False,
    fuse: bool = False,
    seed: str | None = None,
) -> dict[str, object]:
    """Run the judge-driven deep-research loop and write report.md / report.tex / run.json."""
    n_pool, target, m0, _ = TIERS[effort]
    now = datetime.now()
    # Seed mode mirrors pipeline.run: doc-shaped qtext from the paper, question derived if empty.
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
    qhash = hashlib.sha1(question.encode()).hexdigest()[:12]
    print(
        f"[deep] '{question}' effort={effort} rank={rank} recency={recency} "
        f"max_rounds={max_rounds} critique_k={critique_k} figures={figures} "
        f"embed={embed_mode} hyde={use_hyde} grade={not no_grade} fuse={fuse} seed={seed}",
        flush=True,
    )
    root = out_root or OUT
    cfg = (
        f"{effort}-{rank}-deep{max_rounds}-k{critique_k}-r{recency}-{embed_mode}"
        f"{'-hyde' if use_hyde else '-raw'}"
        f"{'-nocluster' if no_cluster else ''}{'-nograph' if no_graph else ''}"
        f"{'-nofig' if not figures else ''}{'-nofpull' if no_frontier_pull else ''}"
        f"{'-nograde' if no_grade else ''}{'-fuse' if fuse else ''}"
        f"{f'-seed{seed_slug(seed)}' if seed else ''}"
    )
    out_dir = root / _slug(question) / cfg
    timer = StageTimer(out_dir, question)

    with timer.stage("embed"):
        if not seed and use_hyde:
            qtext = hyde_query(question)  # router LLM — before freeing VRAM
        _free_router_vram()
        qvec = embed_query(qtext, mode=embed_mode)
        free_model()
    tree = TopicTree()

    # round 0 retrieval + grade + rank
    store = Store(PG_DSN, emb_space=embed_mode)
    with timer.stage("retrieve+grade"):
        p = retrieve_rank(
            store,
            qvec,
            question,
            tree,
            n_pool,
            target,
            m0,
            rank,
            no_cluster,
            no_graph,
            recency,
            now,
            no_frontier_pull,
            grade=not no_grade,
            fuse=fuse,
            seed=seed,
        )
    pool, fr, grades, story = p.pool, p.fr, p.grades, p.story
    landmarks, edges, eras, spine, tens = p.landmarks, p.edges, p.eras, p.spine, p.tens

    samples = [f"Title: {lm.title}" for lm in landmarks[:6]]
    schema = propose_schema(question, samples)
    print(f"[deep] schema({schema.hash}): {schema.names()}", flush=True)

    extractions: dict[str, dict[str, str]] = {}
    critiques: dict[str, str] = {}
    transcript: list[dict[str, object]] = []
    report, grounded, off_digest, digest = "", [], [], ""
    seen_gaps: set[str] = set()
    last_verdict: Verdict | None = None

    rounds_run = 0
    for r in range(max_rounds):
        rounds_run = r + 1
        m = min(m0 + M_GROW * r, M_MAX)
        if r > 0:  # re-rank the (now larger) pool with the grown budget
            with timer.stage("retrieve+grade"):
                p = rank_pool(
                    store,
                    pool,
                    m,
                    rank,
                    no_graph,
                    fr,
                    question=question,
                    grades=grades,
                    grade=not no_grade,
                    fuse=fuse,
                )
            landmarks, edges, eras, spine, tens, story = (
                p.landmarks,
                p.edges,
                p.eras,
                p.spine,
                p.tens,
                p.story,
            )
        print(
            f"[deep] round {rounds_run}: landmarks={len(landmarks)} pool={len(pool)}",
            flush=True,
        )

        with timer.stage("extract+compose"):
            digest, report, grounded, off_digest = _fill_and_compose(
                store,
                question,
                landmarks,
                edges,
                eras,
                spine,
                tens,
                schema,
                pool,
                story,
                extractions,
                critiques,
            )
        with timer.stage("judge"):
            frontier_now = sum(
                1 for lm in landmarks if lm.year and lm.year >= fr.frontier_year
            )
            ctx = retrieval_context(report, landmarks, fr.frontier_year, frontier_now)
            v = judge_report(
                question, report, digest, fr.frontier_year, r, max_rounds, context=ctx
            )
        last_verdict = v
        transcript.append(
            {
                "round": rounds_run,
                "saturated": v.saturated,
                "scores": v.scores,
                "gaps": v.gaps,
                "assessment": v.assessment,
            }
        )
        print(
            f"[deep] round {rounds_run} verdict: saturated={v.saturated} "
            f"mean_score={v.mean_score():.1f} gaps={v.gaps}",
            flush=True,
        )
        if v.saturated or r == max_rounds - 1:
            break
        fresh = [g for g in v.gaps if g.lower() not in seen_gaps]
        if not fresh:
            print("[deep] no fresh gaps; stopping", flush=True)
            break
        seen_gaps.update(g.lower() for g in fresh)
        gap_ids, gap_queries = _split_gaps(fresh)
        with timer.stage("expand"):
            added = _inject_gap_ids(store, pool, gap_ids)
            if gap_queries:
                gap_vecs = _embed_gaps(gap_queries, embed_mode)
                added += _expand(store, pool, gap_vecs, tree, fr.frontier_year)
        print(
            f"[deep] expanded pool by {added} "
            f"(ids: {len(gap_ids)}, queries: {len(gap_queries)})",
            flush=True,
        )

    # final depth pass: full-PDF critique of the top papers ...
    if critique_k > 0:
        top = sorted(landmarks, key=lambda lm: -lm.in_degree)[: critique_k // 2]
        recent = sorted(
            (lm for lm in landmarks if lm.year and lm.year >= fr.frontier_year),
            key=lambda lm: -(lm.year or 0),
        )[: critique_k - len(top)]
        crit_items = [(lm.arxiv_id, lm.title, lm.year) for lm in top + recent]
        print(f"[deep] critiquing {len(crit_items)} papers (full PDF) ...", flush=True)
        with timer.stage("critique"):
            critiques = asyncio.run(critique_many(crit_items, question, qhash))
        print(f"[deep] critiqued {len(critiques)}", flush=True)

    # ... then the FINAL deliverable: sectioned long-form compose (one focused call per
    # themed section, integrating the critiques) so the review is long AND analytical.
    abstracts_final = store.abstracts([lm.arxiv_id for lm in landmarks])
    authors_final = store.authors([lm.arxiv_id for lm in landmarks])
    store.close()
    extractions.update(
        asyncio.run(
            extract_many(
                [(lm.arxiv_id, lm.title) for lm in landmarks], schema, abstracts_final
            )
        )
    )
    print("[deep] composing long-form review (sectioned) ...", flush=True)
    with timer.stage("compose-long"):
        report, grounded, off_digest = compose_long(
            question,
            landmarks,
            edges,
            tens,
            extractions,
            critiques,
            schema,
            abstracts_final,
            set(pool),
            story=story,
        )
    digest = build_digest(
        question,
        landmarks,
        edges,
        eras,
        spine,
        tens,
        extractions,
        schema,
        abstracts_final,
        story=story,
        pool=pool,
    )
    digest = _digest_with_critiques(digest, critiques)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_pool(out_dir, pool, grades, {lm.arxiv_id for lm in landmarks})
    with timer.stage("viz"):
        viz_meta = render_story(question, landmarks, edges, story, pool, out_dir)

    # reader pre-summaries -> papers.json (the cohort artifact the QA tools serve).
    with timer.stage("summaries"):
        summaries = asyncio.run(
            summarize_many(
                [(lm.arxiv_id, lm.title) for lm in landmarks], abstracts_final
            )
        )
    papers = _papers_json(landmarks, grades, summaries, authors_final)
    _ = (out_dir / "papers.json").write_text(
        json.dumps(papers, indent=1), encoding="utf-8"
    )

    # P3 vision: crop + caption key figures (report-cited, role-gated) -> inline + gallery.
    # Runs after compose so the vision model is swapped in last.
    figs: dict[str, dict[str, object]] = {}
    if figures:
        fig_items = pick_figure_items(landmarks, report, fr.frontier_year, cap=14)
        print(
            f"[deep] reading figures for {len(fig_items)} papers (vision) ...",
            flush=True,
        )
        with timer.stage("figures"):
            figs = asyncio.run(figures_for(fig_items, out_dir, top_n=len(fig_items)))
        print(f"[deep] captioned {len(figs)} figures", flush=True)
        report = attach_figures(report, figs, landmarks)

    frontier = sum(1 for lm in landmarks if lm.year and lm.year >= fr.frontier_year)
    # compose_long's intro already opens with an H1 title; header is just the run banner.
    header = (
        f"*deep research · {rounds_run} round(s) · {len(landmarks)} landmarks · "
        f"frontier≥{fr.frontier_year}: {frontier} · {len(critiques)} full-PDF critiques · "
        f"grounded {len(grounded)} · off-digest {len(off_digest)}*\n\n"
    )
    lm_meta: list[dict[str, object]] = []
    for lm in landmarks:
        d: dict[str, object] = asdict(lm)
        d["authors"] = authors_final.get(lm.arxiv_id)
        lm_meta.append(d)
    _ = (out_dir / "report.md").write_text(
        linkify(header + graph_section(viz_meta) + report), encoding="utf-8"
    )
    _ = (out_dir / "digest.txt").write_text(digest, encoding="utf-8")
    abstract = last_verdict.assessment if last_verdict else ""
    tex, bib = to_tex(question, report, lm_meta, abstract)
    _ = (out_dir / "report.tex").write_text(tex, encoding="utf-8")
    _ = (out_dir / "refs.bib").write_text(bib, encoding="utf-8")
    _ = (out_dir / "judge_transcript.json").write_text(
        json.dumps(transcript, indent=1), encoding="utf-8"
    )
    with timer.stage("pdf"):
        pdf_ok = _compile_pdf(out_dir)
    meta: dict[str, object] = {
        "question": question,
        "mode": "deep_loop",
        "effort": effort,
        "rank": rank,
        "recency": recency,
        "max_rounds": max_rounds,
        "rounds_run": rounds_run,
        "critique_k": critique_k,
        "n_critiques": len(critiques),
        "figures_enabled": figures,
        "no_frontier_pull": no_frontier_pull,
        "embed_mode": embed_mode,
        "use_hyde": use_hyde,
        "grade": not no_grade,
        "fuse": fuse,
        "seed": seed,
        "n_figures": len(figs),
        "figures": figs,
        "graph": viz_meta,
        "pdf": pdf_ok,
        "config": cfg,
        "schema": schema.fields,
        "n_pool": len(pool),
        "n_landmarks": len(landmarks),
        "n_edges": len(edges),
        "frontier_year": fr.frontier_year,
        "frontier_count": frontier,
        "grounded": grounded,
        "off_digest": off_digest,
        "coverage_misses": _coverage_misses(question, report, landmarks),
        "report_chars": len(report),
        "judge_scores_final": last_verdict.scores if last_verdict else {},
        "timings": timer.timings(),
        "landmarks": lm_meta,
    }
    _ = (out_dir / "run.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"[deep] done -> {out_dir}/report.md ({len(report)} chars)", flush=True)
    return meta
