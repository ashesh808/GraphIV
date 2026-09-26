"""
The reports this server already wrote, ranked against a new question by meaning

A question the corpus was already asked has its answer on disk, and reading that costs nothing
Every past question is embedded once per process, since a run's question never changes
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from src.mcp.dashboard import read_one, read_runs
from src.mcp.state import Handles

LOG = logging.getLogger(__name__)

MAX_LIMIT = 50
MAX_RANKED = 200
SUMMARY_PAPERS = 40
VECTORS: dict[str, list[float]] = {}


def cosine(left: list[float], right: list[float]) -> float:
    """
    The closeness of two vectors, zero when either has no length

    Args:
        left: One vector.
        right: The other.

    Returns:
        The cosine.
    """
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    size = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / size if size else 0.0


def rank(
    vector: list[float], runs: list[dict[str, Any]], vectors: dict[str, list[float]]
) -> list[dict[str, Any]]:
    """
    The past runs closest to one question, closest first

    Args:
        vector: The new question's vector.
        runs: The runs to rank, each carrying a slug.
        vectors: One vector per slug, where a slug with none sorts last.

    Returns:
        The runs, each with the closeness it scored.
    """
    scored = [
        dict(run) | {"closeness": round(cosine(vector, vectors.get(str(run["slug"]), [])), 4)}
        for run in runs
    ]
    return sorted(scored, key=lambda r: -float(r["closeness"]))


def one_run(handles: Handles, slug: str) -> str:
    """
    One past run, as its document and the papers behind it

    Args:
        handles: The shared handles.
        slug: The run's directory name.

    Returns:
        The document and the papers as json, or an error when no run carries that name.
    """
    found = read_one(handles.runs, slug)
    if found is None:
        return json.dumps({"error": f"no run named {slug}"})
    papers = found.get("papers")
    kept = papers[:SUMMARY_PAPERS] if isinstance(papers, list) else []
    return json.dumps(
        {
            "slug": slug,
            "question": found.get("question", ""),
            "asked": found.get("asked", ""),
            "report": found.get("report", ""),
            "papers": kept,
        },
        indent=2,
    )


def find_runs(handles: Handles, question: str = "", slug: str = "", limit: int = 10) -> str:
    """
    The reports already on disk, ranked against a question or read back by name

    Args:
        handles: The shared handles.
        question: What is being asked now, which the past questions are ranked against.
        slug: One run to read back instead of searching.
        limit: How many runs to return.

    Returns:
        One json row per run, or the named run itself.
    """
    if slug:
        return one_run(handles, slug)
    runs = read_runs(handles.runs)
    if not runs:
        return json.dumps([])
    kept = max(1, min(MAX_LIMIT, limit))
    if question:
        for run in runs[:MAX_RANKED]:
            name = str(run["slug"])
            if name not in VECTORS and str(run.get("question", "")):
                VECTORS[name] = handles.embed(str(run["question"]))
        runs = rank(handles.embed(question), runs[:MAX_RANKED], VECTORS)
    LOG.info("found %d runs under %s", len(runs), handles.runs)
    return json.dumps([summary(handles.runs, run) for run in runs[:kept]], indent=2)


def summary(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    """
    One run as the library shows it, plus where to read the rest of it

    Args:
        root: The directory runs are written to.
        run: The row the listing built.

    Returns:
        The row, with the file it was read from named.
    """
    slug = str(run["slug"])
    return dict(run) | {"report": str(root / slug / "report.md"), "dashboard": f"#/run/{slug}"}
