"""
Reads config.toml with every relative path resolved against the file's own directory

A relative path then means the same thing from any working directory, so a checkout can move
The DSN is anchored too, as libpq takes only a host starting with a slash as a socket directory
"""

import re
import tomllib
from pathlib import Path
from typing import Any

SOCKET_HOST = re.compile(r"(?<![^\s])host=(\.\S*)")


def load_config(path: str | Path) -> dict[str, Any]:
    """
    Parses a config file and anchors each relative `*_PATH` value to the directory holding it

    An empty value stays empty, since it means the setting is off
    A `*_DEST` DSN whose `host=` starts with a dot names a socket directory, anchored the same way

    Args:
        path: Where config.toml lives.

    Returns:
        The parsed blocks, with every path value absolute.
    """
    path = Path(path).resolve()
    config: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    _anchor(config, path.parent)
    return config


def _anchor(block: dict[str, Any], root: Path) -> None:
    """
    Rewrites the relative path values of one block and of every block nested in it, in place

    Args:
        block: One table of the parsed file.
        root: The directory the file sits in.
    """
    for key, value in block.items():
        if isinstance(value, dict):
            _anchor(value, root)
        elif not isinstance(value, str) or not value:
            continue
        elif key.endswith("_PATH"):
            block[key] = str(root / value)
        elif key.endswith("_DEST"):
            block[key] = SOCKET_HOST.sub(lambda m: f"host={root / m.group(1)}", value)
