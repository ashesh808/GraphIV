"""
MCP server for GraphIV: deep research, question refinement and follow-up tools

A run shells out behind a one-slot lock, so a crash or a CUDA OOM kills the run and not the server
The http transport also serves run artifacts and the dashboard
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from graphiv.core.settings import MAP_MODEL, OUTPUT_DIR, PG_DSN

_RUN = Path(__file__).resolve().parents[2] / "scripts" / "research.py"
_OUT = OUTPUT_DIR
_DONE = re.compile(r"done -> (\S+/report\.md)")
_PORT = int(os.environ.get("GRAPHIV_MCP_PORT", "8756"))
PUBLIC_URL = os.environ.get("GRAPHIV_PUBLIC_URL", f"http://127.0.0.1:{_PORT}").rstrip("/")

"""
GRAPHIV_READONLY marks the public instance, which registers no tool and no mutating route
Exposure is decided by which port the tunnel reaches, never by inspecting a request
"""
_READONLY = os.environ.get("GRAPHIV_READONLY", "") == "1"

mcp = FastMCP("graphiv")
_slot = asyncio.Lock()


def _tool():  # noqa: ANN202
    return (lambda f: f) if _READONLY else mcp.tool()


def _prompt():  # noqa: ANN202
    return (lambda f: f) if _READONLY else mcp.prompt()


_REFINE_SYS = (
    "You refine a freeform research interest into focused literature-review questions over "
    "arXiv, grounded in what the corpus actually contains (a title probe is provided).\n"
    "Rules:\n"
    "- Propose 2-4 CANDIDATE focused questions the corpus can clearly support. Each must stay "
    "inside the user's stated scope: NEVER introduce a subfield, application domain, or "
    "combination the user did not mention (if they say 'JEPA', do not invent 'JEPA for "
    "recommendation systems').\n"
    "- If the input is already a focused literature-review question, return it as the single "
    "candidate.\n"
    "- At most ONE clarifying question, and only if the candidates genuinely diverge; it must "
    "be specific to this topic — no generic boilerplate like 'theory or application?' or "
    "'recent or historical?'.\n"
    'Output ONLY JSON: {"candidates":["question 1","question 2",...],'
    '"clarifying_question":"" }'
)


_SIMILAR_SYS = (
    "You match a NEW research question against questions answered by previously completed "
    "literature reviews. Return the indices of past reviews that would substantially answer "
    "the new question (same topic AND scope — sharing a broad field is not a match).\n"
    'Output ONLY JSON: {"matches":[0,2,...]} — empty list if none apply.'
)


def _runs_index() -> list[dict[str, object]]:
    """
    Finished runs, oldest first: research_id (slug), configs, latest config, question,

        date, n_papers.
    """
    out: list[dict[str, object]] = []
    if not _OUT.is_dir():
        return out
    for d in sorted(_OUT.iterdir()):
        if not d.is_dir():
            continue
        cfgs = sorted(c.name for c in d.iterdir() if (c / "report.md").exists())
        if not cfgs:
            continue
        latest = d / cfgs[-1]
        question, n_papers = "", 0
        rj = latest / "run.json"
        if rj.exists():
            try:
                obj: dict[str, Any] = json.loads(  # pyright: ignore[reportExplicitAny]
                    rj.read_text()
                )
                question = str(obj.get("question", ""))
                marks = obj.get("landmarks")
                n_papers = len(marks) if isinstance(marks, list) else 0
            except Exception:  # noqa: BLE001
                pass
        mtime = (latest / "report.md").stat().st_mtime
        out.append(
            {
                "research_id": d.name,
                "configs": cfgs,
                "config": cfgs[-1],
                "question": question,
                "date": time.strftime("%Y-%m-%d", time.localtime(mtime)),
                "n_papers": n_papers,
            }
        )
    return out


async def _similar_runs(question: str) -> list[dict[str, object]]:
    """
    LLM-match a question against past run questions (no embedding model in-process)
    """
    from graphiv.core.llm import NO_THINK, chat, parse_json

    runs = [r for r in _runs_index() if r["question"]]
    if not runs:
        return []
    listing = "\n".join(f"{i}. {r['question']}" for i, r in enumerate(runs))
    user = f"NEW QUESTION: {question}\n\nPAST REVIEWS:\n{listing}"
    out, _, _ = await chat(MAP_MODEL, _SIMILAR_SYS, user, 0.0, 200, extra_body=NO_THINK)
    obj = parse_json(out)
    if not isinstance(obj, dict):
        return []
    idxs = obj.get("matches")
    if not isinstance(idxs, list):
        return []
    return [runs[i] for i in idxs if isinstance(i, int) and 0 <= i < len(runs)]


def _rewrite_assets(md: str, slug: str, cfg: str) -> str:
    """
    Relative run assets (figures/*.png, graph.png, graph.html) -> served absolute URLs
    """
    base = f"{PUBLIC_URL}/files/{slug}/{cfg}"
    return re.sub(r"\]\((figures/[^)]+|graph\.png|graph\.html)\)", rf"]({base}/\1)", md)


def _finish_report(report_path: Path) -> str:
    """
    Linkify (old reports were written bare) + rewrite asset URLs for the client
    """
    from graphiv.generate.narrate import linkify

    md = report_path.read_text(encoding="utf-8")
    cfg_dir = report_path.parent
    return _rewrite_assets(linkify(md), cfg_dir.parent.name, cfg_dir.name)


@_tool()
async def refine_question(text: str) -> str:
    """
    Turn a freeform research interest into candidate literature-review questions

        Call this FIRST when the user's request is broad or ambiguous. Present the returned
        candidates to the user and let them pick or edit one (never silently pick yourself);
        relay the clarifying_question only if non-empty. Then call deep_research with the chosen
        question. Fast (~seconds). Returns JSON: candidates[] + clarifying_question + probe
        (corpus titles the candidates are grounded in).
    """
    from graphiv.core.llm import NO_THINK, chat, parse_json
    from graphiv.core.store import Store

    store = Store(PG_DSN)
    try:
        probe = store.lexical_pool(text, 20)
    finally:
        store.close()
    probe_txt = "\n".join(f"- ({n.year}) {n.title}" for n in probe) or "(no title hits)"
    user = f"USER INTEREST: {text}\n\nCORPUS TITLE PROBE:\n{probe_txt}"
    out, _, _ = await chat(MAP_MODEL, _REFINE_SYS, user, 0.2, 500, extra_body=NO_THINK)
    obj = parse_json(out)
    if not isinstance(obj, dict) or not obj.get("candidates"):
        obj = {"candidates": [text.strip()], "clarifying_question": ""}
    obj["probe"] = [f"({n.year}) {n.title}" for n in probe[:10]]
    return json.dumps(obj)


@_tool()
async def deep_research(
    question: str, effort: int = 4, seed_arxiv_id: str = "", force_new: bool = False
) -> str:
    """
    Run GraphIV deep research: a grounded, cited literature review over all of arXiv

        effort 0-5 trades latency for depth (3+ = judge-driven deep loop with full-PDF critique
        and figures; effort 4 takes ~5-10 minutes, tell the user before calling). Optionally
        seed retrieval from a specific paper with seed_arxiv_id (question may then be empty ,
        it is derived from the paper). If finished reports already cover a similar question,
        this returns JSON {status:"similar_reports_exist", reports:[...]} WITHOUT running ,
        present those options and let the user pick reuse (retrieve_research/ask_research)
        re-call with force_new=true to run anyway (seeded runs skip the check). Every arXiv id
        cited in the result exists in the corpus; citations come back as markdown links, and the
        report embeds a citation story graph (PNG + interactive HTML). Returns the review as
        markdown. After it completes, use list_report_papers / ask_paper / ask_research for
        follow-ups instead of re-running.
    """
    effort = max(0, min(5, effort))
    seed = seed_arxiv_id.strip()
    if not question.strip() and not seed:
        return "ERROR: provide a question, a seed_arxiv_id, or both."
    if not force_new and not seed:
        try:
            similar = await _similar_runs(question)
        # matching is advisory, never blocks research
        except Exception:  # noqa: BLE001
            similar = []
        if similar:
            return json.dumps(
                {
                    "status": "similar_reports_exist",
                    "message": (
                        "Finished reports already cover similar questions. Ask the user "
                        "whether to reuse one (retrieve_research / ask_research / "
                        "list_report_papers) or run fresh research; call deep_research "
                        "again with force_new=true to run."
                    ),
                    "reports": similar,
                }
            )
    # trajectory selection is a consensus quota over PPR, gated by the pairwise judge
    args = [
        sys.executable,
        str(_RUN),
        question,
        f"--set-effort={effort}",
        "--set-rank=trajectory",
    ]
    if seed:
        args.append(f"--set-seed={seed}")
    async with _slot:  # one 3090: runs serialize, the server stays responsive
        proc = await asyncio.create_subprocess_exec(
            *args,
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
    # the deep loop logs a line per round, so the last match is the final report
    for m in _DONE.finditer(stdout):  # noqa: B007
        pass
    if m is None:
        return (
            f"ERROR: run produced no report (exit {proc.returncode}).\n\n"
            + (stdout + stderr)[-2000:]
        )
    return _finish_report(Path(m.group(1)))


@_tool()
def search_papers(query: str, k: int = 10) -> str:
    """
    Keyword-search paper titles across the 3M-paper arXiv corpus (fast, no GPU)

        For follow-up checks like 'is there work on X the review missed?'. Returns JSON rows
        (arxiv_id, title, year, category, url). Lexical title match, for semantic retrieval run
        deep_research instead.
    """
    from graphiv.core.store import Store

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
                "url": f"https://arxiv.org/abs/{n.arxiv_id}",
            }
            for n in rows
        ]
    )


@_tool()
def paper_details(arxiv_id: str) -> str:
    """
    Full metadata for one paper: title, authors, year, category, abstract, and how many

        papers cite it corpus-wide. Returns JSON; 'error' key if the id is unknown.
    """
    import psycopg

    with psycopg.connect(PG_DSN) as conn:
        row: tuple[Any, ...] | None = conn.execute(
            "SELECT title, authors, year, primary_category, abstract"
            " FROM paper_meta WHERE arxiv_id = %s",
            (arxiv_id,),
        ).fetchone()
    if row is None:
        return json.dumps({"error": f"unknown arXiv id: {arxiv_id}"})
    from graphiv.core.store import Store

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


def _pick_run(research_id: str) -> Path | None:
    """
    research_id = report slug, optionally 'slug/config' to pin a config
    """
    slug, _, cfg = research_id.strip().strip("/").partition("/")
    d = _OUT / slug
    if not d.is_dir():
        return None
    cfgs = [c for c in sorted(d.iterdir()) if (c / "report.md").exists()]
    if not cfgs:
        return None
    return next((c for c in cfgs if c.name == cfg), cfgs[-1])


@_tool()
def list_reports() -> str:
    """
    List previously generated reports (slug + configs + question + date + paper count)

        for retrieve_research / ask_research / list_report_papers.
    """
    return json.dumps(_runs_index())


@_tool()
async def similar_reports(question: str) -> str:
    """
    Find finished reports whose research question substantially covers *question*

        Cheap (one local LLM call, no GPU run). Use for 'have we already researched X?' or
        before suggesting deep_research. Returns a JSON list (slug, config, question, date,
        n_papers) for retrieve_research / ask_research / list_report_papers; empty = none.
    """
    return json.dumps(await _similar_runs(question))


@_tool()
def retrieve_research(research_ids: list[str]) -> str:
    """
    Retrieve finished research reports by research_id (see list_reports /

        similar_reports). Returns the full report markdown; multiple ids (max 3) come back
        concatenated with id banners, use that to put two findings side by side. A
        research_id is the report slug, optionally 'slug/config' to pin one config.
    """
    ids = [i for i in (s.strip() for s in research_ids) if i]
    if not ids:
        return "ERROR: provide at least one research_id (use list_reports)."
    if len(ids) > 3:
        return "ERROR: at most 3 reports per call."
    parts: list[str] = []
    for rid in ids:
        pick = _pick_run(rid)
        if pick is None:
            return f"ERROR: no finished report for research_id '{rid}' (use list_reports)."
        parts.append(_finish_report(pick / "report.md"))
    if len(parts) == 1:
        return parts[0]
    return "\n\n---\n\n".join(
        f"[research_id: {rid}]\n\n{md}" for rid, md in zip(ids, parts, strict=True)
    )


@_tool()
def list_report_papers(research_id: str) -> str:
    """
    The cohort behind a deep run: every landmark paper with its reader summary, role

        (foundational/core/frontier/adjacent/survey), relevance grade, scores, and arxiv link.
        Use this (not the report text) to answer 'which papers did you find?'-style follow-ups.
        Returns a JSON list; 'error' if the run predates papers.json.
    """
    pick = _pick_run(research_id)
    if pick is None:
        return json.dumps({"error": f"no finished report for '{research_id}'"})
    pj = pick / "papers.json"
    if not pj.exists():
        return json.dumps({"error": "this run predates the cohort artifact (papers.json); re-run"})
    return pj.read_text(encoding="utf-8")


@_tool()
async def ask_paper(arxiv_id: str, question: str) -> str:
    """
    Answer a question about ONE specific paper from its full text (lazy-fetched, cached)

        For 'what exactly did <paper> do about X?' follow-ups after a report. Slower than
        paper_details (reads the paper); grounded, says so when the text doesn't address it.
    """
    from graphiv.core.llm import NO_THINK, chat
    from graphiv.core.store import Store
    from graphiv.generate.fulltext import extract_salient

    store = Store(PG_DSN)
    try:
        meta = store.meta_for(arxiv_id)
    finally:
        store.close()
    if meta is None:
        return f"ERROR: unknown arXiv id: {arxiv_id}"
    title, _, _, abstract = meta
    text = extract_salient(arxiv_id) or abstract
    if not text:
        return f"ERROR: no text available for {arxiv_id}"
    sys_p = (
        "Answer the question about this ONE paper using ONLY the provided text. Quote "
        "numbers when present. If the text does not address the question, say so plainly."
    )
    user = f"PAPER: {title} (arXiv:{arxiv_id})\n\nTEXT:\n{text[:24000]}\n\nQUESTION: {question}"
    out, _, _ = await chat(MAP_MODEL, sys_p, user, 0.2, 900, extra_body=NO_THINK)
    return out.strip() or "(no answer produced)"


@_tool()
async def ask_research(research_ids: list[str], question: str) -> str:
    """
    Answer a follow-up question over finished deep runs (report + paper cohort) without

        re-running research. Cites arXiv ids from the cohorts. One id for 'compare X and Y
        from the report'-style questions; multiple ids (max 3) answer ACROSS reports ,
        'combine the findings of A and B', 'what does A add over B?'. A research_id is the
        report slug, optionally 'slug/config' (see list_reports / similar_reports).
    """
    from graphiv.core.llm import NO_THINK, chat

    ids = [i for i in (s.strip() for s in research_ids) if i]
    if not ids:
        return "ERROR: provide at least one research_id (use list_reports)."
    if len(ids) > 3:
        return "ERROR: at most 3 reports per call."
    picks: list[tuple[str, Path]] = []
    for rid in ids:
        pick = _pick_run(rid)
        if pick is None:
            return f"ERROR: no finished report for research_id '{rid}' (use list_reports)."
        picks.append((rid, pick))
    r_budget, c_budget = 26000 // len(picks), 14000 // len(picks)
    blocks: list[str] = []
    for rid, pick in picks:
        report = (pick / "report.md").read_text(encoding="utf-8")
        papers = ""
        pj = pick / "papers.json"
        if pj.exists():
            papers = pj.read_text(encoding="utf-8")
        blocks.append(
            f"=== RESEARCH {rid} ===\nREVIEW:\n{report[:r_budget]}"
            + f"\n\nCOHORT:\n{papers[:c_budget]}"
        )
    sys_p = (
        "You answer questions using ONLY the provided literature review(s) and their paper "
        "cohort JSON (per-paper summaries + roles + grades). With multiple reviews, "
        "synthesize across them and name which review a finding came from when they "
        "differ. Cite arXiv:<id> for every claim; ids must come from the provided "
        "material. If the material does not answer the question, say so and suggest "
        "running deep_research with a sharper question."
    )
    user = "\n\n".join(blocks) + f"\n\nQUESTION: {question}"
    out, _, _ = await chat(MAP_MODEL, sys_p, user, 0.3, 1200, extra_body=NO_THINK)
    from graphiv.generate.narrate import linkify

    return linkify(out.strip()) or "(no answer produced)"


@_prompt()
def deep_research_flow(interest: str) -> str:
    """
    Guided flow: refine a freeform interest into one question, then run deep research
    """
    return (
        f"The user wants a literature review about: {interest}\n\n"
        "1. Call refine_question with their text. Show the user ALL candidate questions and "
        "let them pick or edit one — do not pick silently. Ask the clarifying_question only "
        "if it is non-empty. If the user names a specific paper, you may skip refinement and "
        "pass its id as seed_arxiv_id instead.\n"
        "2. Tell the user the deep run takes ~5-10 minutes, then call "
        "deep_research(chosen_question, effort=4[, seed_arxiv_id=...]).\n"
        "3. If deep_research returns status=similar_reports_exist instead of a review, "
        "past reports already cover the question: show them (question, date, paper count) "
        "and ask whether to reuse one (retrieve_research / ask_research) or run fresh "
        "(deep_research with force_new=true).\n"
        "4. Present the returned review verbatim (it is fully cited; citations are links and "
        "the graph link is interactive).\n"
        "5. For follow-ups, DO NOT re-run or re-summarize the markdown: use "
        "list_report_papers (the cohort), ask_research (questions over one or MORE reports — also how to combine two findings), ask_paper "
        "(one paper, full text), or search_papers/paper_details (corpus checks)."
    )


def _register_http_routes() -> None:
    """
    Static run artifacts + the run dashboard (http transport only)
    """
    from starlette.requests import Request
    from starlette.responses import (
        FileResponse,
        PlainTextResponse,
        Response,
    )  # noqa: PLC0415

    suffixes = {".png", ".html", ".json", ".md", ".tex", ".bib", ".pdf", ".txt"}
    aid_re = re.compile(r"^(\d{4}\.\d{4,5}|[a-z][a-z.-]*/\d{7})$", re.I)

    @mcp.custom_route("/files/{path:path}", methods=["GET"])
    async def files(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        rel = str(request.path_params["path"])  # pyright: ignore[reportAny]
        target = (_OUT / rel).resolve()
        if not str(target).startswith(str(_OUT.resolve()) + os.sep):
            return PlainTextResponse("forbidden", status_code=403)
        if not target.is_file() or target.suffix.lower() not in suffixes:
            return PlainTextResponse("not found", status_code=404)
        return FileResponse(target)

    @mcp.custom_route("/pdf/{arxiv_id:path}", methods=["GET"])
    async def paper_pdf(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        """
        Serve a paper's PDF from the local store; `?fetch=1` pulls a miss from arXiv
        """
        aid = str(request.path_params["arxiv_id"])  # pyright: ignore[reportAny]
        if not aid_re.match(aid):
            return PlainTextResponse("bad arxiv id", status_code=400)
        from graphiv.download.fetch import fetch_pdf, local_pdf

        p = local_pdf(aid)
        if p is None and request.query_params.get("fetch") and not _READONLY:
            p = await asyncio.to_thread(fetch_pdf, aid)
        if p is None:
            return PlainTextResponse(
                "no local pdf (pass ?fetch=1 to pull from arXiv)", status_code=404
            )
        return FileResponse(p, media_type="application/pdf")

    from graphiv.serve import webui

    webui.register(mcp, _OUT, readonly=_READONLY)


def run(http: bool = False) -> None:
    """
    Start the server on the requested transport

    Args:
        http: serve loopback streamable-http instead of stdio, which sandboxed clients
            need because a hardened unit cannot spawn a stdio server inside /home.
    """
    if http:
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = _PORT
        _register_http_routes()
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
