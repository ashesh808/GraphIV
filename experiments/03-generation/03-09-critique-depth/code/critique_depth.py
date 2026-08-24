"""
How deep the per-paper critique should go, varying only its width

Everything else is held constant on the deep path, with figures off
"""

from __future__ import annotations

from pathlib import Path

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import deep_panel  # noqa: E402

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir

RESULTS = _EXP / "results"

_BASE = {"effort": "standard", "deep": True, "max_rounds": 2, "figures": False}


def run(_use_cache: bool = True) -> None:
    conditions = [
        ("k0", {**_BASE, "critique_k": 0}),
        ("k4", {**_BASE, "critique_k": 4}),
        ("k8", {**_BASE, "critique_k": 8}),
    ]
    _ = run_experiment(
        results_dir=RESULTS,
        topic_keys=deep_panel(),
        conditions=conditions,
        label_key="critique_k",
        table_cols=[
            "critique_k",
            "n_topics",
            "n_critiques",
            "words",
            "num_density",
            "grounded",
            "gold_recall",
            "j_grounding",
            "j_coverage",
            "j_lineage",
            "faithfulness",
        ],
        plot_metrics=[
            ("num_density", "Specificity (digits / 1k chars)"),
            ("j_grounding", "Judge grounding (1-5)"),
            ("grounded", "Grounded citations"),
            ("n_critiques", "Full-PDF critiques folded in"),
        ],
        title="03-09: full-PDF critique depth (deep panel)",
        do_judge=True,
        do_faith=True,
        pairwise=("k8", "k0"),
        shared_runs=True,
    )


if __name__ == "__main__":
    run()
