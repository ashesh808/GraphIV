"""
Configuration: one TOML file, typed sections, repo-relative path resolution

Resolution runs an explicit path argument, then $GRAPHIV_CONFIG, then the repo's config.toml
Nothing is read at import, so a Config only exists once someone calls load
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RetrieveCfg:
    """
    Constants for the retrieval redesign parked in scratchpad/graphiv-redesign

    The shipped pipeline reads its knobs from the stage tables instead.
    """

    n_pool: int
    k_lexical: int
    reranker: str
    rrf_k: int
    topic_map: bool
    vote_k: int
    use_siblings: bool
    frontier_pull_max: int
    frontier_probe: int
    ancestor_max_add: int
    ancestor_min_citers: int
    ancestor_min_cosine: float
    m: int
    grade_concurrency: int
    selector: str
    quota: int
    gamma: float
    seeds: int
    max_lineages: int
    recency: float
    ppr_alpha: float
    ppr_iters: int


@dataclass(frozen=True)
class Config:
    """
    Parsed config.toml, with env overrides already applied

    Construct it with Config.load(); sections are plain attributes.
    """

    pg_dsn: str
    embed_api: str
    embed_model: str
    embed_dim: int
    embed_rows: int
    embed_max_seq: int
    embed_space: str
    embed_query_prompt: str
    embed_sym_prompt: str
    llm_base_url: str
    llm_router: str
    map_model: str
    narrator_model: str
    vision_model: str
    data_dir: Path
    topic_tree_db: Path
    grade_cache_db: Path
    arxiv_json: Path
    sqlite_db: Path
    sqlite_schemas: Path
    pdf_dir: Path
    html_dir: Path
    citation_stats: Path
    citation_labels: Path
    models_dir: Path
    hf_cache: Path
    community_summary_db: Path
    fulltext_cache_db: Path
    theme: Path
    output_dir: Path
    preset_dir: Path
    kaggle_url: str
    html_migrate_src: str
    nomic_npy: str
    nomic_umap50_npy: str
    old_sqlite: str
    retrieve: RetrieveCfg
    stages: dict[str, dict[str, Any]] = field(  # pyright: ignore[reportExplicitAny]
        default_factory=dict
    )

    @staticmethod
    def load(path: Path | None = None) -> Config:
        """
        Read and type the config file

        Args:
            path: explicit config file; falls back to $GRAPHIV_CONFIG, then
                <repo root>/config.toml.

        Returns:
            Frozen Config with env overrides (ARXIVKG_PG_DSN, GRAPHIV_EMBED_API)
            already applied.
        """
        p = path or Path(os.environ.get("GRAPHIV_CONFIG", REPO_ROOT / "config.toml"))
        with open(p, "rb") as f:
            raw: dict[str, Any] = tomllib.load(f)  # pyright: ignore[reportExplicitAny]

        pg: dict[str, Any] = raw["postgres"]  # pyright: ignore[reportExplicitAny]
        emb: dict[str, Any] = raw["embeddings"]  # pyright: ignore[reportExplicitAny]
        llm: dict[str, Any] = raw["llm"]  # pyright: ignore[reportExplicitAny]
        paths: dict[str, Any] = raw["paths"]  # pyright: ignore[reportExplicitAny]
        dl: dict[str, Any] = raw["download"]  # pyright: ignore[reportExplicitAny]
        eb: dict[str, Any] = raw["embeddings_build"]  # pyright: ignore[reportExplicitAny]  # fmt: skip
        ret: dict[str, Any] = raw["retrieve"]  # pyright: ignore[reportExplicitAny]
        stages: dict[str, dict[str, Any]] = raw.get("stage", {})  # pyright: ignore[reportExplicitAny]  # fmt: skip

        dsn = os.environ.get("ARXIVKG_PG_DSN") or (
            f"host={gpath(str(pg['socket_dir']))} "
            f"port={int(pg['port'])} dbname={str(pg['dbname'])}"
        )
        return Config(
            pg_dsn=dsn,
            embed_api=os.environ.get("GRAPHIV_EMBED_API") or str(emb["api"]),
            embed_model=str(emb["model"]),
            embed_dim=int(emb["dim"]),
            embed_rows=int(emb["rows"]),
            embed_max_seq=int(emb["max_seq"]),
            embed_space=str(emb["space"]),
            embed_query_prompt=str(emb["query_prompt"]),
            embed_sym_prompt=str(emb["sym_prompt"]),
            llm_base_url=str(llm["base_url"]),
            llm_router=str(llm["router"]),
            map_model=str(llm["map_model"]),
            narrator_model=str(llm["narrator_model"]),
            vision_model=str(llm["vision_model"]),
            data_dir=gpath(str(paths["data_dir"])),
            topic_tree_db=gpath(str(paths["topic_tree_db"])),
            grade_cache_db=gpath(str(paths["grade_cache_db"])),
            arxiv_json=gpath(str(paths["arxiv_json"])),
            sqlite_db=gpath(str(paths["sqlite_db"])),
            sqlite_schemas=gpath(str(paths["sqlite_schemas"])),
            pdf_dir=gpath(str(paths["pdf_dir"])),
            html_dir=gpath(str(paths["html_dir"])),
            citation_stats=gpath(str(paths["citation_stats"])),
            citation_labels=gpath(str(paths["citation_labels"])),
            models_dir=gpath(str(paths["models_dir"])),
            hf_cache=gpath(str(paths["hf_cache"])),
            community_summary_db=gpath(str(paths["community_summary_db"])),
            fulltext_cache_db=gpath(str(paths["fulltext_cache_db"])),
            theme=gpath(str(paths["theme"])),
            output_dir=gpath(str(paths["output_dir"])),
            preset_dir=gpath(str(paths.get("preset_dir", "research-preset"))),
            kaggle_url=str(dl["kaggle_url"]),
            html_migrate_src=str(dl["html_migrate_src"]),
            nomic_npy=str(eb["nomic_npy"]),
            nomic_umap50_npy=str(eb["nomic_umap50_npy"]),
            old_sqlite=str(eb["old_sqlite"]),
            retrieve=RetrieveCfg(
                n_pool=int(ret["n_pool"]),
                k_lexical=int(ret["k_lexical"]),
                reranker=str(ret["reranker"]),
                rrf_k=int(ret["rrf_k"]),
                topic_map=bool(ret["topic_map"]),
                vote_k=int(ret["vote_k"]),
                use_siblings=bool(ret["use_siblings"]),
                frontier_pull_max=int(ret["frontier_pull_max"]),
                frontier_probe=int(ret["frontier_probe"]),
                ancestor_max_add=int(ret["ancestor_max_add"]),
                ancestor_min_citers=int(ret["ancestor_min_citers"]),
                ancestor_min_cosine=float(ret["ancestor_min_cosine"]),
                m=int(ret["m"]),
                grade_concurrency=int(ret["grade_concurrency"]),
                selector=str(ret["selector"]),
                quota=int(ret["quota"]),
                gamma=float(ret["gamma"]),
                seeds=int(ret["seeds"]),
                max_lineages=int(ret["max_lineages"]),
                recency=float(ret["recency"]),
                ppr_alpha=float(ret["ppr_alpha"]),
                ppr_iters=int(ret["ppr_iters"]),
            ),
            stages=stages,
        )


def gpath(value: str) -> Path:
    """
    Resolve a config path string: absolute as-is, else relative to the repo root

    Args:
        value: path string from config.toml.

    Returns:
        Absolute Path.
    """
    p = Path(value)
    return p if p.is_absolute() else REPO_ROOT / p
