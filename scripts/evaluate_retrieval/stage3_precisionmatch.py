"""
Runs PrecisionMatch, which asks how much of an answer is not about the topic at all
"""

from __future__ import annotations

import argparse

from driver import run_benchmark

from src.core.config import load_config
from src.core.parse_graph_export import load_graph_export
from src.eval.precision_match import PrecisionMatch


def main() -> None:
    """
    Mines the reviews and judges every recipe the config names
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()
    settings = load_config(str(args.config_path))
    block = settings["retriever_eval"]
    graph = load_graph_export(str(settings["dataset"]["GRAPH_PATH"]))  # pyright: ignore[reportAny]
    bench = PrecisionMatch(
        None,
        [int(b) for b in block["BUDGETS"]],
        graph,
        survey_threshold=float(block["SURVEY_THRESHOLD"]),
    )
    run_benchmark(bench, str(args.config_path), {})


if __name__ == "__main__":
    main()
