"""
Where an experiment keeps its cache and its results, resolved from the calling module

Every experiment module used to open with the same four lines
Two of them counted parents wrong, so a repo root pointed at experiments/ instead
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def experiment(module_file: str) -> tuple[Path, Path, Path]:
    """
    The cache directory, the results directory and the repo root

    Args:
        module_file: Always `__file__` from a module under an experiment's `code/`.

    Returns:
        (cache, results, repo root).
    """
    exp = Path(module_file).resolve().parents[1]
    return exp / "cache", exp / "results", exp.parents[2]


def read_json(path: Path) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
    """
    Parse one cache file

    Args:
        path: The file to read.

    Returns:
        Whatever the file holds.
    """
    return json.loads(path.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
