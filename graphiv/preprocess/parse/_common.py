"""
Config bridge for the citation parser (was the phase-3 parser)
"""

from __future__ import annotations

from pathlib import Path

from graphiv.core.config import Config

_C = Config.load()

BASE_PATH: Path = _C.data_dir
PG_DSN: str = _C.pg_dsn
DB_PATH: Path = _C.sqlite_db
HTML_DIR: Path = _C.html_dir
STATS_DIR: Path = _C.citation_stats

# html_status sentinels mirror download/_common
HTML_OK: int = 1
HTML_WARNING: int = 2
HTML_ERROR: int = 3
