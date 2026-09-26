"""
How much of a report carries a citation, counted without a model

Every sentence either matches the citation pattern or does not, so there is no judgement here.
Table rows, headings and the run footer are excluded, since none of them is a claim.
"""

from __future__ import annotations

import json
from typing import Any

from _harness.measure import attribution
from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)


def measure() -> None:
    """
    Count the citing and non-citing sentences of every report listed in cache/reports.txt
    """
    paths = [REPO / ln for ln in (CACHE / "reports.txt").read_text().split() if ln.strip()]
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for rp in paths:
        run = json.loads((rp.parent / "run.json").read_text())  # pyright: ignore[reportAny]
        rows.append(
            {
                "report": rp.parent.parent.name,
                "mode": "survey" if run["rank"] == "joint" else "frontier",
                "graph": run["n_edges"] > 0,
                **attribution.coverage(rp.read_text()),
            }
        )
    _ = (CACHE / "coverage.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


def table() -> tuple[list[dict[str, Any]], dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    One row per report, plus the fold over all of them
    """
    raw = read_json(CACHE / "coverage.json")
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for r in raw:
        rows.append(
            {
                "report": str(r["report"])[:44],
                "mode": r["mode"],
                "digest": "graph" if r.get("graph", True) else "no graph",
                "sentences": int(r["sentences"]),
                "carry a citation": int(r["cited"]),
                "no citation": int(r["uncited"]),
                "coverage": round(int(r["cited"]) / max(1, int(r["sentences"])), 3),
            }
        )
    rows.sort(key=lambda r: (str(r["mode"]), str(r["report"]), str(r["digest"])))
    sent = sum(int(r["sentences"]) for r in rows)
    cited = sum(int(r["carry a citation"]) for r in rows)
    total = {
        "report": f"all {len(rows)}",
        "mode": "",
        "digest": "",
        "sentences": sent,
        "carry a citation": cited,
        "no citation": sent - cited,
        "coverage": round(cited / max(1, sent), 3),
    }
    return rows, total


def run() -> None:
    """
    Print the coverage table and write the results, tables and figure
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not (CACHE / "coverage.json").exists():
        measure()
    rows, total = table()
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"reports": rows, "total": total}, indent=2), encoding="utf-8"
    )
    cols = [
        "report",
        "mode",
        "digest",
        "sentences",
        "carry a citation",
        "no citation",
        "coverage",
    ]
    tables.write(
        RESULTS,
        [*rows, total],
        cols,
        [
            ("report", "Report"),
            ("sentences", "Sentences"),
            ("carry a citation", "Cited"),
            ("coverage", "Coverage"),
        ],
        macro_pairs=[
            ("coverageRate", total["coverage"]),
            ("coverageCited", total["carry a citation"]),
            ("coverageSentences", total["sentences"]),
        ],
        caption="Counted by pattern match, with no model involved",
    )
    bar_chart(
        rows,
        "report",
        [("coverage", "sentences carrying a citation")],
        RESULTS / "coverage.png",
        title="How much of each report is sourced",
    )
    print(tables.metrics_md([*rows, total], cols))
