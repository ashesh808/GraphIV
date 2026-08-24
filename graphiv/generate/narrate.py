"""
Digest narration plus the mechanical guard that grounds every cited id

A typo id within edit distance two of a digest id is corrected, and a fabricated one is stripped
Every id that survives exists in the corpus by construction, not by the model's good behavior
"""

from __future__ import annotations

import re
from typing import Any

from openai import AsyncOpenAI

from graphiv.core.models import Edge, Era, Landmark
from graphiv.core.router import dated, model_status, restart_router
from graphiv.core.settings import LLM_BASE_URL

# How many within-topic relations to list per landmark, per direction
K_REL: int = 6

_INTENT_OUT: dict[str, str] = {
    "uses": "uses",
    "extends": "extends",
    "compares": "compares-with",
    "critiques": "critiques",
    "motivates": "motivated-by",
    "background": "cites",
}
_INTENT_IN: dict[str, str] = {
    "uses": "used-by",
    "extends": "extended-by",
    "compares": "compared-by",
    "critiques": "critiqued-by",
    "motivates": "motivates",
    "background": "cited-by",
}

"""
Matches modern ids, legacy archive-prefixed ids, and bare legacy ids with no prefix
That last form is malformed and almost always a hallucination, so it must still be caught
"""
_ARXIV_RE: re.Pattern[str] = re.compile(
    r"arXiv:\s?([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5}|\d{7})", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Step 5a , digest


def _relations(lm: Landmark, edges: list[Edge], lm_ids: set[str]) -> str:
    """
    Compact within-topic relation list for one landmark (landmarks only)
    """
    out_rels: list[str] = []
    in_rels: list[str] = []
    for e in edges:
        if e.src == lm.arxiv_id and e.dst in lm_ids:
            verb = _INTENT_OUT.get(e.intent or "", "cites")
            out_rels.append(f"{verb} arXiv:{e.dst}")
        elif e.dst == lm.arxiv_id and e.src in lm_ids:
            verb = _INTENT_IN.get(e.intent or "", "cited-by")
            in_rels.append(f"{verb} arXiv:{e.src}")
    rels = out_rels[:K_REL] + in_rels[:K_REL]
    return "; ".join(rels) if rels else "(none in-topic)"


def build_digest(
    question: str,
    landmarks: list[Landmark],
    edges: list[Edge],
    abstracts: dict[str, str],
    eras: list[Era],
    spine: list[str],
    tens: list[Edge],
) -> str:
    """
    Chronological, fully-grounded text digest fed to the narrator
    """
    lm_ids = {lm.arxiv_id for lm in landmarks}
    by_id = {lm.arxiv_id: lm for lm in landmarks}
    ordered = sorted(landmarks, key=lambda lm: (lm.year or 0, -lm.in_degree))

    parts: list[str] = [
        f"TOPIC: {question}",
        "",
        "ERAS:",
    ]
    for era in eras:
        parts.append(f"  [{era.index}] {era.label}: {era.year_lo}-{era.year_hi}")
    parts.append("")
    parts.append("PAPERS (chronological):")
    for lm in ordered:
        cat = f" [{lm.category}]" if lm.category else ""
        yr = lm.year if lm.year is not None else "?"
        parts.append(
            f'arXiv:{lm.arxiv_id} ({yr}) "{lm.title}"{cat}  '
            f"(cited-by {lm.in_degree} in-topic, era {lm.era})"
        )
        abstract_text = (abstracts.get(lm.arxiv_id) or "").strip()
        if abstract_text:
            parts.append(f"  abstract: {abstract_text}")
        parts.append(f"  relations: {_relations(lm, edges, lm_ids)}")

    parts.append("")
    parts.append("MAIN PATH (oldest -> newest, the developmental spine):")
    if spine:
        chain = " -> ".join(f"arXiv:{i} ({by_id[i].year})" for i in spine if i in by_id)
        parts.append(f"  {chain}")
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


# ---------------------------------------------------------------------------
# Step 5b , narrate (gentle lazy-load + restart-on-failure)


async def narrate(
    digest: str,
    system_prompt: str,
    model: str,
    temperature: float = 0.4,
    max_tokens: int = 6000,
) -> str:
    """
    One full-context narration request; restart-and-retry on connection failure
    """
    status = await model_status(model)
    if status is None:
        print(f"  [narrate] '{model}' not listed; restarting router ...", flush=True)
        await restart_router(model)
    else:
        print(f"  [narrate] '{model}' status={status} (load-on-demand)", flush=True)

    client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key="none")
    user_msg = (
        "Write the developmental trajectory for the topic below, grounded ONLY in "
        "these papers. Cite every claim inline as arXiv:<id>.\n\n" + digest
    )
    for attempt in range(3):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": dated(system_prompt)},
                    {"role": "user", "content": user_msg},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=1200,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            msg = f"{type(e).__name__}: {str(e)[:160]}"
            is_conn = (
                "Could not establish connection" in msg
                or "ConnectError" in msg
                or "InternalServerError" in msg
            )
            if not is_conn or attempt >= 2:
                print(f"  [narrate] request error (final): {msg}", flush=True)
                raise
            print(f"  [narrate] request error (attempt {attempt + 1}): {msg}", flush=True)
            await restart_router(model)
    return ""


# ---------------------------------------------------------------------------
# Step 6 , hallucination post-check


def check_citations(story: str, allowed: set[str]) -> tuple[list[str], list[str]]:
    """
    Return (cited_in_digest, hallucinated) arXiv ids found in the story
    """
    found = {m.group(1).lower() for m in _ARXIV_RE.finditer(story)}
    allowed_lc = {a.lower() for a in allowed}
    grounded = sorted(i for i in found if i in allowed_lc)
    hallucinated = sorted(i for i in found if i not in allowed_lc)
    return grounded, hallucinated


def verify_ids_exist(arxiv_ids: list[str]) -> set[str]:
    """
    Subset of `arxiv_ids` that exist as papers in the corpus (case-sensitive)
    """
    if not arxiv_ids:
        return set()
    import psycopg  # local import: keeps module import light

    from graphiv.core.settings import PG_DSN

    with psycopg.connect(PG_DSN) as conn:
        rows: list[tuple[Any, ...]] = conn.execute(
            "SELECT arxiv_id FROM paper WHERE arxiv_id = ANY(%s)", (arxiv_ids,)
        ).fetchall()
    return {str(r[0]) for r in rows}


def classify_citations(story: str, allowed: set[str]) -> tuple[list[str], list[str], list[str]]:
    """
    Strict grounding check: (grounded, off_digest_but_real, fabricated)

        `off_digest_but_real` ids exist in the corpus but weren't in the digest (the model
        reached beyond what it was given); `fabricated` ids don't exist at all (true
        hallucinations). Verifies the off-digest ids against the corpus (`paper` table).
    """
    grounded, off = check_citations(story, allowed)
    if not off:
        return grounded, [], []
    # case-insensitive existence: query the graph with the as-found ids
    real = {i.lower() for i in verify_ids_exist(off)}
    off_real = sorted(i for i in off if i in real)
    fabricated = sorted(i for i in off if i not in real)
    return grounded, off_real, fabricated


def _edit_distance_le(a: str, b: str, cap: int = 2) -> int:
    """
    Levenshtein distance, early-exited at cap+1 (band DP; ids are short)
    """
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def _fuzzy_target(bad: str, allowed_lc: dict[str, str]) -> str | None:
    """
    The digest id `bad` is a typo of: unique at distance 1, else unique at distance 2

        for ids long enough that two edits still identify one paper. None if ambiguous.
    """
    d1 = [v for k, v in allowed_lc.items() if _edit_distance_le(bad, k, 1) <= 1]
    if len(d1) == 1:
        return d1[0]
    if d1 or len(bad) < 8:
        return None
    d2 = [v for k, v in allowed_lc.items() if _edit_distance_le(bad, k, 2) <= 2]
    return d2[0] if len(d2) == 1 else None


def _strip_id_mentions(story: str, ids: set[str]) -> str:
    """
    Remove `arXiv:<id>` mentions (with wrapping brackets) for every id in `ids`
    """
    out: list[str] = []
    last = 0
    pat = re.compile(
        r"\s*[\[(]?\s*arXiv:\s?([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5}|\d{7})\s*[\])]?",
        re.IGNORECASE,
    )
    for m in pat.finditer(story):
        if m.group(1).lower() not in ids:
            continue
        out.append(story[last : m.start()])
        out.append(" ")  # keep neighbouring words separated
        last = m.end()
    out.append(story[last:])
    s = "".join(out)
    s = re.sub(r"\(\s*\)|\[\s*\]", "", s)
    s = re.sub(r" {2,}", " ", s)
    s = re.sub(r"\s+([.,;])", r"\1", s)
    return s


# number+unit tokens worth verifying (7.7x, 31%, 3x); bare integers are too noisy to check
_NUM_RE: re.Pattern[str] = re.compile(r"(\d+(?:\.\d+)?)\s?([x×%])")


def _num_matches(tok: str, source: str) -> bool:
    """
    Boundary-aware: '3' must not match inside '3.7' or '31'; 3.70 ~ 3.7; 31 ~ 31.0
    """
    variants = {tok}
    if "." in tok:
        variants.add(tok.rstrip("0").rstrip("."))
    else:
        variants.add(tok + ".0")
    # the lookahead blocks a digit or decimal continuation but still allows sentence punctuation
    return any(re.search(rf"(?<![\d.]){re.escape(v)}(?!\.?\d)", source) for v in variants)


def check_numbers(
    report: str,
    extractions: dict[str, dict[str, str]],
    abstracts: dict[str, str],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """
    Echo-check: every number+unit in a sentence with exactly one cited paper must appear

        in that paper's extraction fields or abstract. Returns (verified, unverified) as
        (arxiv_id, number-token) pairs. Multi-citation sentences are skipped (attribution is
        ambiguous); bare integers are skipped (too noisy).
    """
    verified: list[tuple[str, str]] = []
    unverified: list[tuple[str, str]] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", report):
        ids = {m.group(1).lower() for m in _ARXIV_RE.finditer(sentence)}
        if len(ids) != 1:
            continue
        aid = next(iter(ids))
        source = " ".join(str(v) for v in (extractions.get(aid) or {}).values())
        source = source + " " + (abstracts.get(aid) or "")
        for m in _NUM_RE.finditer(sentence):
            num, unit = m.group(1), m.group(2)
            ok = _num_matches(num, source)
            (verified if ok else unverified).append((aid, f"{num}{unit}"))
    return verified, unverified


def flag_numbers(report: str, unverified: list[tuple[str, str]]) -> str:
    """
    Append a dagger to unverified number tokens (first occurrence per sentence-id pair)
    """
    for _aid, tok in unverified:
        pat = re.compile(rf"(?<![\d.])({re.escape(tok)})(?!†)")
        report = pat.sub(r"\1†", report, count=1)
    if unverified:
        report += (
            "\n\n---\n*† number could not be verified against the cited paper's "
            "abstract or extracted fields (figure- or full-text-sourced).*"
        )
    return report


_LINKIFY_RE: re.Pattern[str] = re.compile(
    r"[\[(]?\s*arXiv:\s?([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5})(?:\s*[\])])?",
    re.IGNORECASE,
)


def linkify(md: str) -> str:
    """
    Output-boundary formatting: every arXiv citation (any bracket style) becomes one

        consistent markdown hyperlink `[arXiv:<id>](https://arxiv.org/abs/<id>)`. Idempotent ,
        already-linked mentions (followed by an open paren) are left alone. The internal report
        string stays bare; apply this only when writing report.md or returning over MCP.
    """
    out: list[str] = []
    last = 0
    for m in _LINKIFY_RE.finditer(md):
        if m.end() < len(md) and md[m.end()] == "(":
            continue  # already a markdown link target
        aid = m.group(1)
        pre = md[last : m.start()]
        out.append(pre)
        # keep a separating space if the match swallowed one before a word boundary
        if pre and not pre[-1].isspace() and m.group(0)[0] in " ([":
            out.append(" ")
        out.append(f"[arXiv:{aid}](https://arxiv.org/abs/{aid})")
        last = m.end()
    out.append(md[last:])
    return "".join(out)


def ground_report(
    story: str, allowed: set[str]
) -> tuple[str, list[str], list[str], dict[str, str], list[str]]:
    """
    Mechanical grounding guard: every arXiv id in the returned text exists in the corpus

        (1) fuzzy-correct, an unknown id within edit distance 1-2 of a digest id is a typo,
        fixed in place; (2) corpus-check the rest (real-but-off-digest ids are kept);
        (3) strip fabricated survivors. Returns (clean_story, grounded, off_digest_real,
        corrections, stripped).
    """
    allowed_lc = {a.lower(): a for a in allowed}
    _, off = check_citations(story, allowed)
    corrections: dict[str, str] = {}
    for bad in off:
        good = _fuzzy_target(bad, allowed_lc)
        if good is not None:
            corrections[bad] = good
            story = re.sub(
                rf"arXiv:\s?{re.escape(bad)}",
                f"arXiv:{good}",
                story,
                flags=re.IGNORECASE,
            )
    grounded, off_real, fabricated = classify_citations(story, allowed)
    if fabricated:
        story = _strip_id_mentions(story, set(fabricated))
    if corrections or fabricated:
        print(
            f"  [ground] corrected {len(corrections)} typo id(s), "
            f"stripped {len(fabricated)} fabricated id(s)",
            flush=True,
        )
    return story, grounded, off_real, corrections, fabricated
