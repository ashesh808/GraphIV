"""
The registrations and both transports, holding the graph and the model for the life of the process

Every tool body lives in its own file, so each one is callable and testable without a transport
The docstrings here are what the calling model reads, so they say when to call a tool and why
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from functools import wraps
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from apps.api.dashboard import mount
from apps.api.orchestration import RUNTIME_LOCK, Coordinator, ResearchRequest, safe_error
from src.mcp import find_runs as finding
from src.mcp import identify_areas as splitting
from src.mcp import mine as mining
from src.mcp import read_paper as reading
from src.mcp import recall_paper as recalling
from src.mcp import refine as refining
from src.mcp import retrieve as retrieving
from src.mcp import search_papers as searching
from src.mcp import what_cites as citing
from src.mcp import write_report as writing
from src.mcp.state import Serving, load, serving
from src.storage.runs import ReportStore

LOG = logging.getLogger(__name__)

# the public vhost reaches this, so an instance set read only registers nothing that writes a file
READONLY = os.environ.get("GRAPHIV_READONLY") == "1"
mcp = FastMCP("graphiv")
_TOOL_BODIES: list[tuple[Callable[..., str], bool]] = []


def tool(writes: bool = False) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """
    Registers one tool unless this instance is read only and the tool writes

    Args:
        writes: Whether calling it leaves anything on disk.

    Returns:
        The decorator.
    """

    def register(body: Callable[..., str]) -> Callable[..., str]:
        @wraps(body)
        def serialized(*args: Any, **kwargs: Any) -> str:
            with RUNTIME_LOCK:
                try:
                    return body(*args, **kwargs)
                except Exception as error:  # noqa: BLE001 - redact errors at the transport boundary
                    raise RuntimeError(safe_error(error)) from None

        _TOOL_BODIES.append((serialized, writes))
        return serialized if READONLY and writes else mcp.tool()(serialized)

    return register


@tool()
def refine(interest: str) -> str:
    """
    Turn a freeform research interest into the focused questions this corpus can answer.

    Call this first when the user described what they want rather than asking one question.
    Returns candidates, each tagged survey (the lineage a field is built on) or frontier (what
    people are doing right now), plus at most one clarifying question and the corpus titles the
    candidates were grounded in. Relay the clarifying question only when it is not empty.
    """
    return refining.refine(load(), interest)


@tool()
def identify_areas(
    question: str = "",
    cap: int = 4,
    people: list[dict[str, Any]] | None = None,
    arxiv_ids: list[str] | None = None,
    scope: str = "",
) -> str:
    """
    Split one question, people's work, or one list of papers, into areas read separately.

    For a question: call this when it spans more than one field, since a question spanning four
    fields embeds into a region that is none of them. Returns 2 to `cap` areas, each with the
    method words a paper in it would use and the question that area alone has to answer. Pass each
    one to retrieve. A question about a single field does not need this.

    For people: pass `people`, each {"name": as written on arXiv, "known": [one arxiv id they
    wrote, or more]}, which answers what a person or a team works on. arXiv has no author id, so
    the known paper picks which of the people sharing the name is meant: papers sharing coauthors
    and references with it are kept. A very common name can still pull in namesakes, so compare
    `kept` with `matched` and check the papers listed. Returns one area per topic their papers sit
    in, each with an `area_id`. Pass each `area_id` to retrieve, which keeps their own papers as
    the ranking, then write_report.

    For papers: pass `arxiv_ids` for a reading list, and `scope` when the user named what they
    care about, such as "knowledge graphs, citation graphs". Returns the areas inside the scope,
    each with an `area_id`, its papers and their count, plus how many papers fell outside it. Pass
    the `area_id` to mine to read those papers and to retrieve for the field around them.
    """
    return splitting.identify_areas(load(), question, cap, people, arxiv_ids, scope)


@tool()
def retrieve(
    question: str = "",
    arxiv_id: str = "",
    methods: list[str] | str | None = None,
    mode: str = "survey",
    date_min: str = "",
    date_max: str = "",
    seen: list[str] | None = None,
    effort: str = "standard",
    area_id: str = "",
    arxiv_ids: list[str] | None = None,
    people: list[dict[str, Any]] | None = None,
) -> str:
    """
    Retrieve and read one area, returning the papers worth reading and an id for the ranking.

    This is the main tool. It searches the corpus, ranks by position in the citation graph, holds
    the result to the area, cuts to the field's current era and has a reader grade every candidate
    as foundational, core, frontier, adjacent, survey or unrelated.

    Pick a mode. `survey` casts a wide net weighted to what the field cites, `frontier` a wide net
    weighted to what it is doing now, `ancestry` what led to one paper and `evolution` what came
    of it. Pass `arxiv_id` to start from that paper instead of the question; ancestry and
    evolution always start from a paper, the closest one to the question when none is named, and
    that paper leads the reply. `date_min` and `date_max` bound the dates, iso, both open when
    empty, so ancestry usually caps at the paper's date and evolution starts from it.

    Pass `methods` from identify_areas to hold the search to that area. Pass every earlier
    `query_id` as `seen`: the reply carries `new_share`, which is the share of this ranking
    nothing earlier already found, and a value near zero means you have renamed an area rather
    than opened a new one. Keep the `query_id` and pass it to mine and write_report.

    Pass an `area_id` from identify_areas, or `arxiv_ids`, to search the field around those papers
    from their own mean vector, with `question` defaulting to the area's name. Most of what comes
    back was written by others, so each paper says `given` when it is one of the papers passed.
    An `area_id` identify_areas made from `people` is not searched: their own papers are the
    ranking.

    Pass `people`, as identify_areas takes them, with a `question` to ask whether they work on it.
    Their papers in the topic closest to the question come back as the ranking, or `related`
    false with no ranking when the reader finds none of them about it. Keep the person out of
    `question`, since no paper names its own author.
    """
    return retrieving.retrieve(
        load(),
        question,
        arxiv_id,
        methods,
        mode,
        date_min,
        date_max,
        seen,
        effort,
        area_id,
        arxiv_ids,
        people,
    )


@tool()
def mine(
    query_id: str = "",
    arxiv_ids: list[str] | None = None,
    question: str = "",
    mode: str = "survey",
    effort: str = "standard",
    area_id: str = "",
) -> str:
    """
    Read the citation graph around a set of papers for what the field argues about.

    Pass the `query_id` a retrieve call returned, an `area_id` from identify_areas to read an
    author's or a list's own papers, or name papers yourself with `arxiv_ids` and a `question`.
    Returns the magnets, which are the papers this set takes positions on, with the counts per
    intent; the lineages, which are dated paths through the graph showing how the field
    got here; the disputes, which are the sentences in which one paper says another is wrong; the
    successors, which are recent papers citing this set and so need no citations of their own; and
    the connectors, which are papers that bridge two papers in the set without being in it.
    """
    return mining.mine(load(), query_id, arxiv_ids, question, mode, effort, area_id)


@tool()
def read_paper(
    arxiv_ids: list[str],
    schema: list[dict[str, Any]] | dict[str, Any] | None = None,
    question: str = "",
    want: str | list[str] = "",
) -> str:
    """
    Read the full text of papers, at whichever depth you need.

    With neither `schema` nor `want`, returns each paper's section list so you can see what it
    holds. With `want`, one or more keywords such as "limitations" or "threat model, defenses",
    returns the sections whose titles carry any of them, and when no title does, the sentences
    that carry the most of them. With `schema`, you invent the fields and this fills them from
    each paper's own method and results sections: a list of entries with a name, a description and
    optional `options` to force a closed answer, or a mapping of name to description. Use the
    schema form to compare papers on axes you chose. Anything the paper does not say comes back as
    "n/a" rather than guessed.
    """
    return reading.read_paper(load(), arxiv_ids, schema, question, want)


@tool(writes=True)
def write_report(
    query_ids: list[str],
    title: str = "",
    sections: list[dict[str, str] | str] | str | None = None,
    effort: str = "standard",
    end: bool = True,
    question: str = "",
) -> str:
    """
    Assemble the document and write it to disk.

    Pass every `query_id` from this session, and the question as the reader asked it as `question`,
    since the report is mined, written and answered against it, while `title` names the document
    and stands in for the question when it is empty. The report carries what the area
    currently is with each paper's role, how it got here as dated lineages, a table comparing the
    methods on axes this question decides, what has just appeared against it, and what is
    contested in the citing authors' own words. Pass your own prose as `sections`, each a title
    and a body or markdown with headings, and it is carried as written. Every arXiv id is then
    checked against the corpus: a typo is corrected and an id no paper carries is cut out. Setting
    `end` false keeps the session open for a follow-up.
    """
    return writing.write_report(load(), query_ids, title, sections, effort, end, question)


@tool()
def what_cites(
    arxiv_id: str, intents: list[str] | None = None, since: str = "", limit: int = 20
) -> str:
    """
    Who cited one paper and what they said about it.

    Returns the citing paper, the intent and the sentence. `extends` names the work that built on
    it, `critiques` names the objections the field has already written down, and `compares` names
    who benchmarked against it. Call this on any paper that keeps appearing, to find out whether
    it is famous for working or famous for not working.
    """
    return citing.what_cites(load(), arxiv_id, intents, since, limit)


@tool()
def search_papers(text: str, limit: int = 20, before: str = "", after: str = "") -> str:
    """
    Plain closeness search over the corpus, with no citation graph and no reader.

    Use this to turn a paper you know by name into an id, or to check whether a field is genuinely
    empty when retrieve came back thin. To find papers from what they did or argued, use
    recall_paper instead.
    """
    return searching.search_papers(load(), text, limit, before, after)


@tool()
def recall_paper(
    description: str, author: str = "", before: str = "", after: str = "", limit: int = 10
) -> str:
    """
    Find particular papers from a description of what they did, found or argued.

    Use this rather than retrieve when the user wants specific papers, such as "papers showing X"
    or "the paper that claimed Y", since retrieve ranks what a whole field cites and can bury a few
    recent papers on a narrow claim. A model writes the abstract such a paper would have, the
    corpus is searched with it and with the description, and a reader picks the matches. Pass a
    name the user remembers as `author`. Returns the matches first, each with its abstract.
    """
    return recalling.recall_paper(load(), description, author, before, after, limit)


@tool()
def find_runs(question: str = "", slug: str = "", limit: int = 10) -> str:
    """
    Find a report this server already wrote, and read it back.

    Call this before doing the work: a question this corpus was already asked has a document on
    disk, and reading it costs nothing. With `question`, returns the past runs closest to it by
    meaning, each with its slug, the question it answered, its date, its paper count and its link.
    With `slug`, returns that run's document and the papers behind it. With neither, returns the
    newest runs. A close match is the report to build on rather than repeat.
    """
    return finding.find_runs(load(), question, slug, limit)


class BearerTokenMiddleware:
    """Protect every application route while preserving the MCP ASGI lifespan."""

    def __init__(self, app: ASGIApp, *, token: str, required: bool) -> None:
        self.app = app
        self.token = token.encode()
        self.required = required

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Authenticate HTTP requests without intercepting ASGI lifespan events."""
        if scope["type"] != "http" or scope.get("path") in ("/health/live", "/health/ready"):
            await self.app(scope, receive, send)
            return
        if not self.token and self.required:
            await JSONResponse({"error": "API authentication is not configured"}, status_code=503)(
                scope, receive, send
            )
            return
        if self.token:
            header = next(
                (value for name, value in scope["headers"] if name.lower() == b"authorization"), b""
            )
            scheme, _, credential = header.partition(b" ")
            if scheme.lower() != b"bearer" or not secrets.compare_digest(credential, self.token):
                await JSONResponse(
                    {"error": "A valid bearer token is required"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _runtime_status() -> dict[str, Any]:
    from src.mcp import state

    return state.runtime_status()


def _threaded_tool(
    body: Callable[..., str], readiness: Callable[[], dict[str, Any]]
) -> Callable[..., Any]:
    """Keep synchronous corpus/model calls and lock waits off the HTTP event loop."""

    @wraps(body)
    async def invoke(*args: Any, **kwargs: Any) -> str:
        status = readiness()
        if not status["ready"]:
            reasons = "; ".join(str(reason) for reason in status.get("reasons", []))
            raise RuntimeError(f"Research runtime is not ready: {reasons}")
        return await asyncio.to_thread(body, *args, **kwargs)

    return invoke


def build_http_app(
    settings: Serving,
    role: str = "both",
    *,
    status_callback: Callable[[], dict[str, Any]] | None = None,
    coordinator: Coordinator | None = None,
    report_store: ReportStore | None = None,
) -> Any:
    """Build a lazy HTTP runtime: health and saved reports do not load the corpus."""
    engine = FastMCP("graphiv-dashboard" if role == "frontend" else "graphiv")
    secure(engine, settings)
    engine.settings.port = settings.frontend_port if role == "frontend" else settings.api_port
    if role != "api":
        if report_store is None:
            from src.mcp import state

            accessor = getattr(state, "report_store", None)
            report_store = accessor() if accessor else None
        mount(
            engine,
            settings.runs,
            settings.pdfs,
            settings.fetch if role != "frontend" else False,
            report_store=report_store,
        )

    token = os.environ.get("GRAPHIV_API_TOKEN", "").strip()
    required = (
        os.environ.get("GRAPHIV_RUNTIME") == "azure"
        or os.environ.get("GRAPHIV_REQUIRE_AUTH") == "1"
        or settings.host not in ("127.0.0.1", "localhost", "::1")
    )
    jobs = coordinator or Coordinator()
    status_callback = status_callback or (
        (lambda: {"ready": True, "reasons": [], "scope": "saved-reports"})
        if role == "frontend"
        else _runtime_status
    )

    def readiness() -> dict[str, Any]:
        try:
            status = dict(status_callback())
        except Exception as error:  # noqa: BLE001 - health checks must return sanitized failures
            status = {"ready": False, "reasons": [safe_error(error)]}
        reasons = list(status.get("reasons") or [])
        if required and not token:
            reasons.append("API authentication is not configured")
        status["reasons"] = reasons
        status["ready"] = bool(status.get("ready")) and not reasons
        return status

    if role != "frontend":
        for body, writes in _TOOL_BODIES:
            if not READONLY or not writes:
                engine.add_tool(_threaded_tool(body, readiness))

    @engine.custom_route("/health/live", methods=["GET"])
    async def live(request: Request) -> JSONResponse:
        return JSONResponse({"status": "alive"})

    @engine.custom_route("/health/ready", methods=["GET"])
    async def ready(request: Request) -> JSONResponse:
        status = readiness()
        return JSONResponse(status, status_code=200 if status["ready"] else 503)

    if role != "frontend":

        @engine.custom_route("/api/research", methods=["POST"])
        async def research(request: Request) -> JSONResponse:
            if READONLY:
                return JSONResponse({"error": "This instance is read only"}, status_code=403)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 65536:
                    return JSONResponse({"error": "Research request is too large"}, status_code=413)
            try:
                asked = ResearchRequest.model_validate(json.loads(body))
            except (ValueError, UnicodeError, ValidationError):
                return JSONResponse(
                    {
                        "error": (
                            "Pass a question (1–4000 characters), a supported mode, "
                            "and quick/standard/deep effort"
                        )
                    },
                    status_code=422,
                )
            status = readiness()
            if not status["ready"]:
                return JSONResponse(
                    {"error": "Research runtime is not ready", "reasons": status["reasons"]},
                    status_code=503,
                )
            try:
                job = jobs.submit(asked)
            except OverflowError as error:
                return JSONResponse(
                    {"error": str(error)}, status_code=429, headers={"Retry-After": "30"}
                )
            return JSONResponse(job | {"status_url": f"/api/jobs/{job['id']}"}, status_code=202)

        @engine.custom_route("/api/jobs/{job_id}", methods=["GET"])
        async def job_status(request: Request) -> JSONResponse:
            job = jobs.get(str(request.path_params["job_id"]))
            return JSONResponse(
                job if job else {"error": "No such research job"}, status_code=200 if job else 404
            )

        @engine.custom_route("/api/corpus/validate", methods=["POST"])
        async def validate_corpus_ids(request: Request) -> JSONResponse:
            if not readiness()["ready"]:
                return JSONResponse({"error": "Research runtime is not ready"}, status_code=503)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 131072:
                    return JSONResponse({"error": "Too many paper identifiers"}, status_code=413)
            try:
                parsed = json.loads(body)
                ids = parsed.get("ids") if isinstance(parsed, dict) else None
                if (
                    not isinstance(ids, list)
                    or not 1 <= len(ids) <= 1000
                    or any(not isinstance(item, str) or not 1 <= len(item) <= 80 for item in ids)
                ):
                    raise ValueError("Pass 1–1000 paper identifiers")
            except (ValueError, UnicodeError):
                return JSONResponse({"error": "Pass 1–1000 paper identifiers"}, status_code=422)

            def records() -> list[dict[str, Any]]:
                from src.storage.corpus import open_corpus

                return [
                    {
                        "arxiv_id": row[0],
                        "title": row[1],
                        "abstract": row[2],
                        "date": row[3].isoformat() if row[3] else None,
                        "primary_category": row[4],
                        "authors": row[5],
                    }
                    for row in open_corpus(load().dsn).records(list(dict.fromkeys(ids)))
                ]

            found = await asyncio.to_thread(records)
            known = {row["arxiv_id"] for row in found}
            return JSONResponse(
                {"papers": found, "missing": [item for item in ids if item not in known]}
            )

    app = engine.streamable_http_app()
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application: Any) -> AsyncIterator[None]:
        from src.mcp import state

        prepare = getattr(state, "prepare_runtime", None) if role != "frontend" else None

        async def prepare_background() -> None:
            if not callable(prepare):
                return
            try:
                await asyncio.to_thread(prepare)
            except Exception as error:  # noqa: BLE001 - startup preparation cannot stop HTTP health
                LOG.warning("Runtime preparation failed: %s", safe_error(error))

        prepare_task = asyncio.create_task(prepare_background()) if prepare else None
        async with original_lifespan(application):
            try:
                yield
            finally:
                jobs.close()
                if prepare_task:
                    prepare_task.cancel()
                    try:
                        await prepare_task
                    except asyncio.CancelledError:
                        pass

    app.router.lifespan_context = lifespan
    app.add_middleware(BearerTokenMiddleware, token=token, required=required)
    return app


def run(
    http: bool = False,
    role: str = "both",
    host: str | None = None,
    port: int | None = None,
) -> None:
    """
    Serves the tools, over stdio by default

    The frontend role serves a second server carrying no tools at all, so it opens neither the
    store nor the graph and cannot reach the corpus.

    Args:
        http: Serve streamable-http instead of stdio.
        role: api for the tools, frontend for the dashboard, both for one listener carrying each.
        host: Override the configured HTTP bind address.
        port: Override the configured port for the selected HTTP role.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = serving()
    if host is not None:
        settings = replace(settings, host=host)
    if port is not None:
        settings = (
            replace(settings, frontend_port=port)
            if role == "frontend"
            else replace(settings, api_port=port)
        )
    if not http:
        _ = load()
        mcp.run()
        return
    app = build_http_app(settings, role)
    selected_port = settings.frontend_port if role == "frontend" else settings.api_port
    LOG.info("serving %s on %s:%d, read only %s", role, settings.host, selected_port, READONLY)
    uvicorn.run(app, host=settings.host, port=selected_port, access_log=False)


def secure(server: FastMCP, settings: Serving) -> None:
    """
    Binds one server to its interface, and to the names it answers to

    A transport with no allowed host answers only what it is bound to, which is what rejects a
    proxy that forwards its own name.

    Args:
        server: The server to configure.
        settings: The transport half of the config.
    """
    server.settings.host = settings.host
    if settings.allowed_hosts:
        server.settings.transport_security = TransportSecuritySettings(
            allowed_hosts=settings.allowed_hosts,
            allowed_origins=[f"https://{one}" for one in settings.allowed_hosts],
        )
