"""
The shared half of every benchmark entrypoint, which the four stage scripts call

Mining runs once and every recipe is scored on the same samples, so a comparison is paired
Each recipe writes its own directory and the figure above them compares the lot
"""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

from src.core.config import load_config
from src.core.embed import embed
from src.core.parse_graph_export import GraphExport, load_graph_export
from src.eval.cases import CaseMiner, Sample
from src.eval.match import Match, Score
from src.eval.query_writer import GemmaWriter
from src.eval.report import plot_comparison, write_run
from src.retrieve.recipe import build_pipeline, get_seed_limit, read_recipe

LOG = logging.getLogger(__name__)


def setup_logging(path: Path) -> None:
    """
    Sends every line to the console and to a file beside the run

    Args:
        path: Where the log is written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(path, mode="w")],
        force=True,
    )


def get_prefix(recipe: dict[str, Any]) -> str:
    """
    A name for everything a recipe does before it scores, which is what decides the pool

    Two recipes sharing a prefix see the same candidates, so the pool is built once for both and
    only the scoring is repeated.

    Args:
        recipe: A parsed recipe.

    Returns:
        The name.
    """
    parts: list[str] = []
    for block in recipe["component"]:
        kind = str(block["KIND"])
        if kind == "GraphScorer":
            break
        parts.append(f"{kind}:{block.get('LIMIT', '')}:{block.get('TOP_K', '')}")
        parts.append(str(block.get("HOP_LIMIT", "")))
    return "|".join(parts)


def run_benchmark(bench: Match, config_path: str, mine_args: dict[str, float]) -> None:
    """
    Mines one benchmark's samples, scores every recipe on them and writes the run

    Args:
        bench: The metric, which owns the query and the score.
        config_path: Where config.toml lives.
        mine_args: The per-metric floors the miner needs.
    """
    config: dict[str, Any] = load_config(config_path)
    settings = dict(config["retriever_eval"])
    endpoints, dsn = config["endpoints"], str(config["database"]["PG_DEST"])
    out_root = Path(str(settings["OUTPUT_PATH"])) / bench.name
    setup_logging(out_root / "run.log")
    started = time.perf_counter()

    names = [str(r) for r in settings["recipes"][bench.name]]
    LOG.info("%s: %d recipes, %s", bench.name, len(names), ", ".join(names))

    miner = CaseMiner(
        dsn,
        seed=int(settings["SEED"]),
        max_samples=int(settings["MAX_SAMPLES"]),
        sample_rate=float(settings["SAMPLE_RATE"]),
        survey_threshold=float(settings["SURVEY_THRESHOLD"]),
        min_references=int(settings["MIN_REFERENCES"]),
    )
    samples = miner.mine(bench.name, **mine_args)
    if not samples:
        LOG.error("%s mined nothing, stopping", bench.name)
        return

    writer = GemmaWriter(
        str(endpoints["LLM_API"]),
        str(endpoints["LLM_NAME"]),
        Path(str(settings["OUTPUT_PATH"])).parent / "queries",
    )
    bench.writer = writer
    for sample in samples:
        object.__setattr__(sample, "query", bench.build_query(sample))
    LOG.info("wrote %d queries", sum(1 for s in samples if s.query))

    graph = load_graph_export(str(config["dataset"]["GRAPH_PATH"]))
    recipes = [(n, read_recipe(Path(str(settings["RECIPE_PATH"])) / n)) for n in names]
    groups: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for name, recipe in recipes:
        groups.setdefault(get_prefix(recipe), []).append((name, recipe))
    LOG.info("%d recipes fall into %d pools", len(recipes), len(groups))

    by_recipe: dict[str, list[Score]] = {}
    for prefix, group in groups.items():
        LOG.info("pool %s serves %s", prefix, ", ".join(n for n, _ in group))
        by_recipe |= _score_group(bench, group, samples, graph, dsn, endpoints)
    for name, recipe in recipes:
        label = str(recipe.get("NAME", Path(name).stem))
        write_run(
            out_root / label, recipe, settings | {"metric": bench.name}, by_recipe.get(label, [])
        )

    plot_comparison(out_root / "performance.png", bench.name, bench.headline, by_recipe)
    LOG.info("%s finished in %.1fs", bench.name, time.perf_counter() - started)


def _score_group(
    bench: Match,
    group: list[tuple[str, dict[str, Any]]],
    samples: list[Sample],
    graph: GraphExport,
    dsn: str,
    endpoints: dict[str, Any],
) -> dict[str, list[Score]]:
    """
    Every sample through one pool, scored once per recipe that shares it

    Args:
        bench: The metric.
        group: The recipes sharing a retrieval prefix.
        samples: The mined samples, shared across recipes so the comparison is paired.
        graph: The citation graph export.
        dsn: libpq connection string.
        endpoints: The embedding and llm endpoints.

    Returns:
        One list of scores per recipe label.
    """
    head = group[0][1]
    seed_limit = get_seed_limit(head)
    labels = [str(recipe.get("NAME", Path(name).stem)) for name, recipe in group]
    out: dict[str, list[Score]] = {label: [] for label in labels}
    # the steps are the same for every sample, so only the blocklist moves between them
    pipelines = [
        build_pipeline(recipe, graph, dsn)  # pyright: ignore[reportArgumentType]
        for _, recipe in group
    ]

    for i, sample in enumerate(samples, 1):
        vector = embed(str(endpoints["EMBED_API"]), str(endpoints["EMBED_NAME"]), sample.query)
        for pipeline in pipelines:
            pipeline.block(sample.anchors)
        started = time.perf_counter()
        pool = pipelines[0].build_pool(
            sample.query, vector, retrieve_limit=seed_limit, max_date=_as_date(sample.cutoff)
        )
        pooled = time.perf_counter() - started
        for label, pipeline in zip(labels, pipelines, strict=True):
            clock = time.perf_counter()
            papers = pipeline.score_pool(sample.query, vector, pool, _as_date(sample.cutoff))
            seconds = pooled + time.perf_counter() - clock
            score = bench.compute_score(sample, [p.arxiv_id for p in papers], seconds)
            out[label].append(score)
            LOG.info(
                "%s %-14s %4d/%d %s pool %6d key %4d ceiling %.3f @%s %.3f %5.2fs",
                bench.name,
                label,
                i,
                len(samples),
                sample.sample_id[:22],
                score.n_pool,
                score.n_key,
                score.ceiling,
                bench.headline,
                score.recall.get(bench.headline, 0.0),
                seconds,
            )
    return out


def _as_date(text: str) -> date:
    """
    A cutoff string as a date

    Args:
        text: An iso date.

    Returns:
        The date.
    """
    return date.fromisoformat(text)
