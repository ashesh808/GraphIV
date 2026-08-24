"""
Sectioned long-form composition: outline, then one focused call per section

A single narrate call self-limits to about a thousand words however rich the digest is
Writing section by section is what lets the per-paper critiques surface as analysis
"""

from __future__ import annotations

import asyncio
import re

from graphiv.core.llm import NO_THINK, THINK, chat, parse_json
from graphiv.core.models import Edge, Landmark
from graphiv.generate.narrate import (
    _relations,
    check_citations,
    check_numbers,
    flag_numbers,
    ground_report,
)
from graphiv.generate.schema import Schema
from graphiv.generate.story import Story

NARRATOR = "Gemma-4-26B"


_OUTLINE_SYS = (
    "You are organizing a literature review. Given the question, a list of papers (id, year, "
    "role, title), and the STORY THREADS (lineage chains mined from the citation graph), "
    "propose 5-8 thematic sections that tell the story origins -> key advances -> current "
    "frontier. Assign each paper id to exactly one section; every section needs >=3 papers; "
    "order sections logically. Make at least one section about the LATEST (most recent years) "
    "work.\n"
    "- The sections must COVER EVERY story thread: each thread's papers should progress "
    "through the section order (a thread may span sections or share one; never orphan one).\n"
    "- Use the roles: foundational/core papers anchor early sections, frontier papers the "
    "late ones; adjacent/survey papers only support, never headline, a section.\n"
    "- Keep every section specific to THIS topic. Do NOT create a generic-foundations section "
    "(e.g. 'the rise of transformers', backbones, optimizers, base language models) built from "
    "ubiquitous papers that are merely widely cited; fold any genuinely-needed shared method "
    "briefly into a topic-specific section instead.\n"
    'Output ONLY JSON: [{"title":"..","ids":["id1","id2",..]}, ...].'
)

_SECTION_SYS = (
    "You are writing ONE section of a rigorous literature review, grounded ONLY in the papers "
    "given. Requirements:\n"
    "- Start with '## <the section title>'.\n"
    "- 350-600 words. Discuss the papers' actual contributions (use the extracted fields and "
    "numbers), and COMPARE/CONTRAST them — do not just list.\n"
    "- If (and only if) the section compares >=3 methods on shared dimensions, you may render "
    "that comparison as ONE compact markdown table (methods as rows, dimensions as columns, "
    "arXiv:<id> in the first column) and keep the prose for analysis the table cannot carry; "
    "leave a blank line after the table before any prose continues. Every number in a table "
    "cell must name its baseline or benchmark inline (e.g. '7.7x vs FP16'); numbers measured "
    "against different baselines must never be presented as directly rankable. "
    "Never force a table where the papers are not directly comparable.\n"
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
_WEAVE_SYS = (
    "You are completing a literature review that MISSED some highly relevant papers. For "
    "each missing paper you get its metadata and extracted fields, plus the review's section "
    "titles. Decide the best-fitting section for each and write, per section, 2-4 sentences "
    "integrating its missing papers into that section's argument (compare against papers the "
    "section already discusses; cite as arXiv:<id>). If a paper genuinely adds nothing "
    "beyond papers already covered, put it in section index -1 (further reading).\n"
    'Output ONLY JSON: {"<section index>": "<sentences>", "-1": ["id1", ...]}.'
)


_NUMFIX_SYS = (
    "You correct numeric claims in literature-review sentences. For each sentence you get "
    "the SOURCE material of its cited paper. Rewrite the sentence so every number matches "
    "the source; if the source does not support the number at all, drop the number but keep "
    "the qualitative claim. Change nothing else.\n"
    'Output ONLY JSON: {"<index>": "<fixed sentence>", ...} for sentences you changed.'
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
    role = f" [{lm.role}]" if lm.role else ""
    out = [f'arXiv:{lm.arxiv_id} ({yr}){role} "{lm.title}" (cited-by {lm.in_degree} in-topic)']
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
    pool_ids: set[str],
) -> str:
    blocks = [
        _paper_block(by_id[i], edges, lm_ids, extractions, critiques, schema, abstracts)
        for i in ids
        if i in by_id
    ]
    if not blocks:
        return ""
    user = f"Review question: {question}\nSection title: {title}\n\nPAPERS:\n" + "\n".join(blocks)
    text, _, _ = await chat(NARRATOR, _SECTION_SYS, user, 0.4, 4000, extra_body=THINK)
    out = text.strip()
    # thinking sometimes eats the budget and returns a stub, so a thin section is retried
    if len(out) < 400:
        retry_user = (
            user + "\n\nThe section MUST be at least 350 words of substantive analysis "
            "starting with '## " + title + "'. Discuss every paper above; do not be brief."
        )
        text2, _, _ = await chat(NARRATOR, _SECTION_SYS, retry_user, 0.3, 4000)
        if len(text2.strip()) > len(out):
            out = text2.strip()
    # continuation: if the section was cut at the token cap (no sentence-final char), finish it
    if len(out) > 600 and out[-1] not in ".!?\"')]":
        cont_user = (
            user
            + "\n\nThe draft below was cut off. Continue from where it stops:\n\n"
            + out[-1500:]
        )
        cont, _, _ = await chat(NARRATOR, _CONT_SYS, cont_user, 0.4, 1500)
        if cont.strip():
            out = out + " " + cont.strip()
    # grounding feedback: one bounded rewrite if the draft cites ids outside the pool
    # (the assembly-level ground_report strips whatever survives this)
    _, off = check_citations(out, pool_ids)
    if off:
        bad = ", ".join(f"arXiv:{i}" for i in off)
        fix_user = (
            user + f"\n\nREVISION: your previous draft cited ids that do NOT exist: {bad}. "
            "Rewrite the section citing ONLY arXiv ids from the papers listed above; "
            "keep the analysis otherwise intact.\n\nPREVIOUS DRAFT:\n" + out
        )
        text3, _, _ = await chat(NARRATOR, _SECTION_SYS, fix_user, 0.3, 4000)
        _, off3 = check_citations(text3, pool_ids)
        if text3.strip() and len(off3) < len(off):
            print(
                f"[long]   section '{title}': repaired {len(off) - len(off3)} bad id(s)",
                flush=True,
            )
            out = text3.strip()
    return out


def _plan_outline(
    question: str, landmarks: list[Landmark], story: Story | None = None
) -> list[tuple[str, list[str]]]:
    """
    Ask the model for a story-informed themed outline; fall back to era buckets
    """
    idx = "\n".join(
        f'{lm.arxiv_id} ({lm.year if lm.year is not None else "?"})'
        f'{f" [{lm.role}]" if lm.role else ""} {lm.title}'
        for lm in landmarks
    )
    threads_txt = ""
    if story is not None and story.threads:
        lines = [f"[T{i}] " + " -> ".join(chain) for i, chain in enumerate(story.threads, 1)]
        threads_txt = "\n\nSTORY THREADS:\n" + "\n".join(lines)
    user = f"QUESTION: {question}\n\nPAPERS:\n{idx}{threads_txt}"
    valid = {lm.arxiv_id for lm in landmarks}
    sections: list[tuple[str, list[str]]] = []
    # one thinking-off retry before the era-bucket fallback, which degrades the whole outline
    for extra in (THINK, NO_THINK):
        try:
            text, _, _ = asyncio.run(
                chat(NARRATOR, _OUTLINE_SYS, user, 0.2, 3000, extra_body=extra)
            )
            obj = parse_json(text)
        except Exception:  # noqa: BLE001
            obj = None
        if isinstance(obj, list):
            for item in obj:  # pyright: ignore[reportAny]
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()  # pyright: ignore[reportAny]
                raw = item.get("ids") or []  # pyright: ignore[reportAny]
                ids = [str(i) for i in raw if str(i) in valid] if isinstance(raw, list) else []
                if title and len(ids) >= 2:
                    sections.append((title, ids))
        if sections:
            return sections
        print("[long] outline parse failed; retrying thinking-off", flush=True)
    # fallback: bucket by era index
    buckets: dict[int, list[str]] = {}
    for lm in landmarks:
        buckets.setdefault(lm.era, []).append(lm.arxiv_id)
    labels = {0: "Origins", 1: "Key Advances", 2: "Current Frontier"}
    return [(labels.get(e, f"Era {e}"), ids) for e, ids in sorted(buckets.items()) if ids]


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
    story: Story | None = None,
) -> tuple[str, list[str], list[str]]:
    """
    Outline -> per-section deep compose -> intro + close

    Returns (report, grounded, off).
    """
    by_id = {lm.arxiv_id: lm for lm in landmarks}
    lm_ids = set(by_id)
    outline = _plan_outline(question, landmarks, story)
    print(f"[long] outline: {[t for t, _ in outline]}", flush=True)

    # sections (sequential: one big model resident on the single 3090)
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
                pool_ids,
            )
        )
        if txt:
            section_texts.append(txt)
        print(f"[long]   section '{title}': {len(txt)} chars", flush=True)

    # intro
    intro_user = f"QUESTION: {question}\n\nSECTION TITLES:\n" + "\n".join(
        f"- {t}" for t, _ in outline
    )
    intro, _, _ = asyncio.run(chat(NARRATOR, _INTRO_SYS, intro_user, 0.4, 4000, extra_body=THINK))
    if not intro.strip():  # thinking budget occasionally eats the intro -> retry without it
        intro, _, _ = asyncio.run(chat(NARRATOR, _INTRO_SYS, intro_user, 0.4, 1500))

    # edges carry titles here so the close argues rather than parroting id triples
    title_of = {lm.arxiv_id: lm.title for lm in landmarks}
    tens_lines = [
        f'arXiv:{e.src} ("{title_of.get(e.src, "?")[:60]}") {e.intent} '
        f'arXiv:{e.dst} ("{title_of.get(e.dst, "?")[:60]}")'
        for e in tens[:20]
    ]
    recent = sorted((lm for lm in landmarks if lm.year), key=lambda lm: -(lm.year or 0))[:12]
    recent_lines = [f'arXiv:{lm.arxiv_id} ({lm.year}) "{lm.title}"' for lm in recent]
    close_user = (
        "TENSION HINTS (compare/critique/motivate edges — synthesize, do not list):\n"
        + ("\n".join(tens_lines) or "(few surfaced)")
        + "\n\nMOST RECENT PAPERS:\n"
        + "\n".join(recent_lines)
    )
    close, _, _ = asyncio.run(chat(NARRATOR, _CLOSE_SYS, close_user, 0.4, 4000, extra_body=THINK))

    body = "\n\n".join(section_texts)
    # coverage checkback: weave high-relevance landmarks the sections dropped back in
    body = _cover_missing(question, body, outline, landmarks, extractions, schema, abstracts)
    report = intro.strip() + "\n\n" + body + "\n\n" + close.strip()
    # mechanical guard: fuzzy-correct typo ids -> corpus-verify -> strip fabricated
    report, grounded, off_digest, _, _ = ground_report(report, pool_ids)
    # numeric echo-check: one bounded repair, then dagger the survivors
    report = _repair_numbers(report, extractions, abstracts)
    return report, grounded, off_digest


def _cover_missing(
    question: str,
    body: str,
    outline: list[tuple[str, list[str]]],
    landmarks: list[Landmark],
    extractions: dict[str, dict[str, str]],
    schema: Schema,
    abstracts: dict[str, str],
    max_missing: int = 12,
) -> str:
    """
    Weave uncited relevance>=1 landmarks into their best sections (one bounded call);

        anything the model deems redundant lands in a compact Further Reading list instead of
        silently vanishing. Observed: Quest (rel 2, cited-by 104) extracted-then-uncited.
    """
    missing = sorted(
        (
            lm
            for lm in landmarks
            if lm.relevance is not None and lm.relevance >= 1 and f"arXiv:{lm.arxiv_id}" not in body
        ),
        key=lambda lm: (-(lm.relevance or 0), -lm.in_degree),
    )[:max_missing]
    if not missing:
        return body
    titles = [t for t, _ in outline]
    by_id = {lm.arxiv_id: lm for lm in missing}
    blocks: list[str] = []
    for lm in missing:
        ext = extractions.get(lm.arxiv_id) or {}
        fields = "; ".join(f"{k}: {v}" for k, v in ext.items() if v and str(v).lower() != "n/a")
        blocks.append(
            f'arXiv:{lm.arxiv_id} ({lm.year or "?"}) "{lm.title}" :: '
            f"{fields[:400] or (abstracts.get(lm.arxiv_id) or '')[:250]}"
        )
    user = (
        f"Review question: {question}\n\nSECTIONS:\n"
        + "\n".join(f"[{i}] {t}" for i, t in enumerate(titles))
        + "\n\nMISSING PAPERS:\n"
        + "\n".join(blocks)
    )
    try:
        text, _, _ = asyncio.run(chat(NARRATOR, _WEAVE_SYS, user, 0.3, 2000, extra_body=NO_THINK))
        obj = parse_json(text)
    except Exception:  # noqa: BLE001
        obj = None
    further: list[str] = [lm.arxiv_id for lm in missing]  # fallback: list them all
    if isinstance(obj, dict):
        further = []
        parts = re.split(r"(?m)(^## .*$)", body)
        headers = [i for i in range(1, len(parts), 2)]
        woven = 0
        for k, v in obj.items():  # pyright: ignore[reportAny]
            if str(k) == "-1":
                if isinstance(v, list):
                    further.extend(str(i) for i in v if str(i) in by_id)
                continue
            try:
                idx = int(str(k))
            except Exception:  # noqa: BLE001
                continue
            add = str(v).strip()  # pyright: ignore[reportAny]
            if not add or not (0 <= idx < len(headers)):
                continue
            body_idx = headers[idx] + 1
            if body_idx < len(parts):
                parts[body_idx] = parts[body_idx].rstrip() + "\n\n" + add + "\n"
                woven += 1
        body = "".join(parts)
        # papers the model neither wove nor listed still go to further reading
        for lm in missing:
            if f"arXiv:{lm.arxiv_id}" not in body and lm.arxiv_id not in further:
                further.append(lm.arxiv_id)
        if woven:
            print(f"[long]   coverage: wove {woven} section addition(s)", flush=True)
    if further:
        lines = ["", "## Further Reading", ""]
        for aid in further:
            lm = by_id.get(aid)
            if lm is None:
                continue
            lines.append(
                f'- arXiv:{aid} ({lm.year or "?"}) — "{lm.title}" '
                f"[{lm.role or 'ungraded'}, cited-by {lm.in_degree} in-topic]"
            )
        body = body + "\n".join(lines)
        print(f"[long]   coverage: {len(further)} paper(s) -> further reading", flush=True)
    return body


def _repair_numbers(
    report: str,
    extractions: dict[str, dict[str, str]],
    abstracts: dict[str, str],
) -> str:
    """
    One bounded rewrite of sentences whose numbers don't echo their cited source;

        whatever remains unverified gets a dagger (figure/full-text numbers are often real).
    """
    _, unverified = check_numbers(report, extractions, abstracts)
    if not unverified:
        return report
    bad_ids = {aid for aid, _ in unverified}
    sentences = [
        s
        for s in re.split(r"(?<=[.!?])\s+", report)
        if any(f"arxiv:{aid}" in s.lower() for aid in bad_ids) and _NUM_HINT.search(s)
    ][:8]
    if sentences:
        blocks: list[str] = []
        for i, s in enumerate(sentences):
            ids = {m.lower() for m in re.findall(r"arXiv:\s?(\S+?)[\s\]),]", s)}
            src = " | ".join(
                " ".join(str(v) for v in (extractions.get(a) or {}).values())
                + " "
                + (abstracts.get(a) or "")[:600]
                for a in ids
            )
            blocks.append(f"[{i}] SENTENCE: {s}\nSOURCE: {src[:1200]}")
        text, _, _ = asyncio.run(
            chat(
                NARRATOR,
                _NUMFIX_SYS,
                "\n\n".join(blocks),
                0.2,
                1500,
                extra_body=NO_THINK,
            )
        )
        obj = parse_json(text)
        if isinstance(obj, dict):
            for k, v in obj.items():  # pyright: ignore[reportAny]
                try:
                    idx = int(k)
                except Exception:  # noqa: BLE001
                    continue
                if 0 <= idx < len(sentences) and str(v).strip():
                    report = report.replace(sentences[idx], str(v).strip(), 1)
        n_before = len(unverified)
        _, unverified = check_numbers(report, extractions, abstracts)
        if len(unverified) < n_before:
            print(
                f"[long]   numbers: repaired {n_before - len(unverified)} of {n_before}",
                flush=True,
            )
    return flag_numbers(report, unverified)


_NUM_HINT = re.compile(r"\d+(?:\.\d+)?\s?[x×%]")
