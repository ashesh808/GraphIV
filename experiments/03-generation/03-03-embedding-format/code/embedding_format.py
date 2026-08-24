"""
Embedding format: the two spaces crossed against the two query shapings

Four conditions run the full pipeline, judged at temperature zero
"""

from __future__ import annotations

from pathlib import Path

from _harness.driver import run_experiment  # noqa: E402
from _harness.topics import TOPICS  # noqa: E402

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir

RESULTS = _EXP / "results"
GOLD = [k for k in TOPICS if TOPICS[k].canonical]  # gold-bearing topics (recall + judge)

CONDITIONS = [
    ("sym_hyde", {"effort": "fast", "embed_mode": "sym", "use_hyde": True}),
    ("sym_raw", {"effort": "fast", "embed_mode": "sym", "use_hyde": False}),
    ("asym_hyde", {"effort": "fast", "embed_mode": "asym", "use_hyde": True}),
    ("asym_raw", {"effort": "fast", "embed_mode": "asym", "use_hyde": False}),
]


def run(_use_cache: bool = True) -> None:
    _ = run_experiment(
        results_dir=RESULTS,
        topic_keys=GOLD,
        conditions=CONDITIONS,
        label_key="format",
        table_cols=[
            "format",
            "n_topics",
            "n_landmarks",
            "n_edges",
            "grounded",
            "off_digest",
            "landmark_recall",
            "spine_recall",
            "j_grounding",
            "j_coverage",
            "j_lineage",
            "j_coherence",
            "j_overall",
        ],
        plot_metrics=[
            ("j_overall", "Judge overall (1-5)"),
            ("landmark_recall", "Landmark recall (gold)"),
            ("spine_recall", "Spine recall"),
            ("n_edges", "Citation edges (lineage)"),
        ],
        title="03-03: embedding format (sym/asym x hyde/raw), Gemma-4-26B judge @ T=0",
        do_judge=True,
        pairwise=("asym_raw", "sym_hyde"),
    )


if __name__ == "__main__":
    run()
