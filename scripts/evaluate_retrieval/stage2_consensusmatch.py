"""
Runs ConsensusMatch, which asks for the papers every review of a topic cites
"""

from __future__ import annotations

import argparse
from typing import Any

from driver import run_benchmark

from src.core.config import load_config
from src.eval.consensus_match import ConsensusMatch


def _floors(settings: dict[str, Any]) -> dict[str, float]:
    """
    The triple floors the miner needs, read out of the benchmark settings

    Args:
        settings: The parsed config.

    Returns:
        The keyword arguments for the miner.
    """
    block = settings["retriever_eval"]
    return {
        "gap_days": float(block["GAP_DAYS"]),
        "cosine": float(block["CONSENSUS_COSINE"]),
        "min_key": float(block["CONSENSUS_MIN_KEY"]),
    }


def main() -> None:
    """
    Mines the review triples and scores every recipe the config names
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()
    settings = load_config(str(args.config_path))
    budgets = [int(b) for b in settings["retriever_eval"]["BUDGETS"]]
    run_benchmark(ConsensusMatch(None, budgets), str(args.config_path), _floors(settings))


if __name__ == "__main__":
    main()
