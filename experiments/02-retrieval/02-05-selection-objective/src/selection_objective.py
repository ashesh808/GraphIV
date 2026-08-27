"""
Every selection objective ever proposed for this pipeline, on one table

Scored on the 60 survey pools after the score fix, so the graph arms are not handicapped
The old 27-topic verdict that PPR wins survives against set coverage and loses to fusion
"""

from __future__ import annotations

import json
from typing import Any

from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)


def table() -> tuple[list[dict[str, Any]], dict[str, int]]:  # pyright: ignore[reportExplicitAny]
    """
    Selectors ranked on dev, carrying the pre-fix test score where one exists
    """
    raw = read_json(CACHE / "selectors.json")
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for r in raw["selectors"]:  # pyright: ignore[reportAny]
        was = r.get("test before score fix")
        rows.append(
            {
                "selector": str(r["selector"]),
                "family": str(r["family"]),
                "dev": int(r["dev"]),
                "test": int(r["test"]),
                "test before score fix": "" if was is None else int(was),
                "moved": "" if was is None else f"{int(r['test']) - int(was):+d}",
            }
        )
    return rows, raw["gold_in_pool"]


def by_family(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    The best each family of objective reaches, which is the ordering the suite argues for
    """
    out: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for fam in ("fused", "graph", "text", "set coverage"):
        vals = [r for r in rows if r["family"] == fam]
        if vals:
            best = max(vals, key=lambda r: int(r["dev"]))
            out.append(
                {
                    "family": fam,
                    "arms": len(vals),
                    "best arm": best["selector"],
                    "best dev": int(best["dev"]),
                    "best test": int(best["test"]),
                }
            )
    return out


def run() -> None:
    """
    Print the selector table and the per-family best, then write results and figures
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows, gold = table()
    fams = by_family(rows)
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"selectors": rows, "by_family": fams, "gold_in_pool": gold}, indent=2),
        encoding="utf-8",
    )
    tables.write(
        RESULTS,
        rows,
        ["selector", "family", "dev", "test", "test before score fix", "moved"],
        [("selector", "selector"), ("dev", "dev"), ("test", "test")],
        macro_pairs=[
            ("jointDev", rows[1]["dev"]),
            ("jointTest", rows[1]["test"]),
            ("oracleDev", rows[0]["dev"]),
            ("goldInPoolTest", gold["test"]),
        ],
        caption="60 survey pools, 80 slots each, gold is three or more mentions",
    )
    bar_chart(
        rows,
        "selector",
        [("dev", f"gold found on dev, of {gold['dev']}")],
        RESULTS / "selectors.png",
    )
    bar_chart(
        fams, "family", [("best dev", "best arm in each family, dev")], RESULTS / "by_family.png"
    )
    print(f"\ngold in pool: dev {gold['dev']}, test {gold['test']}\n")
    print(f"{'selector':<28} {'family':<13} {'DEV':>5} {'TEST':>5} {'was':>5} {'moved':>6}")
    for r in rows:
        print(
            f"{r['selector']:<28} {r['family']:<13} {r['dev']:>5} {r['test']:>5} "
            f"{str(r['test before score fix']):>5} {r['moved']:>6}"
        )
    print("\nbest of each family")
    for f in fams:
        print(f"  {f['family']:<13} {f['best arm']:<28} dev {f['best dev']:>4}")
