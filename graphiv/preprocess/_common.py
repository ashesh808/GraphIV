"""
Config bridge for the phase-5-era build modules (topics, community_summary)
"""

from __future__ import annotations

from pathlib import Path

from graphiv.core.config import Config

_C = Config.load()

# build inputs (old the-great-arxiv-db; UMAP-50 is what the tree clusters on)
EMB_UMAP50_NPY: Path = Path(_C.nomic_umap50_npy)
OLD_SQLITE: Path = Path(_C.old_sqlite)

# build outputs
TOPIC_TREE_DB: Path = _C.topic_tree_db
COMMUNITY_SUMMARY_DB: Path = _C.community_summary_db

# LLM endpoint (community-summary stage)
LLM_BASE_URL: str = _C.llm_base_url
LLM_ROUTER: str = _C.llm_router
MAP_MODEL: str = _C.map_model

# Tag stamped into every community_summaries row's `model` column
SUMMARY_MODEL_TAG: str = f"{MAP_MODEL}-community-v1"
