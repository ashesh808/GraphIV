"""Phase-6 constants + helpers, sourced from phases/global-config.json.

Preserves the legacy `kg_rag/_common.py` names so the ported endpoint modules import unchanged;
values now come from the shared global config instead of being hardcoded. This is the only
component allowed a sys.path bootstrap — it is the bridge to the framework config loader.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # phases/ -> _framework
from _framework import gpath, load_global, pg_dsn  # noqa: E402

_G: dict[str, Any] = load_global()
_PATHS: dict[str, str] = _G["paths"]
_EMB: dict[str, Any] = _G["embeddings"]
_LLM: dict[str, str] = _G["llm"]

# --- repo / sqlite --------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
SQLITE_DB = gpath(_G["sqlite"]["db"])

# --- embedding source (old the-great-arxiv-db; nomic set is the indexed one) ----
OLD_SQLITE = gpath(_EMB["old_sqlite"])
NOMIC_NPY = gpath(_EMB["nomic_npy"])
NOMIC_MODEL = gpath(_EMB["nomic_model"])
EMB_DIM: int = _EMB["dim"]
EMB_ROWS: int = _EMB["rows"]
NOMIC_PROMPT: str = _EMB["prompt"]
NOMIC_MAX_SEQ: int = _EMB["max_seq"]

# --- topic graph + full-text + figures ------------------------------------
TOPIC_TREE_DB = gpath(_PATHS["topic_tree_db"])
FULLTEXT_CACHE_DB = gpath(_PATHS["fulltext_cache_db"])
HTML_DIR = gpath(_PATHS["html_dir"])
PDF_DIR = gpath(_PATHS["pdf_dir"])
MAP_MODEL: str = _LLM["map_model"]

# --- postgres (single project store; flake socket, env-overridable) -------
PG_DSN: str = pg_dsn()

# --- LLM endpoint (any OpenAI-compatible server; served via llama-router) --
LLM_BASE_URL: str = _LLM["base_url"]
LLM_ROUTER: str = _LLM["router"]
NARRATOR_MODEL: str = _LLM["narrator_model"]


def arxiv_year(arxiv_id: str) -> int | None:
    """Year from a modern (YYMM.NNNNN) or legacy (arch/YYMMNNN) id; None if unparseable."""
    tail = arxiv_id.split("/")[-1]
    digits = "".join(ch for ch in tail if ch.isdigit())
    if len(digits) < 4:
        return None
    yy = int(digits[:2])
    return 1900 + yy if yy >= 91 else 2000 + yy
