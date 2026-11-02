"""
Builds a pipeline out of a recipe file, so a setting is edited rather than coded

A recipe lists its components in the order they run, and deleting a block deletes that step
Every exponent and every constant a component takes lives in its own block
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

from src.core.parse_graph_export import GraphExport
from src.core.schema import Reranker, Retriever
from src.retrieve.cosine import CosineRetriever
from src.retrieve.expand import AncestorExpander, FrontierExpander
from src.retrieve.query import PaperQuery
from src.retrieve.scorer import GraphScorer, Weights
from src.storage.corpus import CorpusSource

LOG = logging.getLogger(__name__)


def read_recipe(path: str | Path) -> dict[str, Any]:
    """
    Reads one recipe file

    Args:
        path: The toml naming the components and their values.

    Returns:
        The parsed recipe, which is also what a run writes back out.
    """
    parsed = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    if not parsed.get("component"):
        raise ValueError(f"{path} names no component")
    return parsed


def build_weights(block: dict[str, Any]) -> Weights:
    """
    One set of exponents out of a scorer block

    Args:
        block: The `weights` table of a GraphScorer component.

    Returns:
        The exponents, with anything the file leaves out taking its default.
    """
    return Weights(**{k.lower(): float(v) for k, v in block.items()})


def build_pipeline(
    recipe: dict[str, Any],
    graph: GraphExport,
    pg_dest: CorpusSource,
    blocked: list[str] | None = None,
) -> PaperQuery:
    """
    Assembles the components a recipe names, in the order it names them

    The first component is the retriever, the expanders follow and the scorer ends it, which is
    what makes a recipe with one component a cosine-only run.

    Args:
        recipe: A parsed recipe.
        graph: The citation graph export.
        pg_dest: A libpq connection string or corpus adapter.
        blocked: Papers the query must never return.

    Returns:
        The pipeline, ready to be called.
    """
    components: list[dict[str, Any]] = list(recipe["component"])
    head, tail = components[0], components[1:]
    if head["KIND"] != "CosineRetriever":
        raise ValueError(f"a recipe starts with a retriever, not {head['KIND']}")

    retriever: Retriever = CosineRetriever(pg_dest, blocked=blocked)
    expanders: list[Reranker] = []
    limits: list[int | None] = []
    scorers: list[Reranker] = []
    for block in tail:
        kind = str(block["KIND"])
        if kind in ("AncestorExpander", "FrontierExpander"):
            maker = AncestorExpander if kind == "AncestorExpander" else FrontierExpander
            expanders.append(
                maker(
                    graph,
                    pg_dest,
                    top_k=int(block.get("TOP_K", 200)),
                    hop_limit=int(block.get("HOP_LIMIT", 20000)),
                )
            )
            limits.append(int(block.get("HOP_LIMIT", 20000)))
        elif kind == "GraphScorer":
            scorers.append(
                GraphScorer(
                    graph,
                    build_weights(block.get("weights", {})),
                    core=int(block.get("CORE", 200)),
                    depth=int(block.get("DEPTH", 4)),
                    decay=float(block.get("DECAY", 0.5)),
                )
            )
        else:
            raise ValueError(f"unknown component {kind}")

    LOG.info(
        "recipe %s: %s, seed %d",
        recipe.get("NAME", "unnamed"),
        " -> ".join(str(c["KIND"]) for c in components),
        int(head.get("LIMIT", 5000)),
    )
    return PaperQuery(retriever, expanders, limits, scorers)


def get_seed_limit(recipe: dict[str, Any]) -> int:
    """
    How many papers the retriever of a recipe returns

    Args:
        recipe: A parsed recipe.

    Returns:
        The retriever's limit.
    """
    return int(recipe["component"][0].get("LIMIT", 5000))
