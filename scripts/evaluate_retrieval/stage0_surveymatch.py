"""
Runs SurveyMatch, which asks a pipeline for the papers one review cited
"""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from driver import run_benchmark

from src.eval.survey_match import SurveyMatch


def main() -> None:
    """
    Mines the reviews and scores every recipe the config names
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()
    settings = tomllib.loads(Path(str(args.config_path)).read_text(encoding="utf-8"))
    budgets = [int(b) for b in settings["retriever_eval"]["BUDGETS"]]
    run_benchmark(SurveyMatch(None, budgets), str(args.config_path), {})


if __name__ == "__main__":
    main()
