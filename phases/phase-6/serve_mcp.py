"""MCP server for GraphIV — deep research + refinement + follow-up tools (stdio or http).

Designed for a *small local host model* (librechat on the same llama-router): the server owns
all judgment (question refinement runs on the local LLM here, not in the host), so the host
only relays tool results. deep_research shells out to run.py (a crash or CUDA OOM kills the
run, not the server) behind a single-slot lock — one 3090, one PG, one resident model.

The http transport also serves run artifacts (`/files/...`: figures, graph.png/graph.html,
papers.json, report.pdf) and the run dashboard (webui routes at `/` and `/run/...`); returned
markdown rewrites relative asset paths to `$GRAPHIV_PUBLIC_URL` so images render in the client.

    uv run python phases/phase-6/serve_mcp.py          # stdio transport
    uv run python phases/phase-6/serve_mcp.py --http   # streamable-http on 127.0.0.1
                                                       #   (port: $GRAPHIV_MCP_PORT, default 8756)
"""

from __future__ import annotations

import asyncio
import json
import os
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
_PORT = int(os.environ.get("GRAPHIV_MCP_PORT", "8756"))
PUBLIC_URL = os.environ.get("GRAPHIV_PUBLIC_URL", f"http://127.0.0.1:{_PORT}").rstrip(
    "/"
)

mcp = FastMCP("graphiv")
_slot = asyncio.Lock()

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


def _rewrite_assets(md: str, slug: str, cfg: str) -> str:
    """Relative run assets (figures/*.png, graph.png, graph.html) -> served absolute URLs."""
    base = f"{PUBLIC_URL}/files/{slug}/{cfg}"
    return re.sub(r"\]\((figures/[^)]+|graph\.png|graph\.html)\)", rf"]({base}/\1)", md)


def _finish_report(report_path: Path) -> str:
    """Linkify (old reports were written bare) + rewrite asset URLs for the client."""
    from narrate import linkify  # noqa: PLC0415

    md = report_path.read_text(encoding="utf-8")
    cfg_dir = report_path.parent
    return _rewrite_assets(linkify(md), cfg_dir.parent.name, cfg_dir.name)


@mcp.tool()
async def refine_question(text: str) -> str:
    """Turn a freeform research interest into candidate literature-review questions.

    Call this FIRST when the user's request is broad or ambiguous. Present the returned
    candidates to the user and let them pick or edit one (never silently pick yourself);
    relay the clarifying_question only if non-empty. Then call deep_research with the chosen
    question. Fast (~seconds). Returns JSON: candidates[] + clarifying_question + probe
    (corpus titles the candidates are grounded in).
    """
    from llm import NO_THINK, chat, parse_json  # noqa: PLC0415
    from store import Store  # noqa: PLC0415

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


@mcp.tool()
async def deep_research(question: str, effort: int = 4, seed_arxiv_id: str = "") -> str:
    """Run GraphIV deep research: a grounded, cited literature review over all of arXiv.

    effort 0-5 trades latency for depth (3+ = judge-driven deep loop with full-PDF critique
    and figures; effort 4 takes ~5-10 minutes — tell the user before calling). Optionally
    seed retrieval from a specific paper with seed_arxiv_id (question may then be empty —
    it is derived from the paper). Every arXiv id cited in the result exists in the corpus;
    citations come back as markdown links, and the report embeds a citation story graph
    (PNG + interactive HTML). Returns the review as markdown. After it completes, use
    list_report_papers / ask_paper / ask_report for follow-ups instead of re-running.
    """
    effort = max(0, min(5, effort))
    seed = seed_arxiv_id.strip()
    if not question.strip() and not seed:
        return "ERROR: provide a question, a seed_arxiv_id, or both."
    args = [sys.executable, str(_RUN), question, f"--set-effort={effort}"]
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
    for m in _DONE.finditer(stdout):
        pass  # keep the last "done ->" (the deep loop logs intermediate rounds)
    if m is None:
        return (
            f"ERROR: run produced no report (exit {proc.returncode}).\n\n"
            + (stdout + stderr)[-2000:]
        )
    return _finish_report(Path(m.group(1)))


@mcp.tool()
def search_papers(query: str, k: int = 10) -> str:
    """Keyword-search paper titles across the 3M-paper arXiv corpus (fast, no GPU).

    For follow-up checks like 'is there work on X the review missed?'. Returns JSON rows
    (arxiv_id, title, year, category, url). Lexical title match — for semantic retrieval run
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
                "url": f"https://arxiv.org/abs/{n.arxiv_id}",
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


def _pick_run(slug: str, config: str) -> Path | None:
    d = _OUT / slug
    if not d.is_dir():
        return None
    cfgs = [c for c in sorted(d.iterdir()) if (c / "report.md").exists()]
    if not cfgs:
        return None
    return next((c for c in cfgs if c.name == config), cfgs[-1])


@mcp.tool()
def list_reports() -> str:
    """List previously generated reports (slug + configs + question) for get_report /
    list_report_papers / ask_report."""
    out: list[dict[str, object]] = []
    if _OUT.is_dir():
        for d in sorted(_OUT.iterdir()):
            cfgs = [c.name for c in d.iterdir() if (c / "report.md").exists()]
            if not cfgs:
                continue
            question = ""
            rj = d / cfgs[-1] / "run.json"
            if rj.exists():
                try:
                    question = str(json.loads(rj.read_text()).get("question", ""))
                except Exception:  # noqa: BLE001
                    pass
            out.append({"slug": d.name, "configs": cfgs, "question": question})
    return json.dumps(out)


@mcp.tool()
def get_report(slug: str, config: str = "") -> str:
    """Reload a previously generated report by slug (see list_reports). Returns markdown."""
    pick = _pick_run(slug, config)
    if pick is None:
        return f"ERROR: no finished report under slug '{slug}' (use list_reports)"
    return _finish_report(pick / "report.md")


@mcp.tool()
def list_report_papers(slug: str, config: str = "") -> str:
    """The cohort behind a deep run: every landmark paper with its reader summary, role
    (foundational/core/frontier/adjacent/survey), relevance grade, scores, and arxiv link.
    Use this (not the report text) to answer 'which papers did you find?'-style follow-ups.
    Returns a JSON list; 'error' if the run predates papers.json."""
    pick = _pick_run(slug, config)
    if pick is None:
        return json.dumps({"error": f"no finished report under slug '{slug}'"})
    pj = pick / "papers.json"
    if not pj.exists():
        return json.dumps(
            {"error": "this run predates the cohort artifact (papers.json); re-run"}
        )
    return pj.read_text(encoding="utf-8")


@mcp.tool()
async def ask_paper(arxiv_id: str, question: str) -> str:
    """Answer a question about ONE specific paper from its full text (lazy-fetched, cached).

    For 'what exactly did <paper> do about X?' follow-ups after a report. Slower than
    paper_details (reads the paper); grounded — says so when the text doesn't address it.
    """
    from fulltext import extract_salient  # noqa: PLC0415
    from llm import NO_THINK, chat  # noqa: PLC0415
    from store import Store  # noqa: PLC0415

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


@mcp.tool()
async def ask_report(slug: str, question: str, config: str = "") -> str:
    """Answer a follow-up question over a finished deep run (report + paper cohort) without
    re-running research. Cites arXiv ids from the cohort. Use after deep_research for
    'compare X and Y from the report', 'which paper had the best Z?', etc."""
    from llm import NO_THINK, chat  # noqa: PLC0415

    pick = _pick_run(slug, config)
    if pick is None:
        return f"ERROR: no finished report under slug '{slug}' (use list_reports)"
    report = (pick / "report.md").read_text(encoding="utf-8")
    papers = ""
    pj = pick / "papers.json"
    if pj.exists():
        papers = pj.read_text(encoding="utf-8")
    sys_p = (
        "You answer questions about a literature review using ONLY the review text and the "
        "paper cohort JSON (per-paper summaries + roles + grades). Cite arXiv:<id> for every "
        "claim; ids must come from the provided material. If the material does not answer "
        "the question, say so and suggest running deep_research with a sharper question."
    )
    user = f"REVIEW:\n{report[:26000]}\n\nCOHORT:\n{papers[:14000]}\n\nQUESTION: {question}"
    out, _, _ = await chat(MAP_MODEL, sys_p, user, 0.3, 1200, extra_body=NO_THINK)
    from narrate import linkify  # noqa: PLC0415

    return linkify(out.strip()) or "(no answer produced)"


@mcp.prompt()
def deep_research_flow(interest: str) -> str:
    """Guided flow: refine a freeform interest into one question, then run deep research."""
    return (
        f"The user wants a literature review about: {interest}\n\n"
        "1. Call refine_question with their text. Show the user ALL candidate questions and "
        "let them pick or edit one — do not pick silently. Ask the clarifying_question only "
        "if it is non-empty. If the user names a specific paper, you may skip refinement and "
        "pass its id as seed_arxiv_id instead.\n"
        "2. Tell the user the deep run takes ~5-10 minutes, then call "
        "deep_research(chosen_question, effort=4[, seed_arxiv_id=...]).\n"
        "3. Present the returned review verbatim (it is fully cited; citations are links and "
        "the graph link is interactive).\n"
        "4. For follow-ups, DO NOT re-run or re-summarize the markdown: use "
        "list_report_papers (the cohort), ask_report (questions over the review), ask_paper "
        "(one paper, full text), or search_papers/paper_details (corpus checks)."
    )


def _register_http_routes() -> None:
    """Static run artifacts + the run dashboard (http transport only)."""
    from starlette.requests import Request  # noqa: PLC0415
    from starlette.responses import (
        FileResponse,
        PlainTextResponse,
        Response,
    )  # noqa: PLC0415

    _SUFFIXES = {".png", ".html", ".json", ".md", ".tex", ".bib", ".pdf", ".txt"}
    _AID = re.compile(r"^(\d{4}\.\d{4,5}|[a-z][a-z.-]*/\d{7})$", re.I)

    @mcp.custom_route("/files/{path:path}", methods=["GET"])
    async def files(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        rel = str(request.path_params["path"])  # pyright: ignore[reportAny]
        target = (_OUT / rel).resolve()
        if not str(target).startswith(str(_OUT.resolve()) + os.sep):
            return PlainTextResponse("forbidden", status_code=403)
        if not target.is_file() or target.suffix.lower() not in _SUFFIXES:
            return PlainTextResponse("not found", status_code=404)
        return FileResponse(target)

    @mcp.custom_route("/pdf/{arxiv_id:path}", methods=["GET"])
    async def paper_pdf(
        request: Request,
    ) -> Response:  # pyright: ignore[reportUnusedFunction]
        """Serve a paper's PDF from the local store; `?fetch=1` pulls a miss from arXiv."""
        aid = str(request.path_params["arxiv_id"])  # pyright: ignore[reportAny]
        if not _AID.match(aid):
            return PlainTextResponse("bad arxiv id", status_code=400)
        from fetch import fetch_pdf, local_pdf  # noqa: PLC0415

        p = local_pdf(aid)
        if p is None and request.query_params.get("fetch"):
            p = await asyncio.to_thread(fetch_pdf, aid)
        if p is None:
            return PlainTextResponse(
                "no local pdf (pass ?fetch=1 to pull from arXiv)", status_code=404
            )
        return FileResponse(p, media_type="application/pdf")

    import webui  # noqa: PLC0415

    webui.register(mcp, _OUT)


if __name__ == "__main__":
    # --http: loopback streamable-http for sandboxed clients (librechat's hardened
    # unit can't spawn a stdio server inside /home); stdio stays the default.
    if "--http" in sys.argv[1:]:
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = _PORT
        _register_http_routes()
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
