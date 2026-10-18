"""
One paper's full text, at whichever depth the caller asked for

The caller invents the schema, so two questions pull different fields out of one paper
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import psycopg

from src.mcp.state import Handles
from src.report.fulltext import FullText
from src.report.fulltext import read_paper as read_html
from src.report.table import Column, Design, extract

LOG = logging.getLogger(__name__)

SECTION_CHARS = 4000
ABSTRACT_CHARS = 1200
SECTIONS_SHOWN = 4
PASSAGES = 12
PASSAGE_CHARS = (40, 600)
SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")
WORDS = re.compile(r"[a-z][a-z0-9-]{2,}")
DETAILS = "SELECT arxiv_id, title, abstract, date FROM papers WHERE arxiv_id = ANY(%s)"


def keywords(want: str | list[str]) -> list[str]:
    """
    The keywords one want names, whether a single word, a comma list or a list

    Args:
        want: What the caller asked to see.

    Returns:
        The keywords, lowercased.
    """
    raw = want if isinstance(want, list) else re.split(r",|;|/|\band\b", want)
    return [w.strip().lower() for w in raw if str(w).strip()]


def as_fields(schema: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    """
    A schema given as a list of fields or as a mapping of field name to its description

    Args:
        schema: Either shape.

    Returns:
        One entry per field with a name.
    """
    if isinstance(schema, list):
        return schema
    return [
        (
            {"name": name, **spec}
            if isinstance(spec, dict)
            else {"name": name, "description": str(spec)}
        )
        for name, spec in schema.items()
    ]


def passages(paper: FullText, words: list[str]) -> list[dict[str, str]]:
    """
    The sentences that carry the most of the wanted words, for a paper whose titles carry none

    Args:
        paper: The parsed paper.
        words: The keywords.

    Returns:
        The best sentences with the section each came from.
    """
    wanted = {t for w in words for t in WORDS.findall(w)}
    low, high = PASSAGE_CHARS
    scored: list[tuple[int, str, str]] = []
    for name, body in paper.sections.items():
        for sentence in SPLIT.split(body):
            hits = len(wanted & set(WORDS.findall(sentence.lower())))
            if hits and low <= len(sentence) <= high:
                scored.append((hits, name, sentence.strip()))
    scored.sort(key=lambda s: -s[0])
    return [{"section": name, "text": text} for _, name, text in scored[:PASSAGES]]


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
    schema: list[dict[str, Any]] | dict[str, Any] | None = None,
    question: str = "",
    want: str | list[str] = "",
) -> str:
    """
    A paper's contents, one of its sections, or a schema the caller invented, filled from it

    Args:
        handles: The shared handles.
        arxiv_ids: The papers to read.
        schema: The fields to fill, as a list of entries or a mapping of name to description.
        question: What the papers are being read for, which the extractor is held to.
        want: One or more keywords, which return the sections or sentences that carry them.

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
        found = read_html(handles.html, arxiv_id, title, handles.fetch)
        if found is None or not found.sections:
            missing.append(arxiv_id)
            continue
        papers.append(found)

    if want and not schema:
        words = keywords(want)
        out: list[dict[str, Any]] = []
        for paper in papers:
            titled = [
                (name, body)
                for name, body in paper.sections.items()
                if any(w in name.lower() for w in words)
            ]
            if titled:
                out += [
                    {"arxiv_id": paper.arxiv_id, "section": name, "text": body[:SECTION_CHARS]}
                    for name, body in titled[:SECTIONS_SHOWN]
                ]
            else:
                out.append(
                    {
                        "arxiv_id": paper.arxiv_id,
                        "note": "no section title carries these words, these sentences do",
                        "sentences": passages(paper, words),
                        "sections": list(paper.sections),
                    }
                )
            out += [
                {"arxiv_id": paper.arxiv_id, "table": t.render()[:SECTION_CHARS]}
                for t in paper.result_tables[:2]
                if any(w in ("result", "results", "table") for w in words)
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

    made = as_design(question, as_fields(schema))
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
