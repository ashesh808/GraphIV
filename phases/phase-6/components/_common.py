"""Phase-6 constants + helpers, sourced from phases/global-config.json.

Preserves the legacy `kg_rag/_common.py` names so the ported endpoint modules import unchanged;
values now come from the shared global config instead of being hardcoded. This is the only
component allowed a sys.path bootstrap — it is the bridge to the framework config loader.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

from neo4j import Driver, GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # phases/ -> _framework
from _framework import gpath, load_global  # noqa: E402

_G: dict[str, Any] = load_global()
_PATHS: dict[str, str] = _G["paths"]
_EMB: dict[str, Any] = _G["embeddings"]
_NEO: dict[str, str] = _G["neo4j"]
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

# --- postgres -------------------------------------------------------------
PG_DSN: str = _G["postgres"]["dsn"]

# --- neo4j ----------------------------------------------------------------
NEO4J_URI: str = _NEO["uri"]
NEO4J_USER: str = _NEO["user"]
NEO4J_PASSWORD: str = _NEO["password"]
NEO4J_HOME = Path(_NEO["home"])
NEO4J_DB: str = _NEO["db"]
VECTOR_INDEX: str = _NEO["vector_index"]

# --- neo4j-admin import staging (phase-4 build artifacts) -----------------
OUT_DIR = DATA_DIR / "neo4j_import"
NODES_CSV = OUT_DIR / "nodes.csv"
NODES_HEADER = OUT_DIR / "nodes_header.csv"
EDGES_CSV = OUT_DIR / "edges.csv"
EDGES_HEADER = OUT_DIR / "edges_header.csv"
EMB_IDS_NPY = OUT_DIR / "emb_ids.npy"

# --- LLM router (llama.cpp, OpenAI-compatible) ----------------------------
LLM_BASE_URL: str = _LLM["base_url"]
LLM_ROUTER: str = _LLM["router"]
NARRATOR_MODEL: str = _LLM["narrator_model"]

# --- visualization (Haruhana palette + per-intent edge colors) ------------
HARUHANA_PATH = gpath(_G["viz"]["haruhana"])
HARUHANA_SURFACE = "#0C0F1E"
HARUHANA_ON_SURFACE = "#D4D0EA"
HARUHANA_SURFACE_VARIANT = "#171D36"
HARUHANA_OUTLINE = "#232E4C"
INTENT_COLORS: dict[str, str] = {
    "uses": "#6FC898",
    "extends": "#82AAFF",
    "compares": "#F8D06A",
    "critiques": "#FF5370",
    "motivates": "#B4A2E8",
    "background": "#8B95A8",
}


@contextlib.contextmanager
def neo4j_driver() -> Generator[Driver]:
    """Yield a Neo4j driver, closed on exit."""
    drv = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        yield drv
    finally:
        drv.close()


def arxiv_year(arxiv_id: str) -> int | None:
    """Year from a modern (YYMM.NNNNN) or legacy (arch/YYMMNNN) id; None if unparseable."""
    tail = arxiv_id.split("/")[-1]
    digits = "".join(ch for ch in tail if ch.isdigit())
    if len(digits) < 4:
        return None
    yy = int(digits[:2])
    return 1900 + yy if yy >= 91 else 2000 + yy
