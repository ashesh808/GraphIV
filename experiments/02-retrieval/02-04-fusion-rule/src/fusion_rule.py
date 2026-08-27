"""
How to spend one budget of landmark slots across two signals that disagree

The combining rule barely matters; which signal goes in matters a lot
Selection reads dev only, and test is printed once at the end
"""

from __future__ import annotations

import json
from typing import Any

from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)

"""
Which family each rule belongs to.
The grouping is the finding: every smooth rule lands in the same place and the hard splits do not.
"""
FAMILY = {
    "blend 0.5 graph": "smooth blend",
    "blend 0.65 graph": "smooth blend",
    "blend 0.35 graph": "smooth blend",
    "blend 0.8 graph": "smooth blend",
    "multiply, graph x grade": "smooth blend",
    "grade first, graph breaks ties": "smooth blend",
    "rrf, graph + reader": "smooth blend",
    "rrf, all three": "smooth blend",
    "quota 60 graph / 20 reader": "hard split",
    "quota 40 graph / 40 reader": "hard split",
    "quota 20 graph / 60 reader": "hard split",
    "multiply, cosine x grade": "weak input",
    "cosine only": "single signal",
    "graph only": "single signal",
    "reader only": "single signal",
}


def table() -> tuple[list[dict[str, Any]], dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    Every rule with the share of the single-signal-to-oracle headroom it captures
    """
    raw = read_json(CACHE / "fusion.json")
    best = int(raw["best_single_dev"])
    head = int(raw["headroom_dev"])
    rows = [
        {
            "rule": str(r["rule"]),
            "family": FAMILY.get(str(r["rule"]), ""),
            "dev": int(r["dev"]),
            "test": int(r["test"]),
            "headroom taken": f"{(int(r['dev']) - best) / head:.0%}",
        }
        for r in raw["rules"]  # pyright: ignore[reportAny]
    ]
    return rows, raw


def by_family(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    The dev spread inside each family, which is how little the combining rule matters
    """
    out: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for fam in ("smooth blend", "hard split", "weak input", "single signal"):
        vals = [int(r["dev"]) for r in rows if r["family"] == fam]
        if vals:
            out.append(
                {
                    "family": fam,
                    "rules": len(vals),
                    "best": max(vals),
                    "worst": min(vals),
                    "spread": max(vals) - min(vals),
                }
            )
    return out


def run() -> None:
    """
    Print the rule table and the per-family spread, then write results and figures
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows, raw = table()
    fams = by_family(rows)
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps(
            {
                "rules": rows,
                "by_family": fams,
                "bounds": {
                    "gold_in_pool": raw["gold_in_pool"],
                    "oracle": raw["oracle"],
                    "best_single_dev": raw["best_single_dev"],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tables.write(
        RESULTS,
        rows,
        ["rule", "family", "dev", "test", "headroom taken"],
        [("rule", "rule"), ("dev", "dev"), ("test", "test")],
        macro_pairs=[
            ("fusionBestDev", rows[0]["dev"]),
            ("fusionBestTest", rows[0]["test"]),
            ("fusionOracleDev", raw["oracle"]["dev"]),
            ("smoothSpread", fams[0]["spread"]),
        ],
        caption="One budget of 80 slots per survey, no reservation and no LeyLine quota",
    )
    bar_chart(rows, "rule", [("dev", "gold found on dev, of 419")], RESULTS / "rules.png")
    bar_chart(
        fams, "family", [("spread", "dev spread inside each family")], RESULTS / "by_family.png"
    )
    print(f"\ngold in pool: dev {raw['gold_in_pool']['dev']}, test {raw['gold_in_pool']['test']}")
    print(f"oracle at the same budget: dev {raw['oracle']['dev']}, test {raw['oracle']['test']}")
    print(f"best single signal on dev {raw['best_single_dev']}, headroom {raw['headroom_dev']}\n")
    print(f"{'rule':<34} {'family':<14} {'DEV':>5} {'TEST':>5} {'headroom':>9}")
    for r in rows:
        print(
            f"{r['rule']:<34} {r['family']:<14} {r['dev']:>5} {r['test']:>5} "
            f"{r['headroom taken']:>9}"
        )
    print("\nspread inside each family")
    for f in fams:
        print(
            f"  {f['family']:<14} {f['rules']} rules, best {f['best']}, "
            f"worst {f['worst']}, spread {f['spread']}"
        )
