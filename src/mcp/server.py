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

from src.mcp import identify_areas as splitting
from src.mcp import mine as mining
from src.mcp import read_paper as reading
from src.mcp import refine as refining
from src.mcp import retrieve as retrieving
from src.mcp import search_papers as searching
from src.mcp import what_cites as citing
from src.mcp import write_report as writing
from src.mcp.dashboard import mount
from src.mcp.state import load

LOG = logging.getLogger(__name__)

PORT = int(os.environ.get("GRAPHIV_MCP_PORT", "8756"))
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
def identify_areas(question: str, cap: int = 4) -> str:
    """
    Split one question into the areas that have to be searched separately.

    Call this when a question spans more than one field, since a question spanning four fields
    embeds into a region that is none of them. Returns 2 to `cap` areas, each with the method
    words a paper in it would use and the question that area alone has to answer. Pass each one
    to retrieve. A question about a single field does not need this.
    """
    return splitting.identify_areas(load(), question, cap)


@tool()
def retrieve(
    question: str,
    methods: list[str] | None = None,
    mode: str = "survey",
    asked: str = "",
    seen: list[str] | None = None,
    effort: str = "standard",
) -> str:
    """
    Retrieve and read one area, returning the papers worth reading and an id for the ranking.

    This is the main tool. It searches the corpus, ranks by position in the citation graph, holds
    the result to the area, cuts to the field's current era and has a reader grade every candidate
    as foundational, core, frontier, adjacent, survey or unrelated.

    Pass `methods` from identify_areas to hold the search to that area. Pass every earlier
    `query_id` as `seen`: the reply carries `new_share`, which is the share of this ranking
    nothing earlier already found, and a value near zero means you have renamed an area rather
    than opened a new one. Keep the `query_id` and pass it to mine and write_report.
    """
    return retrieving.retrieve(load(), question, methods, mode, asked, seen, effort)


@tool()
def mine(
    query_id: str = "",
    arxiv_ids: list[str] | None = None,
    question: str = "",
    mode: str = "survey",
    effort: str = "standard",
) -> str:
    """
    Read the citation graph around a set of papers for what the field argues about.

    Pass the `query_id` a retrieve call returned, or name papers yourself with `arxiv_ids` and a
    `question`. Returns the magnets, which are the papers this set takes positions on, with the
    counts per intent; the lineages, which are dated paths through the graph showing how the field
    got here; the disputes, which are the sentences in which one paper says another is wrong; the
    successors, which are recent papers citing this set and so need no citations of their own; and
    the connectors, which are papers that bridge two papers in the set without being in it.
    """
    return mining.mine(load(), query_id, arxiv_ids, question, mode, effort)


@tool()
def read_paper(
    arxiv_ids: list[str],
    schema: list[dict[str, Any]] | None = None,
    question: str = "",
    want: str = "",
) -> str:
    """
    Read the full text of papers, at whichever depth you need.

    With neither `schema` nor `want`, returns each paper's section list so you can see what it
    holds. With `want`, returns the text of the sections matching that keyword, such as
    "limitations" or "results". With `schema`, you invent the fields and this fills them from each
    paper's own method and results sections: one entry per field with a name, a description and
    optional `options` to force a closed answer. Use the schema form to compare papers on axes you
    chose. Anything the paper does not say comes back as "n/a" rather than guessed.
    """
    return reading.read_paper(load(), arxiv_ids, schema, question, want)


@tool(writes=True)
def write_report(
    query_ids: list[str],
    title: str = "",
    sections: list[dict[str, str]] | None = None,
    effort: str = "standard",
    end: bool = True,
) -> str:
    """
    Assemble the document and write it to disk.

    Pass every `query_id` from this session. The report carries what the area currently is with
    each paper's role, how it got here as dated lineages, a table comparing the methods on axes
    this question decides, what has just appeared against it, and what is contested in the citing
    authors' own words. Pass your own prose as `sections`, each a title and a body, and it is
    carried as written. Every arXiv id is then checked against the corpus: a typo is corrected and
    an id no paper carries is cut out. Setting `end` false keeps the session open for a follow-up.
    """
    return writing.write_report(load(), query_ids, title, sections, effort, end)


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
    empty when retrieve came back thin. It is not the main path.
    """
    return searching.search_papers(load(), text, limit, before, after)


def run(http: bool = False) -> None:
    """
    Serves the tools, over stdio by default

    Args:
        http: Serve streamable-http on `GRAPHIV_MCP_PORT` instead.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    handles = load()
    LOG.info("serving %d tools, read only %s", len(mcp._tool_manager.list_tools()), READONLY)
    if http:
        mount(mcp, handles.runs, handles.pdfs)
        mcp.settings.port = PORT
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
