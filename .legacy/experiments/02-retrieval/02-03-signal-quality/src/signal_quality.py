"""
Which pool signal actually predicts that the survey cited the paper

Runs on the 60 frozen pools, so gold membership replaces a model grading its own retrieval
The before column is the same measurement taken before the pool score fix in `fix_scores.py`
"""

from __future__ import annotations

import json
from typing import Any

from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)


def table() -> tuple[list[dict[str, Any]], dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    Each signal's gold yield over the same slot budget, with the pre-fix column beside it
    """
    raw = read_json(CACHE / "signal_quality.json")
    after: dict[str, Any] = raw["after"]  # pyright: ignore[reportExplicitAny,reportAny]
    before = {
        str(s["signal"]): int(s["gold found"])
        for s in raw["before"]["signals"]  # pyright: ignore[reportAny]
    }
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for s in after["signals"]:  # pyright: ignore[reportAny]
        name = str(s["signal"])
        rows.append(
            {
                "signal": name,
                "gold found": int(s["gold found"]),
                "precision": f"{100 * float(s['precision']):.1f}%",
                "lift": round(float(s["lift"]), 2),
                "before the score fix": before.get(name, int(s["gold found"])),
            }
        )
    return rows, after


def run() -> None:
    """
    Print the signal table and the complementarity split, then write results and figures
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows, after = table()
    comp: dict[str, int] = after["complementarity"]  # pyright: ignore[reportAny]
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"signals": rows, "complementarity": comp, "scale": after["scale"]}, indent=2),
        encoding="utf-8",
    )
    either = comp["both"] + comp["graph only"] + comp["reader only"]
    tables.write(
        RESULTS,
        rows,
        ["signal", "gold found", "precision", "lift", "before the score fix"],
        [
            ("signal", "signal"),
            ("gold found", "gold"),
            ("precision", "precision"),
            ("lift", "lift"),
        ],
        macro_pairs=[
            ("graphOnlyGold", comp["graph only"]),
            ("readerOnlyGold", comp["reader only"]),
            ("eitherGold", either),
            ("goldInPool", after["gold_in_pool"]),
        ],
        caption="60 frozen pools, gold is a reference the survey mentions three or more times",
    )
    bar_chart(
        rows,
        "signal",
        [("gold found", "gold found in the same slots"), ("lift", "lift over the base rate")],
        RESULTS / "signals.png",
        title="What each pool signal is worth",
    )
    bar_chart(
        [{"set": k, "gold": v} for k, v in sorted(comp.items())],
        "set",
        [("gold", "gold papers")],
        RESULTS / "complementarity.png",
        title="Where the graph and the reader disagree",
    )
    print(tables.metrics_md(rows, list(rows[0].keys())))
    print(
        tables.metrics_md([{"set": k, "gold": v} for k, v in sorted(comp.items())], ["set", "gold"])
    )
