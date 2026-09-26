"""
One paper's full text, at whichever depth the caller asked for

The caller invents the schema, so two questions pull different fields out of one paper
"""

from __future__ import annotations

import json
import logging
from typing import Any

import psycopg

from src.mcp.state import Handles
from src.report.fulltext import FullText
from src.report.fulltext import read_paper as read_html
from src.report.table import Column, Design, extract

LOG = logging.getLogger(__name__)

SECTION_CHARS = 4000
ABSTRACT_CHARS = 1200
DETAILS = "SELECT arxiv_id, title, abstract, date FROM papers WHERE arxiv_id = ANY(%s)"


def as_design(question: str, schema: list[dict[str, Any]]) -> Design:
    """
    The caller's schema as the columns the extractor fills

    Args:
        question: What the paper is being read for.
        schema: One entry per field, with a name, a description and optional choices.

    Returns:
        The design.
    """
    columns: list[Column] = []
    for entry in schema:
        name = " ".join(str(entry.get("name", "")).split()).replace(" ", "_").lower()
        if not name:
            continue
        options = tuple(
            " ".join(str(o).split()).lower() for o in entry.get("options", []) if str(o).strip()
        )
        kind = str(entry.get("kind", "choice" if options else "text")).lower()
        said = " ".join(str(entry.get("description", "")).split())[:60]
        columns.append(Column(name, kind, said, options))
    return Design(question, tuple(columns))


def contents(paper: FullText, abstract: str) -> dict[str, Any]:
    """
    What a paper holds, so the caller can ask for one section rather than the whole thing

    Args:
        paper: The parsed paper.
        abstract: Its abstract.

    Returns:
        The section names with their lengths, and the tables that carry numbers.
    """
    return {
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "abstract": abstract[:ABSTRACT_CHARS],
        "sections": [{"section": t, "chars": len(b)} for t, b in paper.sections.items()],
        "result_tables": len(paper.result_tables),
    }


def read_paper(
    handles: Handles,
    arxiv_ids: list[str],
    schema: list[dict[str, Any]] | None = None,
    question: str = "",
    want: str = "",
) -> str:
    """
    A paper's contents, one of its sections, or a schema the caller invented, filled from it

    Args:
        handles: The shared handles.
        arxiv_ids: The papers to read.
        schema: The fields to fill, each a name, a description and optional choices.
        question: What the papers are being read for, which the extractor is held to.
        want: A section keyword, which returns that section's text instead.

    Returns:
        The contents, the section or the filled rows, as json.
    """
    if not arxiv_ids:
        return json.dumps({"error": "name at least one arxiv_id"})
    with psycopg.connect(handles.dsn) as conn:
        meta = {
            str(r[0]): (str(r[1] or ""), str(r[2] or ""), str(r[3]))
            for r in conn.execute(DETAILS, (arxiv_ids,)).fetchall()
        }

    papers: list[FullText] = []
    missing: list[str] = []
    for arxiv_id in arxiv_ids:
        title = meta.get(arxiv_id, ("", "", ""))[0]
        found = read_html(handles.html, arxiv_id, title)
        if found is None or not found.sections:
            missing.append(arxiv_id)
            continue
        papers.append(found)

    if want:
        out: list[dict[str, Any]] = []
        for paper in papers:
            for name, body in paper.sections.items():
                if want.lower() in name.lower():
                    out.append(
                        {"arxiv_id": paper.arxiv_id, "section": name, "text": body[:SECTION_CHARS]}
                    )
            out += [
                {"arxiv_id": paper.arxiv_id, "table": t.render()[:SECTION_CHARS]}
                for t in paper.result_tables[:2]
                if want.lower() in ("result", "results", "table")
            ]
        return json.dumps({"sections": out, "no_full_text": missing}, indent=2)

    if not schema:
        return json.dumps(
            {
                "papers": [contents(p, meta.get(p.arxiv_id, ("", "", ""))[1]) for p in papers],
                "no_full_text": missing,
            },
            indent=2,
        )

    made = as_design(question, schema)
    filled = extract(
        handles.model,
        made,
        [
            (p, meta.get(p.arxiv_id, ("", "", ""))[2][:4], meta.get(p.arxiv_id, ("", "", ""))[1])
            for p in papers
        ],
    )
    LOG.info("read %d papers into %d rows", len(papers), len(filled))
    return json.dumps(
        {
            "columns": [{"name": c.name, "options": list(c.options)} for c in made.columns],
            "rows": [
                {"name": m.name, "papers": m.papers, "year": m.year, **m.values} for m in filled
            ],
            "no_full_text": missing,
        },
        indent=2,
    )
