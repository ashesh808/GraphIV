"""
How many judge rounds are worth running, varying only the round cap

Everything else is held constant on the deep path, with figures off to isolate the loop
The judge still owns termination, so a high cap may stop early on its own
"""

from __future__ import annotations

from pathlib import Path

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import deep_panel  # noqa: E402

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir

RESULTS = _EXP / "results"

_BASE = {"effort": "standard", "deep": True, "critique_k": 4, "figures": False}


def run(_use_cache: bool = True) -> None:
    # extend the cap to 6 to find the saturation point (the judge still owns early termination)
    conditions = [
        ("rounds-1", {**_BASE, "max_rounds": 1}),
        ("rounds-2", {**_BASE, "max_rounds": 2}),
        ("rounds-4", {**_BASE, "max_rounds": 4}),
        ("rounds-6", {**_BASE, "max_rounds": 6}),
    ]
    _ = run_experiment(
        results_dir=RESULTS,
        topic_keys=deep_panel(),
        conditions=conditions,
        label_key="rounds",
        table_cols=[
            "rounds",
            "n_topics",
            "rounds_run",
            "n_landmarks",
            "words",
            "frontier_count",
            "grounded",
            "num_density",
            "gold_recall",
            "j_coverage",
            "j_lineage",
            "j_overall",
            "faithfulness",
        ],
        plot_metrics=[
            ("rounds_run", "Rounds actually run (judge-stopped)"),
            ("n_landmarks", "Landmarks covered"),
            ("j_coverage", "Judge coverage (1-5)"),
            ("frontier_count", "Frontier landmarks"),
        ],
        title="03-08: judge-loop rounds / test-time compute (deep panel)",
        do_judge=True,
        do_faith=True,
        pairwise=("rounds-6", "rounds-1"),
        shared_runs=True,
    )


if __name__ == "__main__":
    run()
