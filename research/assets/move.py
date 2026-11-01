"""
Copies each figure in assets/figures beside the Hugging Face card that links it

A figure no card links stays in assets/figures, where the root README links it
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
CARDS = HERE.parents[1] / "offline" / "export" / "cards"
# each figure's card, by the card's directory under CARDS
DESTINATIONS = {
    "dataset": "data",
    "dataset-papers-citations": "data",
    "dataset-topics": "data",
    "benchmarks": "benchmarks",
    "benchmarks-surveymatch": "benchmarks",
    "benchmarks-frontiermatch": "benchmarks",
    "benchmarks-consensusmatch": "benchmarks",
    "citation-labeler": "citation_labeler",
    "citation-labeling-pipeline": "citation_labeler",
    "survey-labeler": "survey_labeler",
    "survey-labeling-pipeline": "survey_labeler",
}


def main() -> None:
    """
    Copies every figure that has a card, and names the ones that do not
    """
    for figure in sorted((HERE / "figures").glob("*.png")):
        card = DESTINATIONS.get(figure.stem)
        if card is None:
            print(f"[move] {figure.name} stays here, for the README that links it", flush=True)
            continue
        _ = shutil.copy2(figure, CARDS / card / figure.name)
        print(f"[move] {figure.name} -> {CARDS / card}", flush=True)


if __name__ == "__main__":
    main()
