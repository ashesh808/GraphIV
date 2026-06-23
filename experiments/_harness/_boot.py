"""The one module that bootstraps sys.path to reach phases/_framework + phase-6 components,
and exposes global-config values (LLM router, sqlite path). Imported first by the harness.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO: Path = Path(__file__).resolve().parents[2]
for _p in (
    str(REPO / "phases"),
    str(REPO / "phases" / "phase-6" / "components"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _framework import gpath, load_global  # noqa: E402

_G: dict[str, Any] = load_global()
LLM_BASE_URL: str = str(_G["llm"]["base_url"])
LLM_ROUTER: str = str(_G["llm"]["router"])
JUDGE_MODEL: str = str(_G["llm"]["map_model"])  # Gemma-4-26B: best judge discrimination
SQLITE_DB: Path = gpath(str(_G["sqlite"]["db"]))
