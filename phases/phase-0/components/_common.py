"""Shared paths for phase-0 (seed metadata); sourced from phases/global-config.json."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # phases/ -> _framework
from _framework import gpath, load_global  # noqa: E402

_G = load_global()
ARXIV_JSON = gpath(_G["paths"]["arxiv_json"])
SEED_STATE = ARXIV_JSON.parent / "metadata" / "seed_state.json"
