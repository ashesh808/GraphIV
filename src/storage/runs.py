"""Read persisted research runs without depending on an application transport."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FILES = ("report.md", "run.json", "papers.json", "graph.json", "report.json")


def read_runs(root: Path) -> list[dict[str, Any]]:
    """
    Every run on disk, newest first

    Args:
        root: The directory runs are written to.

    Returns:
        One row per run, carrying nothing the library does not show.
    """
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for found in sorted(root.iterdir(), reverse=True):
        meta = found / "run.json"
        if not meta.is_file():
            continue
        try:
            parsed: dict[str, Any] = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        papers = parsed.get("papers")
        out.append(
            {
                "slug": found.name,
                "question": str(parsed.get("question", found.name)),
                "asked": str(parsed.get("asked", "")),
                "mode": str(parsed.get("mode", "")),
                "effort": str(parsed.get("effort", "")),
                "papers": len(papers) if isinstance(papers, list) else 0,
            }
        )
    return out


def known(root: Path, slug: str) -> bool:
    """
    Whether one name is a run on disk, checked rather than joined so no path escapes the root

    Args:
        root: The directory runs are written to.
        slug: The name to check.

    Returns:
        True when a directory of that name is there.
    """
    return root.is_dir() and slug in {d.name for d in root.iterdir() if d.is_dir()}


def read_one(root: Path, slug: str) -> dict[str, Any] | None:
    """
    One run, with the document itself

    Args:
        root: The directory runs are written to.
        slug: The run's directory name.

    Returns:
        The run, or None when nothing carries that name.
    """
    if not known(root, slug):
        return None
    where = root / slug
    try:
        parsed: dict[str, Any] = json.loads((where / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    parsed["slug"] = slug
    for name in FILES:
        found = where / name
        if not found.is_file() or name == "run.json":
            continue
        raw = found.read_text(encoding="utf-8")
        key = "sections" if name == "report.json" else name.split(".")[0]
        parsed[key] = json.loads(raw) if name.endswith(".json") else raw
    return parsed
