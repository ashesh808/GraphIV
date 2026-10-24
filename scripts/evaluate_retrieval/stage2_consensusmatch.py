"""
Runs ConsensusMatch, which asks for the papers every review of a topic cites
"""

from __future__ import annotations

import argparse

from driver import run_benchmark

from src.core.config import load_config
from src.eval.consensus_match import ConsensusMatch


def main() -> None:
    """
    Reads the review triples and scores every recipe the config names
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()
    settings = load_config(str(args.config_path))
    budgets = [int(b) for b in settings["retriever_eval"]["BUDGETS"]]
    run_benchmark(ConsensusMatch(None, budgets), str(args.config_path))


if __name__ == "__main__":
    main()
