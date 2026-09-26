"""
Runs FrontierMatch, which asks what the next review on a topic added
"""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path
from typing import Any

from driver import run_benchmark

from src.eval.frontier_match import FrontierMatch


def _floors(settings: dict[str, Any]) -> dict[str, float]:
    """
    The pair floors the miner needs, read out of the benchmark settings

    Args:
        settings: The parsed config.

    Returns:
        The keyword arguments for the miner.
    """
    block = settings["retriever_eval"]
    return {
        "gap_days": float(block["GAP_DAYS"]),
        "cosine": float(block["FRONTIER_COSINE"]),
        "window_days": float(block["FRONTIER_WINDOW_DAYS"]),
        "min_key": float(block["FRONTIER_MIN_KEY"]),
    }


def main() -> None:
    """
    Mines the review pairs and scores every recipe the config names
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()
    settings = tomllib.loads(Path(str(args.config_path)).read_text(encoding="utf-8"))
    budgets = [int(b) for b in settings["retriever_eval"]["BUDGETS"]]
    run_benchmark(FrontierMatch(None, budgets), str(args.config_path), _floors(settings))


if __name__ == "__main__":
    main()
