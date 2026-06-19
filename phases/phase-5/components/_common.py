"""Phase-5 constants, sourced from phases/global-config.json.

Semantic-index build inputs (UMAP-50 nomic vectors + the old great-arxiv-db id list) and
outputs (topic tree, community summaries), plus the LLM endpoint used by the summary stage.
This is the only phase-5 module allowed a sys.path bootstrap to reach the framework loader.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # phases/ -> _framework
from _framework import gpath, load_global  # noqa: E402

_G: dict[str, Any] = load_global()
_PATHS: dict[str, str] = _G["paths"]
_EMB: dict[str, Any] = _G["embeddings"]
_LLM: dict[str, str] = _G["llm"]

# --- build inputs (old the-great-arxiv-db; UMAP-50 is what the tree clusters on) ----
EMB_UMAP50_NPY = gpath(_EMB["nomic_umap50_npy"])
OLD_SQLITE = gpath(_EMB["old_sqlite"])

# --- build outputs --------------------------------------------------------
TOPIC_TREE_DB = gpath(_PATHS["topic_tree_db"])
COMMUNITY_SUMMARY_DB = gpath(_PATHS["community_summary_db"])

# --- LLM endpoint (community-summary stage) -------------------------------
LLM_BASE_URL: str = _LLM["base_url"]
LLM_ROUTER: str = _LLM["router"]
MAP_MODEL: str = _LLM["map_model"]

# Tag stamped into every community_summaries row's `model` column.
SUMMARY_MODEL_TAG: str = f"{MAP_MODEL}-community-v1"
