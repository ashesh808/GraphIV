"""
What the frontier reservation buys and what it costs, swept as a slot count

Coverage is flat from 0 to 32 reserved slots while the picks get a year and a half newer
Only at 48 does the reservation start costing gold, so it is close to free in between
"""

from __future__ import annotations

import json
from typing import Any

from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)

NO_RESERVE = "no reservation"


def table() -> tuple[list[dict[str, Any]], dict[str, int]]:  # pyright: ignore[reportExplicitAny]
    """
    Each reservation size against the unreserved baseline, on coverage and on recency
    """
    raw = read_json(CACHE / "frontier_reach.json")
    arms: list[dict[str, Any]] = raw["arms"]  # pyright: ignore[reportExplicitAny,reportAny]
    base = next(a for a in arms if str(a["arm"]) == NO_RESERVE)
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for a in arms:
        rows.append(
            {
                "reservation": str(a["arm"]),
                "dev": int(a["dev"]),
                "test": int(a["test"]),
                "gold cost (dev)": int(a["dev"]) - int(base["dev"]),
                "median age": float(a["median age"]),
                "papers under 2 years old": int(a["within 1 year"]),
                "recency gain": int(a["within 1 year"]) - int(base["within 1 year"]),
            }
        )
    rows.sort(key=lambda r: float(r["median age"]), reverse=True)
    return rows, raw["gold_in_pool"]  # pyright: ignore[reportAny]


def run() -> None:
    """
    Print the reservation sweep and write the results, tables and figures
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows, gold = table()
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"sweep": rows, "gold_in_pool": gold}, indent=2), encoding="utf-8"
    )
    best = max(rows, key=lambda r: int(r["dev"]))
    tables.write(
        RESULTS,
        rows,
        [
            "reservation",
            "dev",
            "test",
            "gold cost (dev)",
            "median age",
            "papers under 2 years old",
            "recency gain",
        ],
        [
            ("reservation", "reservation"),
            ("dev", "dev"),
            ("median age", "median age"),
            ("papers under 2 years old", "under 2yr"),
        ],
        macro_pairs=[
            ("bestReservationDev", best["dev"]),
            ("bestReservation", best["reservation"]),
            ("recencyGainAtBest", best["recency gain"]),
        ],
        caption="Joint scoring throughout; only the reserved slot count varies",
    )
    bar_chart(
        rows,
        "reservation",
        [("dev", "gold found (dev)"), ("papers under 2 years old", "picks under 2 years old")],
        RESULTS / "reservation.png",
        title="What the frontier reservation buys",
    )
    print(tables.metrics_md(rows, list(rows[0].keys())))
