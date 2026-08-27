"""
The flag grammar and config resolution every scripts/ entrypoint shares

Least specific first: the stage table in config.toml, then a --preset file, then --set flags.
Every flag therefore has a config-file equivalent, which is what makes a run reproducible.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from graphiv.core.config import Config


def _coerce(value: str) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
    """
    Parse a --set value as int or float when numeric, else keep it a string

    Args:
        value: raw token from the command line.

    Returns:
        The coerced value.
    """
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


@dataclass
class Resolved:
    """
    The effective stage config, the loaded Config, the dry-run flag and positionals
    """

    config: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    globals: Config
    dry_run: bool
    positionals: list[str]


def load_preset(
    preset_dir: Path, name: str
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """
    Read one named preset, which is a flat table of the same keys `--set` would carry

    Args:
        preset_dir: where preset files live.
        name: the preset's file stem.

    Returns:
        The preset's keys.

    Raises:
        SystemExit: when the preset does not exist, listing the ones that do.
    """
    path = preset_dir / f"{name}.toml"
    if not path.exists():
        have = sorted(p.stem for p in preset_dir.glob("*.toml")) if preset_dir.is_dir() else []
        raise SystemExit(f"no preset {name!r} in {preset_dir}; have {have}")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def resolve(stage: str, argv: list[str], required: tuple[str, ...] = ()) -> Resolved:
    """
    Build the effective stage config from the command line and config.toml

    Args:
        stage: key under [stage.*] in config.toml.
        argv: arguments after the program name.
        required: keys that must be present once overrides are applied.

    Returns:
        The Resolved config.

    Raises:
        SystemExit: on an unknown flag, a missing config file or a missing required key.
    """
    dry_run = False
    config_path: Path | None = None
    preset: str | None = None
    overrides: dict[str, Any] = {}  # pyright: ignore[reportExplicitAny]
    positionals: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            dry_run = True
        elif a.startswith("--config="):
            config_path = Path(a.split("=", 1)[1])
        elif a == "--preset" or a.startswith("--preset="):
            if "=" in a:
                preset = a.split("=", 1)[1]
            else:
                i += 1
                preset = argv[i]
        elif a.startswith("--include-"):
            overrides[a[len("--include-") :].replace("-", "_")] = True
        elif a.startswith("--set-"):
            rest = a[len("--set-") :]
            if "=" in rest:
                k, v = rest.split("=", 1)
                overrides[k.replace("-", "_")] = _coerce(v)
            else:
                i += 1
                overrides[rest.replace("-", "_")] = _coerce(argv[i])
        elif a.startswith("--"):
            raise SystemExit(f"unknown flag: {a}")
        else:
            positionals.append(a)
        i += 1

    if config_path is not None and not config_path.exists():
        raise SystemExit(f"config not found: {config_path}")
    cfg = Config.load(config_path)

    config: dict[str, Any] = dict(cfg.stages.get(stage, {}))  # pyright: ignore[reportExplicitAny]  # fmt: skip
    if not config:
        raise SystemExit(f"config.toml has no [stage.{stage}] table")
    if preset is not None:
        config.update(load_preset(cfg.preset_dir, preset))
    config.update(overrides)
    # the run record carries the label so a finished run says which bundle produced it
    config["preset"] = preset or ""

    missing = [k for k in required if k not in config]
    if missing:
        raise SystemExit(f"incomplete [stage.{stage}]: missing {missing}")

    return Resolved(config=config, globals=cfg, dry_run=dry_run, positionals=positionals)


def print_config(stage: str, r: Resolved) -> None:
    """
    Print the resolved config before any work runs

    Args:
        stage: stage name used in the banner.
        r: the resolved config to print.
    """
    banner = "DRY-RUN - " if r.dry_run else ""
    print(f"[{stage}] {banner}resolved config:")
    print(json.dumps(r.config, indent=2, sort_keys=True))
    if r.positionals:
        print(f"[{stage}] positionals: {r.positionals}")
