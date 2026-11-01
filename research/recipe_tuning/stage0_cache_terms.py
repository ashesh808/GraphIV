"""
Caches every train and val case's pool and score terms, so the fit never touches the store

Every tuned recipe shares one retrieval prefix, so one pool per case serves all of them
Spawned workers pool the cases, each with its own graph and connection, as Postgres has the cores
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import time
from datetime import date
from multiprocessing.pool import Pool
from pathlib import Path
from typing import Any

import numpy as np
from driver import get_release
from metrics import FOLDERS, Sample, read_cases

from src.core.config import load_config
from src.core.embed import embed
from src.core.parse_graph_export import GraphExport, load_graph_export
from src.core.paths import OFFLINE_CONFIG
from src.retrieve.query import PaperQuery
from src.retrieve.recipe import build_pipeline, get_seed_limit, read_recipe
from src.retrieve.scorer import GraphScorer, Weights

TERMS = list(Weights.__dataclass_fields__)
BENCHMARKS = ("SurveyMatch", "FrontierMatch", "ConsensusMatch")
SPLITS = ("train", "val")
# the pool every tuned recipe builds, read from the one that ships with each benchmark
PREFIX = "survey.toml"

Pooled = tuple[np.ndarray, np.ndarray, int]

# each worker's own pipeline, built once by its initializer
STATE: dict[str, Any] = {}


def cache_path(config: dict[str, Any], metric: str, split: str) -> Path:
    """
    Where one benchmark's split is cached, under its version so a new cutoff never reads it

    Args:
        config: The parsed config.
        metric: The benchmark.
        split: train or val.

    Returns:
        The npz file.
    """
    root = Path(str(config["recipe_tuning"]["CACHE_PATH"]))
    return root / get_release(config).name / f"{FOLDERS[metric]}-{split}.npz"


def start_worker(config: dict[str, Any]) -> None:
    """
    Loads the graph and builds the shared pool's pipeline, once per worker

    Args:
        config: The parsed config.
    """
    recipe = read_recipe(Path(str(config["recipe_tuning"]["RECIPE_PATH"])) / PREFIX)
    graph: GraphExport = load_graph_export(str(config["dataset"]["GRAPH_PATH"]))
    pipeline: PaperQuery = build_pipeline(recipe, graph, str(config["database"]["PG_DEST"]))
    STATE.update(
        config=config,
        graph=graph,
        pipeline=pipeline,
        limit=get_seed_limit(recipe),
    )


def pool_case(case: Sample) -> Pooled:
    """
    One case's pool as its terms per paper and which of those papers are in its answer

    Args:
        case: The published case.

    Returns:
        The terms, the answer mask and the answer's size.
    """
    endpoints = STATE["config"]["endpoints"]
    pipeline: PaperQuery = STATE["pipeline"]
    graph: GraphExport = STATE["graph"]
    scorer = pipeline.scorers[0]
    assert isinstance(scorer, GraphScorer)
    vector = embed(str(endpoints["EMBED_API"]), str(endpoints["EMBED_NAME"]), case.query)
    pipeline.block(case.anchors)
    cap = date.fromisoformat(case.cutoff)
    pool = pipeline.build_pool(case.query, vector, STATE["limit"], cap)
    rows = scorer.get_paper_rows(pool)
    each = scorer.get_individual_score(pool, rows, graph.get_day_number(cap))
    terms = np.stack([each[t] for t in TERMS], axis=1).astype(np.float32)
    answer = set(case.key)
    return terms, np.array([p.arxiv_id in answer for p in pool], np.bool_), len(answer)


def cache_split(config: dict[str, Any], metric: str, split: str, workers: Pool) -> None:
    """
    Pools every case of one split across the workers and writes them as one npz

    The cases are concatenated in their published order, and `offsets` marks where each starts.

    Args:
        config: The parsed config.
        metric: The benchmark.
        split: train or val.
        workers: The worker pool.
    """
    out = cache_path(config, metric, split)
    if out.is_file():
        print(f"[cache] {out.name} exists, skipped", flush=True)
        return
    cases = read_cases(get_release(config), metric, split)
    done: list[Pooled] = []
    started = time.perf_counter()
    for i, pooled in enumerate(workers.imap(pool_case, cases, chunksize=4), 1):
        done.append(pooled)
        if i % 100 == 0:
            rate = (time.perf_counter() - started) / i
            print(f"[cache] {metric} {split} {i}/{len(cases)}, {rate:.2f}s a case", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out,
        terms=np.concatenate([d[0] for d in done]),
        hits=np.concatenate([d[1] for d in done]),
        offsets=np.concatenate([[0], np.cumsum([len(d[1]) for d in done])]),
        n_key=np.array([d[2] for d in done], np.int32),
        case_ids=np.array([c.sample_id for c in cases]),
        names=np.array(TERMS),
    )
    print(f"[cache] wrote {out}, {len(cases)} cases", flush=True)


def main() -> None:
    """
    Caches each benchmark's train and val split, skipping any already cached
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default=str(OFFLINE_CONFIG))
    _ = ap.add_argument("--workers", type=int, default=6, help="processes pooling cases at once")
    args = ap.parse_args()
    config = load_config(str(args.config_path))
    context = mp.get_context("spawn")
    with context.Pool(args.workers, initializer=start_worker, initargs=(config,)) as workers:
        for metric in BENCHMARKS:
            for split in SPLITS:
                cache_split(config, metric, split, workers)


if __name__ == "__main__":
    main()
