"""
What every tool needs, opened once, and the rankings the server keeps between calls

A ranking is thousands of papers, so it stays here and the caller carries the id it was given
The id is a hash of what produced it, so asking the same thing twice costs nothing
"""

from __future__ import annotations

import hashlib
import logging
import os
import tomllib
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.core.embed import embed
from src.core.llm import Gemma
from src.core.parse_graph_export import GraphExport, load_graph_export
from src.core.schema import Grade, Paper

LOG = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2] / "config.toml"
CONFIG = Path(os.environ.get("GRAPHIV_CONFIG") or REPO)
MODES = {"survey": "survey.toml", "frontier": "frontier.toml", "consensus": "consensus.toml"}
ID_CHARS = 12


@dataclass
class Handles:
    """
    The store, the graph, the endpoints and the model, all of which outlive every call
    """

    dsn: str
    endpoints: dict[str, str]
    graph: GraphExport
    model: Gemma
    recipes: Path
    html: Path
    pdfs: Path
    runs: Path
    fetch: bool = False

    def embed(self, text: str) -> list[float]:
        """
        One query vector

        Args:
            text: The question.

        Returns:
            The unit normalized vector.
        """
        return embed(self.endpoints["EMBED_API"], self.endpoints["EMBED_NAME"], text)

    def recipe(self, mode: str) -> Path:
        """
        The recipe file one mode names

        Args:
            mode: survey, frontier or consensus.

        Returns:
            The path, falling back to survey for a mode nothing defines.
        """
        return self.recipes / MODES.get(mode, MODES["survey"])


@dataclass
class Held:
    """
    One ranking the server keeps, and everything a later call would otherwise have to redo
    """

    query_id: str
    question: str
    anchor: str
    mode: str
    asked: date
    vector: list[float] = field(default_factory=list)
    ranked: list[Paper] = field(default_factory=list)
    kept: list[Paper] = field(default_factory=list)
    grades: dict[str, Grade] = field(default_factory=dict)
    era: int = 0
    pool: int = 0
    seconds: float = 0.0

    @property
    def head(self) -> list[str]:
        """
        What an overlap between two areas is measured on

        Returns:
            The top of the ranking whatever the dates.
        """
        return [p.arxiv_id for p in self.ranked[:HEAD]]


HEAD = 300
STORE: dict[str, Held] = {}


@dataclass(frozen=True)
class Serving:
    """
    What the transport itself needs, which is the half of the config that needs no corpus
    """

    host: str
    api_port: int
    frontend_port: int
    allowed_hosts: list[str]
    runs: Path
    html: Path
    pdfs: Path
    fetch: bool


@lru_cache(maxsize=1)
def serving(config_path: str | Path = CONFIG) -> Serving:
    """
    The ports and the paths, read without opening the store or the graph

    Args:
        config_path: Where config.toml lives.

    Returns:
        The settings.
    """
    config: dict[str, Any] = tomllib.loads(Path(config_path).read_text(encoding="utf-8"))
    block = dict(config["serve"])
    return Serving(
        host=str(block["HOST"]),
        api_port=int(block["API_PORT"]),
        frontend_port=int(block["FRONTEND_PORT"]),
        allowed_hosts=[str(one) for one in block.get("ALLOWED_HOSTS", [])],
        runs=Path(str(block["RUNS_PATH"])),
        html=Path(str(config["dataset"]["HTML_PATH"])),
        pdfs=Path(str(config["dataset"]["PDF_PATH"])),
        fetch=bool(block.get("FETCH", False)),
    )


@lru_cache(maxsize=1)
def load(config_path: str | Path = CONFIG) -> Handles:
    """
    Everything a tool needs, built once per process

    Args:
        config_path: Where config.toml lives.

    Returns:
        The handles.
    """
    config: dict[str, Any] = tomllib.loads(Path(config_path).read_text(encoding="utf-8"))
    endpoints = {k: str(v) for k, v in config["endpoints"].items()}
    block = dict(config["serve"])
    settings = serving(config_path)
    graph = load_graph_export(str(config["dataset"]["GRAPH_PATH"]))
    handles = Handles(
        dsn=str(config["database"]["PG_DEST"]),
        endpoints=endpoints,
        graph=graph,
        model=Gemma(endpoints["LLM_API"], endpoints["LLM_NAME"], str(block["CACHE_PATH"])),
        recipes=Path(str(block["RECIPE_PATH"])),
        html=settings.html,
        pdfs=settings.pdfs,
        runs=settings.runs,
        fetch=settings.fetch,
    )
    LOG.info("loaded %d papers", graph.n_papers)
    return handles


def make_id(*parts: str) -> str:
    """
    The id one ranking is kept under, which is a hash of everything that produced it

    Args:
        parts: What the ranking was built from.

    Returns:
        The id.
    """
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:ID_CHARS]


def keep(held: Held) -> Held:
    """
    Puts one ranking where a later call can find it

    Args:
        held: The ranking.

    Returns:
        The ranking, for chaining.
    """
    STORE[held.query_id] = held
    return held


def get(query_id: str) -> Held | None:
    """
    One ranking by its id

    Args:
        query_id: What a retrieve call returned.

    Returns:
        The ranking, or None when this process never made it.
    """
    return STORE.get(query_id)


def overlap(head: list[str], seen: list[str]) -> tuple[float, dict[str, float]]:
    """
    How much of a ranking's head earlier rankings already held

    A genuinely new area shares almost none of its head with one already searched, and an area
    renamed rather than changed shares most of it.

    Args:
        head: The head of the new ranking.
        seen: Ids of rankings made earlier.

    Returns:
        The share of the head nothing earlier held, and the share held per earlier id.
    """
    if not head:
        return 0.0, {}
    per: dict[str, float] = {}
    every: set[str] = set()
    for query_id in seen:
        earlier = STORE.get(query_id)
        if earlier is None:
            continue
        shared = set(head) & set(earlier.head)
        per[query_id] = len(shared) / len(head)
        every |= shared
    return 1.0 - len(every) / len(head), per


def reset() -> None:
    """
    Forgets every ranking, which is what ends one session
    """
    STORE.clear()
