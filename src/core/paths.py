"""Locate shared assets in a checkout or an installed distribution."""

from pathlib import Path

_BUNDLED = Path(__file__).resolve().parents[1] / "_resources"
PROJECT_ROOT = _BUNDLED if _BUNDLED.is_dir() else Path(__file__).resolve().parents[2]
RUNTIME_CONFIG = PROJECT_ROOT / "configs" / "runtime.toml"
OFFLINE_CONFIG = PROJECT_ROOT / "configs" / "offline.toml"
