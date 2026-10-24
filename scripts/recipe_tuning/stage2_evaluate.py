"""
Scores every recipe config.toml lists on one split of all four benchmarks

PrecisionMatch reuses the SurveyMatch cases and judges what is on topic, since it has no answer key
"""

from __future__ import annotations

import argparse

from driver import run_benchmark
from metrics import ConsensusMatch, FrontierMatch, Match, SurveyMatch
from precision import PrecisionMatch

from src.core.config import load_config
from src.core.parse_graph_export import load_graph_export

BENCHMARKS = ("SurveyMatch", "FrontierMatch", "ConsensusMatch", "PrecisionMatch")


def main() -> None:
    """
    Loads the graph once, then runs each benchmark named, all four when none is
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    _ = ap.add_argument(
        "--split", default="", help="train, val or test, [recipe_tuning] SPLIT if empty"
    )
    _ = ap.add_argument("benchmarks", nargs="*", help="the benchmarks to run, all four if none")
    args = ap.parse_args()
    unknown = sorted(set(args.benchmarks) - set(BENCHMARKS))
    if unknown:
        ap.error(
            f"no benchmark named {', '.join(unknown)}, the benchmarks are {', '.join(BENCHMARKS)}"
        )
    config = load_config(str(args.config_path))
    settings = config["recipe_tuning"]
    split = str(args.split or settings["SPLIT"])
    budgets = [int(b) for b in settings["BUDGETS"]]
    graph = load_graph_export(str(config["dataset"]["GRAPH_PATH"]))
    built: dict[str, Match] = {
        "SurveyMatch": SurveyMatch(budgets),
        "FrontierMatch": FrontierMatch(budgets),
        "ConsensusMatch": ConsensusMatch(budgets),
        "PrecisionMatch": PrecisionMatch(
            budgets,
            graph,
            survey_threshold=float(config["benchmarks"]["SURVEY_THRESHOLD"]),
        ),
    }
    for name in args.benchmarks or BENCHMARKS:
        run_benchmark(built[name], config, split, graph)


if __name__ == "__main__":
    main()
