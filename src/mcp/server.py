"""
The registrations and both transports, holding the graph and the model for the life of the process

Every tool body lives in its own file, so each one is callable and testable without a transport
The docstrings here are what the calling model reads, so they say when to call a tool and why
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

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
from src.mcp.dashboard import mount
from src.mcp.state import Serving, load, serving

LOG = logging.getLogger(__name__)

# the public vhost reaches this, so an instance set read only registers nothing that writes a file
READONLY = os.environ.get("GRAPHIV_READONLY") == "1"
mcp = FastMCP("graphiv")


def tool(writes: bool = False) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """
    Registers one tool unless this instance is read only and the tool writes

    Args:
        writes: Whether calling it leaves anything on disk.

    Returns:
        The decorator.
    """

    def register(body: Callable[..., str]) -> Callable[..., str]:
        return body if READONLY and writes else mcp.tool()(body)

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


def run(http: bool = False, role: str = "both") -> None:
    """
    Serves the tools, over stdio by default

    The frontend role serves a second server carrying no tools at all, so it opens neither the
    store nor the graph and cannot reach the corpus.

    Args:
        http: Serve streamable-http instead of stdio.
        role: api for the tools, frontend for the dashboard, both for one listener carrying each.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = serving()
    if not http:
        _ = load()
        mcp.run()
        return
    if role == "frontend":
        page = FastMCP("graphiv-dashboard")
        secure(page, settings)
        page.settings.port = settings.frontend_port
        mount(page, settings.runs, settings.pdfs)
        LOG.info("serving the dashboard on %s:%d", page.settings.host, page.settings.port)
        page.run(transport="streamable-http")
        return
    secure(mcp, settings)
    mcp.settings.port = settings.api_port
    if role != "api":
        mount(mcp, settings.runs, settings.pdfs, settings.fetch)
    _ = load()
    LOG.info(
        "serving %d tools on %s:%d, read only %s",
        len(mcp._tool_manager.list_tools()),
        mcp.settings.host,
        mcp.settings.port,
        READONLY,
    )
    mcp.run(transport="streamable-http")


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
