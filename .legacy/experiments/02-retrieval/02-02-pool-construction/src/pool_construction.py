"""
Pool-stage recall on 60 surveys, one lever at a time, with no reader and no LLM

Half the gold never reaches the pool and no knob recovers it, so this is the ceiling
Of the four levers only the ancestor floor moves the answer, and it is already set right
"""

from __future__ import annotations

import json
from typing import Any

from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)

SHIPPED = "shipped"

"""
Which stage of the front end each lever belongs to.
The grouping is the finding: everything before the citation graph turned out to be inert.
"""
STAGE = {
    "ef_search 40 (the old silent default)": "vector channel",
    "lexical off": "lexical channel",
    "lexical OR (bug fixed)": "lexical channel",
    "n_pool 200": "vector channel",
    "n_pool 600": "vector channel",
    "n_pool 800": "vector channel",
    "ancestor floor 0.25": "citation graph",
    "ancestor floor 0.35": "citation graph",
    "ancestor floor 0.4": "citation graph",
    "ancestor floor 0.45": "citation graph",
}


def _read(name: str) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
    return read_json(CACHE / name)


def ceiling() -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """
    How much of the answer key ever reaches the pool, which bounds every later experiment
    """
    raw: dict[str, Any] = _read("pool_recall.json")  # pyright: ignore[reportExplicitAny]
    gold: dict[str, int] = raw["total_gold"]
    ship = next(a for a in raw["arms"] if a["name"] == SHIPPED)  # pyright: ignore[reportAny]
    total = int(gold["dev"]) + int(gold["test"])
    found = int(ship["dev"]) + int(ship["test"])
    return {
        "gold papers": total,
        "reach the pool": found,
        "never arrive": total - found,
        "share reached": f"{found / total:.0%}",
    }


def sweep() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    Every arm against shipped, tagged by which stage of the front end the lever sits in
    """
    raw: dict[str, Any] = _read("pool_recall.json")  # pyright: ignore[reportExplicitAny]
    base = next(a for a in raw["arms"] if a["name"] == SHIPPED)  # pyright: ignore[reportAny]
    ref = int(base["dev"]) + int(base["test"])
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for a in raw["arms"]:  # pyright: ignore[reportAny]
        name = str(a["name"])
        total = int(a["dev"]) + int(a["test"])
        rows.append(
            {
                "lever": name,
                "stage": "shipped default" if name == SHIPPED else STAGE[name],
                "gold in pool": total,
                "vs shipped": total - ref,
                "avg pool size": round((int(a["pool_dev"]) + int(a["pool_test"])) / 60),
            }
        )
    rows.sort(key=lambda r: -int(r["gold in pool"]))
    return rows


def by_stage(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    The spread each stage's levers can produce, which is where the inert ones show up
    """
    out: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for stage in ("vector channel", "lexical channel", "citation graph"):
        deltas = [int(r["vs shipped"]) for r in rows if r["stage"] == stage]
        out.append(
            {
                "stage": stage,
                "levers": len(deltas),
                "best": max(deltas),
                "worst": min(deltas),
                "spread": max(deltas) - min(deltas),
            }
        )
    return out


def run() -> None:
    """
    Print the ceiling, the sweep and the per-stage spread, then write tables and figures
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    cap, rows = ceiling(), sweep()
    stages = by_stage(rows)
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"ceiling": cap, "sweep": rows, "by_stage": stages}, indent=2),
        encoding="utf-8",
    )
    tables.write(
        RESULTS,
        rows,
        ["lever", "stage", "gold in pool", "vs shipped", "avg pool size"],
        [("lever", "lever"), ("gold in pool", "gold in pool"), ("vs shipped", "vs shipped")],
        macro_pairs=[
            ("poolGoldTotal", cap["gold papers"]),
            ("poolGoldFound", cap["reach the pool"]),
            ("poolGoldLost", cap["never arrive"]),
            ("graphSpread", stages[2]["spread"]),
        ],
        caption="Pool-stage recall over 60 surveys, one lever moved at a time",
    )
    bar_chart(
        rows,
        "lever",
        [("gold in pool", f"gold reaching the pool, of {cap['gold papers']}")],
        RESULTS / "sweep.png",
    )
    bar_chart(
        stages,
        "stage",
        [("spread", "how many papers a stage's levers can move")],
        RESULTS / "by_stage.png",
    )
    print("\nceiling")
    for k, v in cap.items():
        print(f"   {k}: {v}")
    print("\nsweep")
    for r in rows:
        print(
            f"   {r['lever']:<38} {r['stage']:<16} {r['gold in pool']:>5} "
            f"{r['vs shipped']:>+5}  pool {r['avg pool size']:>4}"
        )
    print("\nspread each stage can produce")
    for r in stages:
        print(
            f"   {r['stage']:<16} {r['levers']} levers, best {r['best']:+}, "
            f"worst {r['worst']:+}, spread {r['spread']}"
        )
