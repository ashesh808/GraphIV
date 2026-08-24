"""
Component ablation: knock out one component at a time and read the whole vector

Dropping the citation graph inflates the frontier count while zeroing edges
That is the finding, and it is why no single metric is ever reported alone
"""

from __future__ import annotations

from pathlib import Path

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import battery  # noqa: E402

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir

RESULTS = _EXP / "results"


def run(_use_cache: bool = True) -> None:
    conditions = [
        ("full", {"effort": "standard", "rank": "ppr"}),
        ("indegree", {"effort": "standard", "rank": "indegree"}),
        ("no_cluster", {"effort": "standard", "rank": "ppr", "no_cluster": True}),
        ("no_graph", {"effort": "standard", "rank": "ppr", "no_graph": True}),
        ("no_fulltext", {"effort": "fast", "rank": "ppr"}),
    ]
    _ = run_experiment(
        results_dir=RESULTS,
        topic_keys=battery(),
        conditions=conditions,
        label_key="config",
        table_cols=[
            "config",
            "n_topics",
            "n_landmarks",
            "n_edges",
            "frontier_count",
            "grounded",
            "off_digest",
            "num_density",
            "landmark_recall",
            "j_overall",
            "faithfulness",
        ],
        plot_metrics=[
            ("n_edges", "Citation edges (lineage)"),
            ("frontier_count", "Frontier landmarks"),
            ("off_digest", "Off-digest (lower=better)"),
            ("j_overall", "Judge overall (1-5)"),
        ],
        title="03-02: component ablation (mean over battery)",
        do_judge=True,
        do_faith=True,
    )


if __name__ == "__main__":
    run()
