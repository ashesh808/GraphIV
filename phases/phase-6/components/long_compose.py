"""Sectioned long-form composition for the deep path.

A single narrate call self-limits to ~1k words regardless of how rich the digest is, so the
deep review came out short and the per-paper critiques never surfaced as analysis. This
composes the review the way a person writes one: plan an outline (themed sections, each owning
a set of papers), then write EACH section in its own focused call — integrating that section's
extracted fields + full-PDF critiques + in-topic relations — then frame it with an intro and an
open-problems close. Many focused calls => a long, genuinely analytical literature review.

Thinking ON, routed to the -code model (large ctx + MTP). Grounding is post-checked on the
assembled whole.
"""

from __future__ import annotations

import asyncio
import re

from llm import THINK, chat, parse_json
from narrate import _relations, check_citations
from schema import Schema
from subgraph import Edge, Landmark

NARRATOR = "Gemma-4-26B-Code"

# modern arXiv id whose month field is out of 01-12 (e.g. 2300.00352) -> a hallucinated id.
_MODERN_ID = re.compile(
    r"\s*[\[(]?\s*arXiv:\s?(\d{2})(\d{2})\.\d{4,5}\s*[\])]?", re.IGNORECASE
)


def _drop_invalid_ids(report: str) -> str:
    """Remove citations to malformed modern arXiv ids (invalid month) and tidy the gaps.

    Legacy ids (archive/YYMMNNN) use a different shape and are left untouched.
    """
    out: list[str] = []
    last = 0
    for m in _MODERN_ID.finditer(report):
        if "01" <= m.group(2) <= "12":
            continue  # valid month -> keep
        out.append(report[last : m.start()])
        last = m.end()
    out.append(report[last:])
    s = "".join(out)
    s = re.sub(r"\(\s*\)|\[\s*\]", "", s)  # empty brackets left behind
    s = re.sub(r" {2,}", " ", s)
    s = re.sub(r"\s+([.,;])", r"\1", s)  # space before punctuation
    return s


_OUTLINE_SYS = (
    "You are organizing a literature review. Given the question and a list of papers "
    "(id, year, title), propose 5-8 thematic sections that tell the story origins -> key "
    "advances -> current frontier. Assign each paper id to exactly one section; every section "
    "needs >=3 papers; order sections logically. Make at least one section about the LATEST "
    "(most recent years) work.\n"
    'Output ONLY JSON: [{"title":"..","ids":["id1","id2",..]}, ...].'
)

_SECTION_SYS = (
    "You are writing ONE section of a rigorous literature review, grounded ONLY in the papers "
    "given. Requirements:\n"
    "- Start with '## <the section title>'.\n"
    "- 350-600 words. Discuss the papers' actual contributions (use the extracted fields and "
    "numbers), and COMPARE/CONTRAST them — do not just list.\n"
    "- Where a CRITIQUE is provided, weave in its strengths/weaknesses as real critical "
    "analysis (this is the depth the review is judged on).\n"
    "- Cite every claim inline as arXiv:<id>. Never invent an id or a fact not provided."
)

_INTRO_SYS = (
    "Write the opening of a literature review answering the question: a 2-3 paragraph "
    "introduction that frames the problem, why it matters, and the arc the review will trace "
    "(origins -> frontier). Ground claims in the provided section titles; cite arXiv:<id> only "
    "if given. Start with '# <a descriptive review title>'. No bullet lists."
)

_CLOSE_SYS = (
    "Write the closing of a literature review: a 'Tensions and Open Problems' section followed "
    "by a short 'Outlook' paragraph on the current frontier and where the field is heading.\n"
    "- SYNTHESIZE 2-3 genuine debates in flowing prose: name the disagreement, explain BOTH "
    "sides, and cite the papers (arXiv:<id>) that take each position. Each tension is a "
    "paragraph of argument.\n"
    "- Do NOT output raw citation pairs or lists of bare ids (no 'X critiques Y, including A, B, "
    "C'); every id must sit inside a real claim about what the paper argues.\n"
    "Start with '## Tensions and Open Problems'. Be specific and forward-looking."
)
# continuation when a section is cut off at the token cap (no closing punctuation)
_CONT_SYS = (
    "Continue the literature-review section seamlessly from exactly where the draft stops. "
    "Do NOT repeat any text and do NOT add a heading. Cite arXiv:<id> for claims. Finish the "
    "current thought and bring the section to a clean close."
)


def _paper_block(
    lm: Landmark,
    edges: list[Edge],
    lm_ids: set[str],
    extractions: dict[str, dict[str, str]],
    critiques: dict[str, str],
    schema: Schema,
    abstracts: dict[str, str],
) -> str:
    yr = lm.year if lm.year is not None else "?"
    out = [
        f'arXiv:{lm.arxiv_id} ({yr}) "{lm.title}" (cited-by {lm.in_degree} in-topic)'
    ]
    ext = extractions.get(lm.arxiv_id)
    if ext:
        for name in schema.names():
            val = ext.get(name)
            if val and val.lower() != "n/a":
                out.append(f"    {name}: {val}")
    else:
        ab = (abstracts.get(lm.arxiv_id) or "").strip()
        if ab:
            out.append(f"    abstract: {ab[:300]}")
    if lm.arxiv_id in critiques:
        out.append(f"    CRITIQUE: {critiques[lm.arxiv_id]}")
    out.append(f"    relations: {_relations(lm, edges, lm_ids)}")
    return "\n".join(out)


async def _section(
    title: str,
    ids: list[str],
    by_id: dict[str, Landmark],
    edges: list[Edge],
    lm_ids: set[str],
    extractions: dict[str, dict[str, str]],
    critiques: dict[str, str],
    schema: Schema,
    abstracts: dict[str, str],
    question: str,
) -> str:
    blocks = [
        _paper_block(by_id[i], edges, lm_ids, extractions, critiques, schema, abstracts)
        for i in ids
        if i in by_id
    ]
    if not blocks:
        return ""
    user = (
        f"Review question: {question}\nSection title: {title}\n\nPAPERS:\n"
        + "\n".join(blocks)
    )
    text, _, _ = await chat(NARRATOR, _SECTION_SYS, user, 0.4, 4000, extra_body=THINK)
    out = text.strip()
    # retry-on-thin: thinking occasionally consumes the budget and returns a stub; force a
    # substantive second pass (thinking off, lower temperature) so no section is near-empty.
    if len(out) < 400:
        retry_user = (
            user + "\n\nThe section MUST be at least 350 words of substantive analysis "
            "starting with '## "
            + title
            + "'. Discuss every paper above; do not be brief."
        )
        text2, _, _ = await chat(NARRATOR, _SECTION_SYS, retry_user, 0.3, 4000)
        if len(text2.strip()) > len(out):
            out = text2.strip()
    # continuation: if the section was cut at the token cap (no sentence-final char), finish it.
    if len(out) > 600 and out[-1] not in ".!?\"')]":
        cont_user = (
            user
            + "\n\nThe draft below was cut off. Continue from where it stops:\n\n"
            + out[-1500:]
        )
        cont, _, _ = await chat(NARRATOR, _CONT_SYS, cont_user, 0.4, 1500)
        if cont.strip():
            out = out + " " + cont.strip()
    return out


def _plan_outline(
    question: str, landmarks: list[Landmark]
) -> list[tuple[str, list[str]]]:
    """Ask the model for a themed outline; fall back to era buckets if it fails."""
    idx = "\n".join(
        f'{lm.arxiv_id} ({lm.year if lm.year is not None else "?"}) {lm.title}'
        for lm in landmarks
    )
    user = f"QUESTION: {question}\n\nPAPERS:\n{idx}"
    try:
        text, _, _ = asyncio.run(
            chat(NARRATOR, _OUTLINE_SYS, user, 0.2, 3000, extra_body=THINK)
        )
        obj = parse_json(text)
    except Exception:  # noqa: BLE001
        obj = None
    sections: list[tuple[str, list[str]]] = []
    valid = {lm.arxiv_id for lm in landmarks}
    if isinstance(obj, list):
        for item in obj:  # pyright: ignore[reportAny]
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()  # pyright: ignore[reportAny]
            raw = item.get("ids") or []  # pyright: ignore[reportAny]
            ids = (
                [str(i) for i in raw if str(i) in valid]
                if isinstance(raw, list)
                else []
            )
            if title and len(ids) >= 2:
                sections.append((title, ids))
    if sections:
        return sections
    # fallback: bucket by era index
    buckets: dict[int, list[str]] = {}
    for lm in landmarks:
        buckets.setdefault(lm.era, []).append(lm.arxiv_id)
    labels = {0: "Origins", 1: "Key Advances", 2: "Current Frontier"}
    return [
        (labels.get(e, f"Era {e}"), ids) for e, ids in sorted(buckets.items()) if ids
    ]


def compose_long(
    question: str,
    landmarks: list[Landmark],
    edges: list[Edge],
    tens: list[Edge],
    extractions: dict[str, dict[str, str]],
    critiques: dict[str, str],
    schema: Schema,
    abstracts: dict[str, str],
    pool_ids: set[str],
) -> tuple[str, list[str], list[str]]:
    """Outline -> per-section deep compose -> intro + close. Returns (report, grounded, off)."""
    by_id = {lm.arxiv_id: lm for lm in landmarks}
    lm_ids = set(by_id)
    outline = _plan_outline(question, landmarks)
    print(f"[long] outline: {[t for t, _ in outline]}", flush=True)

    # sections (sequential: one big -code model resident on the single 3090)
    section_texts: list[str] = []
    for title, ids in outline:
        txt = asyncio.run(
            _section(
                title,
                ids,
                by_id,
                edges,
                lm_ids,
                extractions,
                critiques,
                schema,
                abstracts,
                question,
            )
        )
        if txt:
            section_texts.append(txt)
        print(f"[long]   section '{title}': {len(txt)} chars", flush=True)

    # intro
    intro_user = f"QUESTION: {question}\n\nSECTION TITLES:\n" + "\n".join(
        f"- {t}" for t, _ in outline
    )
    intro, _, _ = asyncio.run(
        chat(NARRATOR, _INTRO_SYS, intro_user, 0.4, 1500, extra_body=THINK)
    )
    if (
        not intro.strip()
    ):  # thinking budget occasionally eats the intro -> retry without it
        intro, _, _ = asyncio.run(chat(NARRATOR, _INTRO_SYS, intro_user, 0.4, 1500))

    # close (tensions + outlook). Give the edges WITH titles so the model can synthesize a
    # real argument instead of parroting "src intent dst" pairs.
    title_of = {lm.arxiv_id: lm.title for lm in landmarks}
    tens_lines = [
        f'arXiv:{e.src} ("{title_of.get(e.src, "?")[:60]}") {e.intent} '
        f'arXiv:{e.dst} ("{title_of.get(e.dst, "?")[:60]}")'
        for e in tens[:20]
    ]
    recent = sorted(
        (lm for lm in landmarks if lm.year), key=lambda lm: -(lm.year or 0)
    )[:12]
    recent_lines = [f'arXiv:{lm.arxiv_id} ({lm.year}) "{lm.title}"' for lm in recent]
    close_user = (
        "TENSION HINTS (compare/critique/motivate edges — synthesize, do not list):\n"
        + ("\n".join(tens_lines) or "(few surfaced)")
        + "\n\nMOST RECENT PAPERS:\n"
        + "\n".join(recent_lines)
    )
    close, _, _ = asyncio.run(
        chat(NARRATOR, _CLOSE_SYS, close_user, 0.4, 2000, extra_body=THINK)
    )

    report = (
        intro.strip() + "\n\n" + "\n\n".join(section_texts) + "\n\n" + close.strip()
    )
    report = _drop_invalid_ids(
        report
    )  # strip malformed arXiv ids (e.g. invalid month) inline
    grounded, off_digest = check_citations(report, pool_ids)
    return report, grounded, off_digest
