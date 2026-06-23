"""Steps 5-6 of the narrative layer: build a chronological digest from the
induced subgraph, narrate it with the local Gemma teacher (one full-context
request), and post-check that every cited arXiv id was actually in the digest.

LLM access mirrors phase_3/label/teacher.py (AsyncOpenAI against the llama.cpp
OpenAI-compatible router, /router/restart + /v1/models recovery) but **gently**:
we do NOT cold-restart at startup (that would evict other GPU work); we let the
router load-on-demand and only restart on an actual connection failure. Health is
checked via /v1/models, never via a chat completion (per memory guidance).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from openai import AsyncOpenAI

from _common import LLM_BASE_URL, LLM_ROUTER  # noqa: E402
from subgraph import Edge, Era, Landmark  # noqa: E402

# How many within-topic relations to list per landmark, per direction.
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

# modern 2006.11239 / 2205.11487 (4-5 digit), legacy hep-th/9201002, or a BARE legacy
# id with no archive prefix (e.g. arXiv:9701001) — the last form is malformed and almost
# always a hallucination, so we must still catch it (it slipped the old regex).
_ARXIV_RE: re.Pattern[str] = re.compile(
    r"arXiv:\s?([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5}|\d{7})", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Step 5a — digest


def _relations(lm: Landmark, edges: list[Edge], lm_ids: set[str]) -> str:
    """Compact within-topic relation list for one landmark (landmarks only)."""
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
    """Chronological, fully-grounded text digest fed to the narrator."""
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
            pol = f" [{e.polarity}]" if e.polarity else ""
            parts.append(f"  arXiv:{e.src} {e.intent}{pol} arXiv:{e.dst}")
    else:
        parts.append("  (none surfaced)")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Step 5b — narrate (gentle lazy-load + restart-on-failure)


async def model_status(model: str) -> str | None:
    """Return the router's status string for `model`, or None if unreachable/absent.

    Health via /v1/models only — never a chat completion (memory: llm-health-check).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as h:
            r = await h.get(f"{LLM_BASE_URL}/models")
            if r.status_code != 200:
                return None
            data = r.json()
            for m in data.get("data", []):
                if m.get("id") == model:
                    return m.get("status", {}).get("value", "?")
    except Exception:
        return None
    return None


async def restart_router(model: str) -> None:
    """Restart the router and wait until `model` is listed again (recovery only)."""
    print("  >>> /router/restart", flush=True)
    try:
        async with httpx.AsyncClient(timeout=60.0) as h:
            r = await h.get(f"{LLM_ROUTER}/router/restart")
            print(f"      restart -> {r.status_code}", flush=True)
    except Exception as e:
        print(f"      restart error: {e}", flush=True)
    for _ in range(60):
        if await model_status(model) is not None:
            return
        await asyncio.sleep(2.0)
    print("      WARN: router did not list model after 120s", flush=True)


async def narrate(
    digest: str,
    system_prompt: str,
    model: str,
    temperature: float = 0.4,
    max_tokens: int = 6000,
) -> str:
    """One full-context narration request; restart-and-retry on connection failure."""
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
                    {"role": "system", "content": system_prompt},
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
            print(
                f"  [narrate] request error (attempt {attempt + 1}): {msg}", flush=True
            )
            await restart_router(model)
    return ""


# ---------------------------------------------------------------------------
# Step 6 — hallucination post-check


def check_citations(story: str, allowed: set[str]) -> tuple[list[str], list[str]]:
    """Return (cited_in_digest, hallucinated) arXiv ids found in the story."""
    found = {m.group(1).lower() for m in _ARXIV_RE.finditer(story)}
    allowed_lc = {a.lower() for a in allowed}
    grounded = sorted(i for i in found if i in allowed_lc)
    hallucinated = sorted(i for i in found if i not in allowed_lc)
    return grounded, hallucinated


def verify_ids_exist(arxiv_ids: list[str]) -> set[str]:
    """Subset of `arxiv_ids` that exist as papers in the corpus (case-sensitive)."""
    if not arxiv_ids:
        return set()
    import psycopg  # local import: keeps module import light

    from _common import PG_DSN

    with psycopg.connect(PG_DSN) as conn:
        rows: list[tuple[Any, ...]] = conn.execute(
            "SELECT arxiv_id FROM paper WHERE arxiv_id = ANY(%s)", (arxiv_ids,)
        ).fetchall()
    return {str(r[0]) for r in rows}


def classify_citations(
    story: str, allowed: set[str]
) -> tuple[list[str], list[str], list[str]]:
    """Strict grounding check: (grounded, off_digest_but_real, fabricated).

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
