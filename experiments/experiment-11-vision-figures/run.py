"""experiment-6 — Vision figure augmentation.

Toggles the deep-loop figure gallery (`figures` on/off). When on, the vision model
(Gemma-4-26B-Vision) crops Figure-1 from top landmarks' PDFs and captions them. We measure how
many figures are produced and — the real question — whether the captions are FAITHFUL to the
images, re-checked by the vision model against each saved crop.

    uv run python experiments/experiment-6-vision-figures/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import deep_panel  # noqa: E402

HERE = Path(__file__).resolve().parent

_BASE = {"effort": "standard", "deep": True, "max_rounds": 2, "critique_k": 4}


def main() -> None:
    conditions = [
        ("figures-on", {**_BASE, "figures": True}),
        ("figures-off", {**_BASE, "figures": False}),
    ]
    _ = run_experiment(
        results_dir=HERE / "results",
        topic_keys=deep_panel(),
        conditions=conditions,
        label_key="figures",
        table_cols=[
            "figures",
            "n_topics",
            "n_figures",
            "fig_checked",
            "caption_faithfulness",
            "words",
            "grounded",
            "gold_recall",
            "j_coverage",
        ],
        plot_metrics=[
            ("n_figures", "Figures captioned"),
            ("caption_faithfulness", "Caption faithfulness (0-1)"),
            ("words", "Review length (words)"),
            ("j_coverage", "Judge coverage (1-5)"),
        ],
        title="experiment-11: vision figure augmentation (deep panel)",
        do_judge=True,
        do_vision=True,
        shared_runs=True,
    )


if __name__ == "__main__":
    main()
