"""
What every tool needs, opened once, and the rankings the server keeps between calls

A ranking is thousands of papers, so it stays here and the caller carries the id it was given
The id is a hash of what produced it, so asking the same thing twice costs nothing
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.core.embed import embed
from src.core.llm import Gemma
from src.core.parse_graph_export import GraphExport, load_graph_export
from src.core.paths import RUNTIME_CONFIG
from src.core.runtime import runtime_config
from src.core.schema import Grade, Paper
from src.storage.artifacts import Snapshot, load_snapshot
from src.storage.blobs import BlobNotFoundError, blob_service_from_environment
from src.storage.corpus import CorpusSource
from src.storage.runs import BlobReportStore, LocalReportStore, ReportStore

LOG = logging.getLogger(__name__)

REPO = RUNTIME_CONFIG
CONFIG = Path(os.environ.get("GRAPHIV_CONFIG") or REPO)
MODES = {
    "survey": "survey.toml",
    "frontier": "frontier.toml",
    "consensus": "consensus.toml",
    "ancestry": "ancestry.toml",
    "evolution": "evolution.toml",
}
ID_CHARS = 12


@dataclass
class Handles:
    """
    The store, the graph, the endpoints and the model, all of which outlive every call
    """

    dsn: CorpusSource
    endpoints: dict[str, str]
    graph: GraphExport
    model: Gemma
    recipes: Path
    html: Path
    pdfs: Path
    runs: Path
    fetch: bool = False
    report_store: ReportStore | None = None

    def embed(self, text: str) -> list[float]:
        """
        One query vector

        Args:
            text: The question.

        Returns:
            The unit normalized vector.
        """
        options = {}
        if self.endpoints.get("EMBED_API_KEY"):
            options["api_key"] = self.endpoints["EMBED_API_KEY"]
        return embed(self.endpoints["EMBED_API"], self.endpoints["EMBED_NAME"], text, **options)

    def recipe(self, mode: str) -> Path:
        """
        The recipe file one mode names

        Args:
            mode: survey, frontier, consensus, ancestry or evolution.

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
    seed: str = ""
    vector: list[float] = field(default_factory=list)
    ranked: list[Paper] = field(default_factory=list)
    kept: list[Paper] = field(default_factory=list)
    grades: dict[str, Grade] = field(default_factory=dict)
    era: int = 0
    pool: int = 0
    seconds: float = 0.0
    # a person's own papers, mined without the citation hop so the walk stays on their work
    pinned: bool = False

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


@dataclass
class Area:
    """
    One area a list of papers was split into, kept so a later call names it by id
    """

    area_id: str
    area: str
    why: str
    arxiv_ids: list[str] = field(default_factory=list)
    pinned: bool = False


AREAS: dict[str, Area] = {}


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
    config: dict[str, Any] = runtime_config(config_path)
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
    config: dict[str, Any] = runtime_config(config_path)
    endpoints = {k: str(v) for k, v in config["endpoints"].items()}
    block = dict(config["serve"])
    settings = serving(config_path)
    backend = config["storage"]["BACKEND"]
    dsn: CorpusSource = str(config["database"]["PG_DEST"])
    graph_path = config["dataset"]["GRAPH_PATH"]
    if backend in {"sqlite", "azure"}:
        from src.storage.sqlite import SQLiteCorpus

        snapshot = _snapshot(config_path) if backend == "azure" else None
        database = snapshot.database if snapshot else Path(config["storage"]["METADATA_PATH"])
        index = snapshot.index if snapshot else config["storage"].get("INDEX_PATH")
        dsn = SQLiteCorpus(
            database, Path(index) if index else None,
            embedding_dimension=snapshot.embedding_dimension if snapshot else None,
        )
        if snapshot:
            graph_path = snapshot.graph
            if snapshot.embedding_model and endpoints["EMBED_NAME"] != snapshot.embedding_model:
                raise ValueError("Embedding model must match the published corpus snapshot")
    graph = load_graph_export(str(graph_path))
    options: dict[str, Any] = {}
    if os.environ.get("GRAPHIV_RUNTIME") == "azure" or backend == "azure":
        options.update(reasoning_effort=None, raise_on_error=True)
    if endpoints.get("LLM_API_KEY"):
        options["api_key"] = endpoints["LLM_API_KEY"]
    handles = Handles(
        dsn=dsn,
        endpoints=endpoints,
        graph=graph,
        model=Gemma(
            endpoints["LLM_API"], endpoints["LLM_NAME"], str(block["CACHE_PATH"]), **options
        ),
        recipes=Path(str(block["RECIPE_PATH"])),
        html=settings.html,
        pdfs=settings.pdfs,
        runs=settings.runs,
        fetch=settings.fetch,
        report_store=report_store(config_path),
    )
    LOG.info("loaded %d papers", graph.n_papers)
    return handles


@lru_cache(maxsize=1)
def _blob_service() -> Any:
    return blob_service_from_environment()


@lru_cache(maxsize=1)
def report_store(config_path: str | Path = CONFIG) -> ReportStore:
    """Construct report persistence without downloading a corpus or making a request."""
    config = runtime_config(config_path)
    if config["storage"]["REPORT_BACKEND"] == "azure":
        return BlobReportStore(
            _blob_service(), os.environ.get("GRAPHIV_REPORTS_CONTAINER", "reports"),
            Path(config["serve"]["RUNS_PATH"]),
        )
    return LocalReportStore(Path(config["serve"]["RUNS_PATH"]))


@lru_cache(maxsize=1)
def _snapshot(config_path: str | Path = CONFIG) -> Snapshot:
    config = runtime_config(config_path)
    return load_snapshot(
        _blob_service(), os.environ.get("GRAPHIV_METADATA_CONTAINER", "metadata"),
        os.environ.get("GRAPHIV_MANIFEST_BLOB", "manifest.json"),
        Path(config["storage"]["CACHE_PATH"]),
    )


_PREPARE_LOCK = threading.Lock()
_PREPARATION: dict[str, Any] = {"complete": False, "reason": "Corpus preparation is pending"}


def prepare_runtime() -> None:
    """Download and validate deployment artifacts in the background, without model requests."""
    with _PREPARE_LOCK:
        try:
            config = runtime_config(CONFIG)
            _ = report_store()
            if config["storage"]["BACKEND"] == "azure":
                _ = _snapshot()
            missing = _configuration_reasons(config)
            if missing:
                _PREPARATION.update(complete=False, reason="; ".join(missing))
                return
            handles = load()
            if isinstance(handles.dsn, str):
                import psycopg

                with psycopg.connect(handles.dsn, connect_timeout=10) as connection:
                    _ = connection.execute("SELECT 1").fetchone()
            _PREPARATION.update(complete=True, reason="")
        except BlobNotFoundError:
            _PREPARATION.update(
                complete=False,
                reason="Corpus manifest or a referenced artifact has not been published",
            )
        except Exception as error:  # noqa: BLE001 -- background health must survive bad configuration
            # Exceptions can contain provider URLs, tokens or DSNs; expose only their type.
            LOG.warning("Runtime preparation failed (%s)", type(error).__name__)
            _PREPARATION.update(
                complete=False, reason=f"Corpus preparation failed ({type(error).__name__})"
            )


def _configuration_reasons(config: dict[str, Any]) -> list[str]:
    reasons = []
    if config["storage"]["BACKEND"] == "postgres" and not config["database"].get("PG_DEST"):
        reasons.append("PostgreSQL DSN is not configured")
    for prefix, label in (("LLM", "LLM"), ("EMBED", "Embedding")):
        if not config["endpoints"].get(f"{prefix}_API"):
            reasons.append(f"{label} endpoint is not configured")
        if not config["endpoints"].get(f"{prefix}_NAME"):
            reasons.append(f"{label} model is not configured")
    return reasons


def runtime_status() -> dict[str, Any]:
    """Cheap readiness; no credential material, downloads or remote model requests."""
    config = runtime_config(CONFIG)
    reasons = _configuration_reasons(config)
    if not _PREPARATION["complete"] and _PREPARATION["reason"]:
        reason = str(_PREPARATION["reason"])
        if reason not in reasons:
            reasons.append(reason)
    return {"ready": not reasons, "storage": config["storage"]["BACKEND"], "reasons": reasons}


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


def keep_area(area: Area) -> Area:
    """
    Puts one area where a later call can find it

    Args:
        area: The area.

    Returns:
        The area, for chaining.
    """
    AREAS[area.area_id] = area
    return area


def get_area(area_id: str) -> Area | None:
    """
    One area by its id

    Args:
        area_id: What an identify_areas call returned.

    Returns:
        The area, or None when this process never made it.
    """
    return AREAS.get(area_id)


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
    Forgets every ranking and every area, which is what ends one session
    """
    STORE.clear()
    AREAS.clear()
