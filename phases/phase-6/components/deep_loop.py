"""Judge-driven deep-research loop (the deep tier's control flow).

Round 0 retrieves + ranks + composes a draft. Then each round a thinking judge (-code) reads
the draft and either declares it SATURATED or returns concrete gap queries; the loop embeds
those gaps, retrieves more papers, merges them, re-ranks (growing the landmark budget), and
recomposes. The JUDGE owns termination — `max_rounds` is only an upper cap (set it large to
"run until saturated"). Before the final compose, the top papers get a full-PDF critique
(`critique_k`) folded into the digest. Emits report.md + report.tex + run.json + the judge
transcript.

VRAM is sequenced for one 3090: free the router LLM before each nomic embed, free nomic
before each Gemma stage (extract / compose / judge / critique), exactly as the single-pass
path does.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from _common import PG_DSN
from compose_report import build_digest, compose
from critique import critique_many
from extract import extract_many
from figures import figures_for
from judge import Verdict, judge_report
from latex_report import to_tex
from long_compose import compose_long
from pipeline import (
    OUT,
    TIERS,
    _free_router_vram,
    _slug,
    hyde_query,
    rank_pool,
    retrieve_rank,
)
from retrieval_refined import refined_pool
from retrieve import embed_query, free_model
from store import Store
from schema import Schema, propose_schema
from subgraph import Edge, Era, Landmark, PoolNode
from topic_anchor import TopicTree

GAP_POOL = 150  # per-gap retrieval breadth
M_GROW = 40  # landmark budget growth per round (broaden coverage)
M_MAX = 260  # hard cap on landmark count
COMPOSE_TOKENS = 14000  # large budget: thinking-on -code writes a long review


def _embed_gaps(
    gaps: list[str], embed_mode: str = "sym"
) -> list[tuple[str, list[float]]]:
    """Embed gap queries in one nomic load, then free it (hand VRAM back to Gemma)."""
    _free_router_vram()
    out = [(g, embed_query(g, mode=embed_mode)) for g in gaps]
    free_model()
    return out


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
    pool_ids: set[str],
    extractions: dict[str, dict[str, str]],
    critiques: dict[str, str],
) -> tuple[str, str, list[str], list[str]]:
    """Extract (cached) -> digest (+critiques) -> compose (thinking on). Returns
    (digest, report, grounded, off_digest)."""
    abstracts = store.abstracts([lm.arxiv_id for lm in landmarks])
    new_ext = asyncio.run(
        extract_many([(lm.arxiv_id, lm.title) for lm in landmarks], schema, abstracts)
    )
    extractions.update(new_ext)
    base = build_digest(
        question, landmarks, edges, eras, spine, tens, extractions, schema, abstracts
    )
    digest = _digest_with_critiques(base, critiques)
    report, grounded, off = compose(
        question, digest, pool_ids, max_tokens=COMPOSE_TOKENS, think=True
    )
    return digest, report, grounded, off


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
) -> dict[str, object]:
    """Run the judge-driven deep-research loop and write report.md / report.tex / run.json."""
    n_pool, target, m0, _ = TIERS[effort]
    now = datetime.now()
    qhash = hashlib.sha1(question.encode()).hexdigest()[:12]
    print(
        f"[deep] '{question}' effort={effort} rank={rank} recency={recency} "
        f"max_rounds={max_rounds} critique_k={critique_k} figures={figures} "
        f"embed={embed_mode} hyde={use_hyde}",
        flush=True,
    )

    qtext = (
        hyde_query(question) if use_hyde else question
    )  # router LLM — before freeing VRAM
    _free_router_vram()
    qvec = embed_query(qtext, mode=embed_mode)
    free_model()
    tree = TopicTree()

    # round 0 retrieval + rank
    store = Store(PG_DSN, emb_space=embed_mode)
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
    )
    pool, fr = p.pool, p.fr
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
            p = rank_pool(store, pool, m, rank, no_graph, fr)
            landmarks, edges, eras, spine, tens = (
                p.landmarks,
                p.edges,
                p.eras,
                p.spine,
                p.tens,
            )
        print(
            f"[deep] round {rounds_run}: landmarks={len(landmarks)} pool={len(pool)}",
            flush=True,
        )

        digest, report, grounded, off_digest = _fill_and_compose(
            store,
            question,
            landmarks,
            edges,
            eras,
            spine,
            tens,
            schema,
            set(pool),
            extractions,
            critiques,
        )
        v = judge_report(question, report, digest, fr.frontier_year, r, max_rounds)
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
        gap_vecs = _embed_gaps(fresh, embed_mode)
        added = _expand(store, pool, gap_vecs, tree, fr.frontier_year)
        print(f"[deep] expanded pool by {added} (gaps: {len(fresh)})", flush=True)

    # final depth pass: full-PDF critique of the top papers ...
    if critique_k > 0:
        top = sorted(landmarks, key=lambda lm: -lm.in_degree)[: critique_k // 2]
        recent = sorted(
            (lm for lm in landmarks if lm.year and lm.year >= fr.frontier_year),
            key=lambda lm: -(lm.year or 0),
        )[: critique_k - len(top)]
        crit_items = [(lm.arxiv_id, lm.title, lm.year) for lm in top + recent]
        print(f"[deep] critiquing {len(crit_items)} papers (full PDF) ...", flush=True)
        critiques = asyncio.run(critique_many(crit_items, question, qhash))
        print(f"[deep] critiqued {len(critiques)}", flush=True)

    # ... then the FINAL deliverable: sectioned long-form compose (one focused call per
    # themed section, integrating the critiques) so the review is long AND analytical.
    abstracts_final = store.abstracts([lm.arxiv_id for lm in landmarks])
    store.close()
    extractions.update(
        asyncio.run(
            extract_many(
                [(lm.arxiv_id, lm.title) for lm in landmarks], schema, abstracts_final
            )
        )
    )
    print("[deep] composing long-form review (sectioned) ...", flush=True)
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
    )
    digest = _digest_with_critiques(digest, critiques)

    # output dir (needed before figures so vision PNGs land beside the report)
    root = out_root or OUT
    cfg = (
        f"{effort}-{rank}-deep{max_rounds}-k{critique_k}-r{recency}-{embed_mode}"
        f"{'-hyde' if use_hyde else '-raw'}"
        f"{'-nocluster' if no_cluster else ''}{'-nograph' if no_graph else ''}"
        f"{'-nofig' if not figures else ''}{'-nofpull' if no_frontier_pull else ''}"
    )
    out_dir = root / _slug(question) / cfg
    out_dir.mkdir(parents=True, exist_ok=True)

    # P3 vision: crop + caption key figures (top in-degree + most recent) -> Key Figures gallery.
    # Runs after compose so the vision model is swapped in last. report already carries the prose.
    figs: dict[str, dict[str, object]] = {}
    if figures:
        by_indeg = sorted(landmarks, key=lambda lm: -lm.in_degree)[:8]
        by_recent = sorted(
            (lm for lm in landmarks if lm.year and lm.year >= fr.frontier_year),
            key=lambda lm: -(lm.year or 0),
        )[:6]
        seen_f: set[str] = set()
        fig_items: list[tuple[str, str]] = []
        for lm in by_indeg + by_recent:
            if lm.arxiv_id not in seen_f:
                seen_f.add(lm.arxiv_id)
                fig_items.append((lm.arxiv_id, lm.title))
        print(
            f"[deep] reading figures for {len(fig_items)} papers (vision) ...",
            flush=True,
        )
        figs = asyncio.run(figures_for(fig_items, out_dir, top_n=len(fig_items)))
        print(f"[deep] captioned {len(figs)} figures", flush=True)
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

    frontier = sum(1 for lm in landmarks if lm.year and lm.year >= fr.frontier_year)
    # compose_long's intro already opens with an H1 title; header is just the run banner.
    header = (
        f"*deep research · {rounds_run} round(s) · {len(landmarks)} landmarks · "
        f"frontier≥{fr.frontier_year}: {frontier} · {len(critiques)} full-PDF critiques · "
        f"grounded {len(grounded)} · off-digest {len(off_digest)}*\n\n"
    )
    lm_meta = [asdict(lm) for lm in landmarks]
    _ = (out_dir / "report.md").write_text(header + report, encoding="utf-8")
    _ = (out_dir / "digest.txt").write_text(digest, encoding="utf-8")
    abstract = last_verdict.assessment if last_verdict else ""
    tex, bib = to_tex(question, report, lm_meta, abstract)
    _ = (out_dir / "report.tex").write_text(tex, encoding="utf-8")
    _ = (out_dir / "refs.bib").write_text(bib, encoding="utf-8")
    _ = (out_dir / "judge_transcript.json").write_text(
        json.dumps(transcript, indent=1), encoding="utf-8"
    )
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
        "n_figures": len(figs),
        "figures": figs,
        "config": cfg,
        "schema": schema.fields,
        "n_pool": len(pool),
        "n_landmarks": len(landmarks),
        "n_edges": len(edges),
        "frontier_year": fr.frontier_year,
        "frontier_count": frontier,
        "grounded": grounded,
        "off_digest": off_digest,
        "report_chars": len(report),
        "judge_scores_final": last_verdict.scores if last_verdict else {},
        "landmarks": lm_meta,
    }
    _ = (out_dir / "run.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"[deep] done -> {out_dir}/report.md ({len(report)} chars)", flush=True)
    return meta
