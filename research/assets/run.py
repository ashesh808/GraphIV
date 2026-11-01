"""
Draws the card figures into assets/figures, each by its own generator in assets/code

The figure <name>.png is drawn by code/generate_<name>.py, with its dashes as underscores
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIGURES = (
    "dataset",
    "dataset-papers-citations",
    "dataset-topics",
    "benchmarks",
    "benchmarks-surveymatch",
    "benchmarks-frontiermatch",
    "benchmarks-consensusmatch",
    "citation-labeler",
    "citation-labeling-pipeline",
    "survey-labeler",
    "survey-labeling-pipeline",
    "poster",
    "bounded-field",
    "leyline",
    "research-pipeline",
)


def main() -> None:
    """
    Runs the generator of every figure named, or of all of them when none is
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("names", nargs="*", help="figures to draw, all of them when none is named")
    _ = ap.add_argument("--config_path", default=str(HERE.parents[1] / "configs" / "offline.toml"))
    args = ap.parse_args()
    unknown = sorted(set(args.names) - set(FIGURES))
    if unknown:
        ap.error(f"no figure named {', '.join(unknown)}, the figures are {', '.join(FIGURES)}")
    out = HERE / "figures"
    out.mkdir(exist_ok=True)
    for name in args.names or FIGURES:
        script = HERE / "code" / f"generate_{name.replace('-', '_')}.py"
        figure = out / f"{name}.png"
        command = [sys.executable, str(script), "--out", str(figure)]
        _ = subprocess.run([*command, "--config_path", str(args.config_path)], check=True)


if __name__ == "__main__":
    main()
