"""Shared constants and helpers for phase_3.parse.

Mirrors the structure of phase_2._common: paths are derived once and reused
by both the matcher and the visualization scripts.
"""

from __future__ import annotations

from pathlib import Path

import sys as _sys

_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[3]))
from _framework import REPO_ROOT as _REPO_ROOT  # noqa: E402

BASE_PATH: Path = _REPO_ROOT / "data"
DB_PATH: Path = BASE_PATH / "metadata" / "arxiv.db"
HTML_DIR: Path = BASE_PATH / "html"
STATS_DIR: Path = BASE_PATH / "citation_stats"

# html_status sentinels mirror phase_2._common
HTML_OK: int = 1
HTML_WARNING: int = 2
HTML_ERROR: int = 3
