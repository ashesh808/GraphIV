"""
Endpoint settings the harness shares, read once from config.toml

It used to bootstrap sys.path; the package is installed now, so it only re-exports.
"""

from __future__ import annotations

from pathlib import Path

from graphiv.core.config import Config

_C = Config.load()

REPO: Path = Path(__file__).resolve().parents[2]
LLM_BASE_URL: str = _C.llm_base_url
LLM_ROUTER: str = _C.llm_router
# the map model gives the best judge discrimination
JUDGE_MODEL: str = _C.map_model
SQLITE_DB: Path = _C.sqlite_db
