"""
Whether the figure gallery earns its place, toggling it on and off

When it is on, the vision model crops each top landmark's first figure and captions it
"""

from __future__ import annotations

from pathlib import Path

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import deep_panel  # noqa: E402

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir

RESULTS = _EXP / "results"

_BASE = {"effort": "standard", "deep": True, "max_rounds": 2, "critique_k": 4}


def run(_use_cache: bool = True) -> None:
    conditions = [
        ("figures-on", {**_BASE, "figures": True}),
        ("figures-off", {**_BASE, "figures": False}),
    ]
    _ = run_experiment(
        results_dir=RESULTS,
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
        title="03-10: vision figure augmentation (deep panel)",
        do_judge=True,
        do_vision=True,
        shared_runs=True,
    )


if __name__ == "__main__":
    run()
