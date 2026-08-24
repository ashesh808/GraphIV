"""
Compose the filled schemas and the graph structure into one digest and draft

The digest is a NODES table plus an ADJACENCY list grouped by citation intent
That representation won the 03-07 pairwise comparison against the flat alternatives
"""

from __future__ import annotations

import asyncio

from graphiv.core.llm import NO_THINK, THINK, chat
from graphiv.core.models import Edge, Era, Landmark, PoolNode
from graphiv.generate.narrate import ground_report
from graphiv.generate.schema import Schema
from graphiv.generate.story import Story, story_digest_block

NARRATOR = "Gemma-4-26B"

_SYS = (
    "You are a research analyst writing a thorough, chronological literature review answering "
    "the user's question, grounded ONLY in the digest provided.\n"
    "- Tell the development as a story: origins -> key advances -> current frontier, using the "
    "ERAS and MAIN PATH for ordering (no awkward middle: you know the start and the present).\n"
    "- For every claim cite the paper as arXiv:<id>. Use the per-paper extracted fields for "
    "specifics (methods, datasets, numbers). Never invent an id or a fact not in the digest.\n"
    "- Organize with headers; compare and contrast papers; surface tensions/open problems from "
    "the compare/critique/motivate edges. If coverage is thin somewhere, say so plainly.\n"
    "- Stay specific to THIS topic: do NOT spend a section or paragraph on generic, ubiquitous "
    "background (e.g. a 'rise of transformers' arc, general-purpose backbones, optimizers, or base "
    "language models) merely because such papers are widely cited. Reference a shared general-purpose "
    "method only briefly and only where it is directly load-bearing for this specific question; spend "
    "the review on the topic's OWN methods, results, and lineage.\n"
    "- Be detailed and specific; length should match the evidence."
)


K_ADJ = 6  # per-intent out-citation cap per node line


def _adjacency_lines(ordered: list[Landmark], edges: list[Edge]) -> list[str]:
    """
    03-07 adjacency-by-intent encoding: each paper -> papers it cites, grouped by intent
    """
    lm_ids = {lm.arxiv_id for lm in ordered}
    out_by: dict[str, dict[str, list[str]]] = {a: {} for a in lm_ids}
    for e in edges:
        if e.src in lm_ids and e.dst in lm_ids and e.src != e.dst:
            out_by[e.src].setdefault(e.intent or "cites", []).append(f"arXiv:{e.dst}")
    lines = ["ADJACENCY (each paper -> papers it cites, grouped by intent):"]
    for lm in ordered:
        grp = out_by[lm.arxiv_id]
        parts = [f"{k}[{', '.join(v[:K_ADJ])}]" for k, v in grp.items()]
        lines.append(f"arXiv:{lm.arxiv_id}: {' '.join(parts) or '(no out-citations in-graph)'}")
    return lines


def build_digest(
    question: str,
    landmarks: list[Landmark],
    edges: list[Edge],
    eras: list[Era],
    spine: list[str],
    tens: list[Edge],
    extractions: dict[str, dict[str, str]],
    schema: Schema,
    abstracts: dict[str, str],
    story: Story | None = None,
    pool: dict[str, PoolNode] | None = None,
) -> str:
    """
    Assemble the NODES table, the intent-grouped adjacency and the story blocks
    """
    by_id = {lm.arxiv_id: lm for lm in landmarks}
    ordered = sorted(landmarks, key=lambda lm: (lm.year or 0, -lm.in_degree))

    parts: list[str] = [
        f"QUESTION: {question}",
        "",
        f"SCHEMA FIELDS: {schema.names()}",
        "",
    ]
    parts.append("ERAS:")
    for era in eras:
        parts.append(f"  [{era.index}] {era.label}: {era.year_lo}-{era.year_hi}")
    parts.append("")
    parts.append("NODES (chronological; role + extracted fields per paper):")
    for lm in ordered:
        yr = lm.year if lm.year is not None else "?"
        cat = f" [{lm.category}]" if lm.category else ""
        role = f" [{lm.role}]" if lm.role else ""
        parts.append(
            f'arXiv:{lm.arxiv_id} ({yr}){role} "{lm.title}"{cat} '
            f"(cited-by {lm.in_degree} in-topic, era {lm.era})"
        )
        ext = extractions.get(lm.arxiv_id)
        if ext:
            for name in schema.names():
                val = ext.get(name)
                if val and val.lower() != "n/a":
                    parts.append(f"    {name}: {val}")
        else:
            ab = (abstracts.get(lm.arxiv_id) or "").strip()
            if ab:
                parts.append(f"    abstract: {ab[:300]}")
    parts.append("")
    parts.extend(_adjacency_lines(ordered, edges))
    parts.append("")
    if story is not None and pool is not None:
        parts.append(story_digest_block(story, by_id, pool))
    else:
        parts.append("MAIN PATH (oldest -> newest):")
        if spine:
            parts.append(
                "  " + " -> ".join(f"arXiv:{i} ({by_id[i].year})" for i in spine if i in by_id)
            )
        else:
            parts.append("  (no single dominant chain)")
    parts.append("")
    parts.append("TENSIONS / OPEN PROBLEMS (compare/critique/motivate edges):")
    if tens:
        for e in tens:
            parts.append(f"  arXiv:{e.src} {e.intent} arXiv:{e.dst}")
    else:
        parts.append("  (none surfaced)")
    return "\n".join(parts)


_SKEL_SYS = (
    "You draft ONE section of a literature-review SKELETON: a ~120-word synopsis of what the "
    "section will argue, followed by a CLAIMS list — one line per paper, 'arXiv:<id> — <the "
    "single most important claim/number this paper contributes>'. Cover every paper given. "
    "No prose beyond the synopsis; no headings other than '## <title>'."
)


def compose_skeleton(
    question: str,
    landmarks: list[Landmark],
    extractions: dict[str, dict[str, str]],
    schema: Schema,
    abstracts: dict[str, str],
    pool_ids: set[str],
    top_n: int = 120,
    per_section: int = 20,
) -> tuple[str, list[str], list[str]]:
    """
    Cheap structured draft for the judge's mid-loop reads (never the deliverable)

        Era-bucketed sections over the top-`top_n` landmarks by score; each section is one small
        thinking-off call (collapse-proof, the monolithic 14k-token compose degenerated into
        repetition at pool ~1700). Returns (skeleton_md, grounded, off_digest).
    """
    top = sorted(landmarks, key=lambda lm: -lm.score)[:top_n]
    top.sort(key=lambda lm: (lm.year or 0))
    chunks = [top[i : i + per_section] for i in range(0, len(top), per_section)]
    parts: list[str] = []
    for chunk in chunks:
        lines: list[str] = []
        for lm in chunk:
            ext = extractions.get(lm.arxiv_id) or {}
            fields = "; ".join(f"{k}: {v}" for k, v in ext.items() if v and v.lower() != "n/a")
            fallback = (abstracts.get(lm.arxiv_id) or "")[:200]
            lines.append(
                f'arXiv:{lm.arxiv_id} ({lm.year or "?"}) "{lm.title[:80]}" :: '
                f"{fields[:400] or fallback}"
            )
        yrs = [lm.year for lm in chunk if lm.year]
        title = f"{min(yrs)}-{max(yrs)}" if yrs else "undated"
        user = f"Review question: {question}\nSection title: {title}\n\nPAPERS:\n" + "\n".join(
            lines
        )
        text, _, _ = asyncio.run(chat(NARRATOR, _SKEL_SYS, user, 0.3, 900, NO_THINK))
        if text.strip():
            parts.append(text.strip())
    skeleton = "\n\n".join(parts)
    skeleton, grounded, off_digest, _, _ = ground_report(skeleton, pool_ids)
    return skeleton, grounded, off_digest


def compose(
    question: str,
    digest: str,
    pool_ids: set[str],
    max_tokens: int = 9000,
    think: bool = False,
) -> tuple[str, list[str], list[str]]:
    """
    Narrate the digest -> (report markdown, grounded ids, off-digest ids)

        `think` enables the large-context model's reasoning channel on the deep path, and
        keeps it off, since Gemma-4 otherwise burns the budget reasoning and returns empty ,
        so the deep path pairs think=True with a larger `max_tokens`.
    """
    user = f"Write the literature review answering: {question}\n\nDIGEST:\n{digest}"
    report, _, _ = asyncio.run(
        chat(
            NARRATOR,
            _SYS,
            user,
            0.4,
            max_tokens,
            extra_body=THINK if think else NO_THINK,
        )
    )
    report, grounded, off_digest, _, _ = ground_report(report, pool_ids)
    return report, grounded, off_digest
