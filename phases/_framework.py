"""Shared run.py contract for every phase: config resolution, dry-run, global-config access.

Config resolution priority (highest first):
  --config=PATH          read that JSON as the base, ignore the local config.json
  --include-X / --set-X  per-key overrides layered onto the base
  ./config.json          phase-local base (used when --config is absent; must exist)
A phase fails fast (SystemExit) if the resolved config is missing a required key.

Flag grammar: --include-NAME sets NAME=true; --set-NAME V (or --set-NAME=V) sets NAME=V,
coercing numbers; hyphens in NAME become underscores to match JSON keys. --dry-run is captured
separately; bare (non --) args are returned as positionals (e.g. phase-6's question).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PHASES_DIR = Path(__file__).resolve().parent
REPO_ROOT = PHASES_DIR.parent
GLOBAL_CONFIG = PHASES_DIR / "global-config.json"


def load_global() -> dict[str, Any]:
    """Load phases/global-config.json (data locations + endpoint APIs)."""
    with open(GLOBAL_CONFIG) as f:
        data: dict[str, Any] = json.load(f)  # pyright: ignore[reportExplicitAny]
    return data


def gpath(value: str) -> Path:
    """Resolve a global-config path string: absolute as-is, else relative to the repo root."""
    p = Path(value)
    return p if p.is_absolute() else REPO_ROOT / p


def _coerce(v: str) -> Any:
    """Parse a --set value as int/float when numeric, else keep it a string."""
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


@dataclass
class Resolved:
    """The effective phase config plus globals, dry-run flag, and positional args."""

    config: dict[str, Any]
    globals: dict[str, Any]
    dry_run: bool
    positionals: list[str]


def resolve(
    phase_dir: Path, argv: list[str], required: tuple[str, ...] = ()
) -> Resolved:
    """Build the effective config from --config / --include / --set / local config.json."""
    dry_run = False
    config_path: Path | None = None
    overrides: dict[str, Any] = {}
    positionals: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            dry_run = True
        elif a.startswith("--config="):
            config_path = Path(a.split("=", 1)[1])
        elif a.startswith("--include-"):
            overrides[a[len("--include-") :].replace("-", "_")] = True
        elif a.startswith("--set-"):
            rest = a[len("--set-") :]
            if "=" in rest:
                k, v = rest.split("=", 1)
                overrides[k.replace("-", "_")] = _coerce(v)
            else:  # value is the next argv token
                i += 1
                overrides[rest.replace("-", "_")] = _coerce(argv[i])
        elif a.startswith("--"):
            raise SystemExit(f"unknown flag: {a}")
        else:
            positionals.append(a)
        i += 1

    base_path = config_path if config_path is not None else phase_dir / "config.json"
    if not base_path.exists():
        raise SystemExit(f"config not found: {base_path}")
    with open(base_path) as f:
        config: dict[str, Any] = json.load(f)  # pyright: ignore[reportExplicitAny]
    config.update(overrides)

    missing = [k for k in required if k not in config]
    if missing:
        raise SystemExit(f"incomplete config {base_path}: missing {missing}")

    return Resolved(
        config=config, globals=load_global(), dry_run=dry_run, positionals=positionals
    )


def print_config(phase: str, r: Resolved) -> None:
    """Print the resolved config before any work runs (called by every run.py)."""
    banner = "DRY-RUN — " if r.dry_run else ""
    print(f"[{phase}] {banner}resolved config:")
    print(json.dumps(r.config, indent=2, sort_keys=True))
    if r.positionals:
        print(f"[{phase}] positionals: {r.positionals}")
