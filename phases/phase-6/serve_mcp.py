"""MCP server for GraphIV — deep research + refinement + follow-up tools over stdio.

Designed for a *small local host model* (librechat on the same llama-router): the server owns
all judgment (question refinement runs on the local LLM here, not in the host), so the host
only relays tool results. deep_research shells out to run.py (a crash or CUDA OOM kills the
run, not the server) behind a single-slot lock — one 3090, one PG, one resident model.

    uv run python phases/phase-6/serve_mcp.py          # stdio transport (librechat etc.)
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "components"))
sys.path.insert(0, str(_HERE.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from _common import MAP_MODEL, PG_DSN  # noqa: E402

_RUN = _HERE / "run.py"
_OUT = _HERE / "output" / "research"
_DONE = re.compile(r"done -> (\S+/report\.md)")

mcp = FastMCP("graphiv")
_slot = asyncio.Lock()

_REFINE_SYS = (
    "You refine a freeform research interest into ONE focused literature-review question "
    "over arXiv. Consider: which subfield/scope, method vs application angle, and time "
    "horizon (origins vs recent frontier). If the input is already focused, keep it.\n"
    'Output ONLY JSON: {"focused_question":"...","clarifying_aspects":["<=3 short '
    'questions for the user, empty if none needed"]}.'
)


@mcp.tool()
async def refine_question(text: str) -> str:
    """Turn a freeform research interest into one focused literature-review question.

    Call this FIRST when the user's request is broad or ambiguous; relay any
    clarifying_aspects to the user, fold their answers back into `text`, and repeat until
    clarifying_aspects is empty. Then call deep_research with the focused_question.
    Fast (~seconds). Returns JSON: focused_question + clarifying_aspects.
    """
    from llm import NO_THINK, chat, parse_json  # noqa: PLC0415

    out, _, _ = await chat(MAP_MODEL, _REFINE_SYS, text, 0.2, 400, extra_body=NO_THINK)
    obj = parse_json(out)
    if not isinstance(obj, dict) or not obj.get("focused_question"):
        obj = {"focused_question": text.strip(), "clarifying_aspects": []}
    return json.dumps(obj)


@mcp.tool()
async def deep_research(question: str, effort: int = 4) -> str:
    """Run GraphIV deep research: a grounded, cited literature review over all of arXiv.

    effort 0-5 trades latency for depth (3+ = judge-driven deep loop with full-PDF critique
    and figures; effort 4 takes ~5-10 minutes — tell the user before calling). Every arXiv
    id cited in the result exists in the corpus. Returns the review as markdown.
    """
    effort = max(0, min(5, effort))
    async with _slot:  # one 3090: runs serialize, the server stays responsive
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(_RUN),
            question,
            f"--set-effort={effort}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=7200)
        except TimeoutError:
            proc.terminate()
            return "ERROR: run exceeded the 2h timeout and was terminated."
    stdout, stderr = out_b.decode(errors="replace"), err_b.decode(errors="replace")
    m = None
    for m in _DONE.finditer(stdout):
        pass  # keep the last "done ->" (the deep loop logs intermediate rounds)
    if m is None:
        return (
            f"ERROR: run produced no report (exit {proc.returncode}).\n\n"
            + (stdout + stderr)[-2000:]
        )
    return Path(m.group(1)).read_text(encoding="utf-8")


@mcp.tool()
def search_papers(query: str, k: int = 10) -> str:
    """Keyword-search paper titles across the 3M-paper arXiv corpus (fast, no GPU).

    For follow-up checks like 'is there work on X the review missed?'. Returns JSON rows
    (arxiv_id, title, year, category). Lexical title match — for semantic retrieval run
    deep_research instead.
    """
    from store import Store  # noqa: PLC0415

    store = Store(PG_DSN)
    try:
        rows = store.lexical_pool(query, max(1, min(50, k)))
    finally:
        store.close()
    return json.dumps(
        [
            {
                "arxiv_id": n.arxiv_id,
                "title": n.title,
                "year": n.year,
                "category": n.category,
            }
            for n in rows
        ]
    )


@mcp.tool()
def paper_details(arxiv_id: str) -> str:
    """Full metadata for one paper: title, authors, year, category, abstract, and how many
    papers cite it corpus-wide. Returns JSON; 'error' key if the id is unknown."""
    import psycopg  # noqa: PLC0415

    with psycopg.connect(PG_DSN) as conn:
        row: tuple[Any, ...] | None = conn.execute(
            "SELECT title, authors, year, primary_category, abstract"
            " FROM paper_meta WHERE arxiv_id = %s",
            (arxiv_id,),
        ).fetchone()
    if row is None:
        return json.dumps({"error": f"unknown arXiv id: {arxiv_id}"})
    from store import Store  # noqa: PLC0415

    store = Store(PG_DSN)
    try:
        cites = store.global_citations([arxiv_id]).get(arxiv_id, 0)
    finally:
        store.close()
    title, authors, year, cat, abstract = row
    return json.dumps(
        {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "year": year,
            "category": cat,
            "abstract": (str(abstract or ""))[:2000],
            "cited_by_count": cites,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
        }
    )


@mcp.tool()
def list_reports() -> str:
    """List previously generated reports (slug + configs) available via get_report."""
    out: list[dict[str, list[str]]] = []
    if _OUT.is_dir():
        for d in sorted(_OUT.iterdir()):
            cfgs = [c.name for c in d.iterdir() if (c / "report.md").exists()]
            if cfgs:
                out.append({d.name: cfgs})
    return json.dumps(out)


@mcp.tool()
def get_report(slug: str, config: str = "") -> str:
    """Reload a previously generated report by slug (see list_reports). Returns markdown."""
    d = _OUT / slug
    if not d.is_dir():
        return f"ERROR: no reports under slug '{slug}' (use list_reports)"
    cfgs = [c for c in sorted(d.iterdir()) if (c / "report.md").exists()]
    if not cfgs:
        return f"ERROR: no finished report under '{slug}'"
    pick = next((c for c in cfgs if c.name == config), cfgs[-1])
    return (pick / "report.md").read_text(encoding="utf-8")


@mcp.prompt()
def deep_research_flow(interest: str) -> str:
    """Guided flow: refine a freeform interest into one question, then run deep research."""
    return (
        f"The user wants a literature review about: {interest}\n\n"
        "1. Call refine_question with their text. If it returns clarifying_aspects, ask "
        "the user those questions, fold the answers back in, and call refine_question "
        "again — until clarifying_aspects is empty.\n"
        "2. Tell the user the focused question and that the deep run takes ~5-10 minutes, "
        "then call deep_research(focused_question, effort=4).\n"
        "3. Present the returned review verbatim (it is fully cited). Offer follow-ups: "
        "search_papers / paper_details for checks, or another deep_research to drill in."
    )


if __name__ == "__main__":
    mcp.run()
