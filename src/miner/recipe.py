"""
The `[miner]` block of a recipe file, which is where every constant this package uses lives

The block sits in the same file as the scorer's exponents, so one mode picks a matched pair
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.miner.leyline import Settings

ARGUES = ("extends", "critiques", "compares")
WEIGHTS = {
    "extends": 1.0,
    "critiques": 1.0,
    "compares": 0.8,
    "uses": 0.4,
    "motivates": 0.15,
    "background": 0.0,
}


@dataclass(frozen=True)
class Recipe:
    """
    What one mode does above the ranking, from the gate down to how far back a successor may sit
    """

    settings: Settings = field(default_factory=Settings)
    gate: float = 4.0
    hop: int = 1
    walk_prefix: int = 30
    connectors: int = 40
    successor_days: int = 240
    successor_floor: float = 0.60
    successor_intents: tuple[str, ...] = ARGUES
    graph_weight: float = 0.65
    relevance_weight: float = 0.35


def build_recipe(parsed: dict[str, Any]) -> Recipe:
    """
    The miner half of a parsed recipe, with every value the file leaves out taking its default

    Args:
        parsed: A recipe file already read into a dict.

    Returns:
        The recipe.
    """
    block: dict[str, Any] = dict(parsed.get("miner", {}))
    weights = {str(k): float(v) for k, v in dict(block.get("weights", WEIGHTS)).items()}
    argues = tuple(str(x) for x in block.get("ARGUES", ARGUES))
    return Recipe(
        settings=Settings(
            weights=weights,
            argues=argues,
            focus=float(block.get("FOCUS", 4.0)),
            decay=float(block.get("DECAY", 0.5)),
            knockdown=float(block.get("KNOCKDOWN", 0.4)),
            seeds=int(block.get("SEEDS", 10)),
            walks=int(block.get("WALKS", 50)),
            branch=int(block.get("BRANCH", 1)),
        ),
        gate=float(block.get("GATE", 4.0)),
        hop=int(block.get("HOP", 1)),
        walk_prefix=int(block.get("WALK_PREFIX", 30)),
        connectors=int(block.get("CONNECTORS", 40)),
        successor_days=int(block.get("SUCCESSOR_DAYS", 240)),
        successor_floor=float(block.get("SUCCESSOR_FLOOR", 0.60)),
        successor_intents=tuple(str(x) for x in block.get("SUCCESSOR_INTENTS", argues)),
        graph_weight=float(block.get("GRAPH_WEIGHT", 0.65)),
        relevance_weight=float(block.get("RELEVANCE_WEIGHT", 0.35)),
    )


def read_recipe(path: str | Path) -> Recipe:
    """
    One recipe file read for its miner block alone

    Args:
        path: The toml.

    Returns:
        The recipe.
    """
    return build_recipe(tomllib.loads(Path(path).read_text(encoding="utf-8")))
