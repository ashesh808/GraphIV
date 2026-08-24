"""
Config bridge for the serve path: retrieval, generation and the dashboard

Values come from config.toml, read once when this module is first imported.
The constant names are the ones the endpoint modules already import.
"""

from __future__ import annotations

from pathlib import Path

from graphiv.core.config import Config

_C = Config.load()

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = _C.data_dir
SQLITE_DB: Path = _C.sqlite_db

OLD_SQLITE: Path = Path(_C.old_sqlite)
NOMIC_NPY: Path = Path(_C.nomic_npy)
EMBED_API: str = _C.embed_api
EMBED_MODEL_NAME: str = _C.embed_model
EMB_DIM: int = _C.embed_dim
EMB_ROWS: int = _C.embed_rows
NOMIC_PROMPT: str = _C.embed_sym_prompt
NOMIC_MAX_SEQ: int = _C.embed_max_seq
ASYM_QUERY_PROMPT: str = _C.embed_query_prompt

TOPIC_TREE_DB: Path = _C.topic_tree_db
FULLTEXT_CACHE_DB: Path = _C.fulltext_cache_db
HTML_DIR: Path = _C.html_dir
PDF_DIR: Path = _C.pdf_dir
OUTPUT_DIR: Path = _C.output_dir

PG_DSN: str = _C.pg_dsn

LLM_BASE_URL: str = _C.llm_base_url
LLM_ROUTER: str = _C.llm_router
MAP_MODEL: str = _C.map_model
NARRATOR_MODEL: str = _C.narrator_model
VISION_MODEL: str = _C.vision_model


def arxiv_year(arxiv_id: str) -> int | None:
    """
    Publication year of an arXiv id, or None when the id does not parse

    Handles modern (YYMM.NNNNN) and legacy (archive/YYMMNNN) forms.

    Args:
        arxiv_id: the paper's arXiv identifier.

    Returns:
        Four-digit year, or None.
    """
    tail = arxiv_id.split("/")[-1]
    digits = "".join(ch for ch in tail if ch.isdigit())
    if len(digits) < 4:
        return None
    yy = int(digits[:2])
    return 1900 + yy if yy >= 91 else 2000 + yy
