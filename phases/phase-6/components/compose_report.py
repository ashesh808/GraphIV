"""P2 / R3 — compose the filled schemas + graph structure into one long report.

Reduce stage: a per-paper block (schema fields + citation relations), ordered chronologically
via the induced subgraph's eras/main-path, narrated by Gemma-4-26B-Code into a grounded,
story-like literature review. References are arXiv ids (pdf:page anchors arrive with P3 figures).
"""

from __future__ import annotations

import asyncio


from llm import NO_THINK, THINK, chat  # noqa: E402
from narrate import _relations, check_citations  # noqa: E402
from schema import Schema  # noqa: E402
from subgraph import Edge, Era, Landmark  # noqa: E402

NARRATOR = "Gemma-4-26B-Code"

_SYS = (
    "You are a research analyst writing a thorough, chronological literature review answering "
    "the user's question, grounded ONLY in the digest provided.\n"
    "- Tell the development as a story: origins -> key advances -> current frontier, using the "
    "ERAS and MAIN PATH for ordering (no awkward middle: you know the start and the present).\n"
    "- For every claim cite the paper as arXiv:<id>. Use the per-paper extracted fields for "
    "specifics (methods, datasets, numbers). Never invent an id or a fact not in the digest.\n"
    "- Organize with headers; compare and contrast papers; surface tensions/open problems from "
    "the compare/critique/motivate edges. If coverage is thin somewhere, say so plainly.\n"
    "- Be detailed and specific; length should match the evidence."
)


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
) -> str:
    lm_ids = {lm.arxiv_id for lm in landmarks}
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
    parts.append("PAPERS (chronological; extracted fields per paper):")
    for lm in ordered:
        yr = lm.year if lm.year is not None else "?"
        cat = f" [{lm.category}]" if lm.category else ""
        parts.append(
            f'arXiv:{lm.arxiv_id} ({yr}) "{lm.title}"{cat} '
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
        parts.append(f"    relations: {_relations(lm, edges, lm_ids)}")
    parts.append("")
    parts.append("MAIN PATH (oldest -> newest):")
    if spine:
        parts.append(
            "  "
            + " -> ".join(f"arXiv:{i} ({by_id[i].year})" for i in spine if i in by_id)
        )
    else:
        parts.append("  (no single dominant chain)")
    parts.append("")
    parts.append("TENSIONS / OPEN PROBLEMS (compare/critique/motivate edges):")
    if tens:
        for e in tens:
            pol = f" [{e.polarity}]" if e.polarity else ""
            parts.append(f"  arXiv:{e.src} {e.intent}{pol} arXiv:{e.dst}")
    else:
        parts.append("  (none surfaced)")
    return "\n".join(parts)


def compose(
    question: str,
    digest: str,
    pool_ids: set[str],
    max_tokens: int = 9000,
    think: bool = False,
) -> tuple[str, list[str], list[str]]:
    """Narrate the digest -> (report markdown, grounded ids, off-digest ids).

    `think` enables the -code model's reasoning channel (deep path); the single-pass path
    keeps it off, since Gemma-4 otherwise burns the budget reasoning and returns empty —
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
    grounded, off_digest = check_citations(report, pool_ids)
    return report, grounded, off_digest
