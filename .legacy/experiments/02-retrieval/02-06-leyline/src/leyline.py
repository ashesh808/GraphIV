"""
LeyLine's quota slots isolated, and the relevance floor that gates its walk

The walk runs cited to citing, so its threads end at the newest work on each lineage
Both answer keys are carried, since the earlier write-up used the looser one
"""

from __future__ import annotations

import json
from typing import Any

from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)

STRICT, LOOSE = "mentions_3", "mentions_1"
SHIPPED = "shipped (rel>=2, magnets only)"


def isolated() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    The quota's own picks against the slots they take, under both answer keys
    """
    raw = read_json(CACHE / "leyline.json")
    out: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for key, label in ((STRICT, "3+ mentions (suite standard)"), (LOOSE, "any mention")):
        ship = next(
            a for a in raw[key]["arms"] if str(a["arm"]) == SHIPPED
        )  # pyright: ignore[reportAny]
        disp = raw[key]["displaced"]
        out.append(
            {
                "answer key": label,
                "LeyLine picks": f"{float(ship['gold hit']):.1%}",
                "the slots they take": f"{float(disp['gold hit']):.1%}",
                "ratio": round(float(ship["gold hit"]) / float(disp["gold hit"]), 2),
                "LeyLine median age": float(ship["median age"]),
                "displaced median age": float(disp["median age"]),
            }
        )
    return out


def ceiling() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    Opening the magnet floor and the collection filter, scored on the suite's answer key
    """
    raw = read_json(CACHE / "leyline.json")
    disp = raw[STRICT]["displaced"]
    rows = [
        {
            "arm": "the PPR slots the quota takes",
            "picks": int(disp["picks"]),
            "gold hit": f"{float(disp['gold hit']):.1%}",
            "median age": float(disp["median age"]),
            "dev": int(disp["dev"]),
            "test": int(disp["test"]),
        }
    ]
    rows += [
        {
            "arm": str(a["arm"]),
            "picks": int(a["picks"]),
            "gold hit": f"{float(a['gold hit']):.1%}",
            "median age": float(a["median age"]),
            "dev": int(a["dev"]),
            "test": int(a["test"]),
        }
        for a in raw[STRICT]["arms"]  # pyright: ignore[reportAny]
    ]
    return rows


def run() -> None:
    """
    Print the isolation table, the floor ablation and the age context, then write results
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    raw = read_json(CACHE / "leyline.json")
    iso, ceil = isolated(), ceiling()
    ctx: list[dict[str, Any]] = raw[STRICT]["context"]  # pyright: ignore[reportExplicitAny]
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"isolated": iso, "ceiling": ceil, "context": ctx}, indent=2),
        encoding="utf-8",
    )
    ship = next(r for r in ceil if str(r["arm"]) == SHIPPED)
    tables.write(
        RESULTS,
        ceil,
        ["arm", "picks", "gold hit", "median age", "dev", "test"],
        [("arm", "arm"), ("gold hit", "gold hit"), ("median age", "median age")],
        macro_pairs=[
            ("leylineGoldHit", ship["gold hit"]),
            ("leylineAge", ship["median age"]),
            ("displacedGoldHit", ceil[0]["gold hit"]),
            ("displacedAge", ceil[0]["median age"]),
        ],
        caption="LeyLine's 8 quota slots isolated from the PPR base they ride on",
    )
    bar_chart(
        ceil, "arm", [("median age", "median age of the quota's picks")], RESULTS / "ceiling.png"
    )
    print("\nthe quota's own picks, against the slots they take")
    for r in iso:
        print(
            f"  {r['answer key']:<28} LeyLine {r['LeyLine picks']:>6} vs "
            f"{r['the slots they take']:>6}  ({r['ratio']}x), age "
            f"{r['LeyLine median age']} vs {r['displaced median age']}"
        )
    print(f"\n{'arm':<34} {'picks':>6} {'gold':>7} {'age':>5} {'DEV':>5} {'TEST':>5}")
    for r in ceil:
        print(
            f"{r['arm']:<34} {r['picks']:>6} {r['gold hit']:>7} "
            f"{r['median age']:>5.1f} {r['dev']:>5} {r['test']:>5}"
        )
    print("\nfor scale")
    for r in ctx:
        print(f"  {r['set']:<24} {int(r['n']):>6} papers, median age {float(r['median age'])}")
