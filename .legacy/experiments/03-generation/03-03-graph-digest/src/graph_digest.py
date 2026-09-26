"""
Whether the citation graph in the prompt changes how well a report is sourced

Only the adjacency digest is withheld, so the pool and the budget match and the edges drop to 0
Both 03-01 and 03-02 are re-run on the no-graph reports under the same two judges
"""

from __future__ import annotations

import json
from typing import Any

from _harness.measure import attribution
from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)

ARMS = ("graph", "no graph")


JUDGES = ("Gemma-4-26B-Batched", "Qwen3.6-35B-A3B-Batched")


def measure() -> None:
    """
    Fold 03-01's census and 03-02's control into one row per report, judge and digest

    Both are read from this experiment's own verdict cache, so a report already scored elsewhere
    costs nothing and a fresh one pays only for its own sentences.
    """
    from graphiv.core.settings import HTML_DIR

    paths = [REPO / ln for ln in (CACHE / "reports.txt").read_text().split() if ln.strip()]
    conn = attribution.open_cache(CACHE / "verdicts.db")
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    try:
        for rp in paths:
            name = f"{rp.parent.parent.name}/{rp.parent.name}"
            run = json.loads((rp.parent / "run.json").read_text())  # pyright: ignore[reportAny]
            arm = "graph" if run["n_edges"] > 0 else "no graph"
            for j in JUDGES:
                got = attribution.census(rp, j, conn, HTML_DIR)
                pl = {"caught": 0, "total": 0}
                for (v,) in conn.execute(
                    "SELECT verdict FROM v WHERE report=? AND judge=? AND task='planted'",
                    (name, j),
                ):
                    pl["total"] += 1
                    pl["caught"] += v == "no"
                rows.append(
                    {
                        "report": rp.parent.parent.name,
                        "judge": j,
                        "arm": arm,
                        "planted_total": pl["total"],
                        "planted_caught": pl["caught"],
                        **got,
                    }
                )
    finally:
        conn.close()
    _ = (CACHE / "graph_digest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _fold(
    rows: list[dict[str, Any]], arm: str
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    got = [r for r in rows if r["arm"] == arm]
    """
    Sentence counts are per report, so they are read once; verdicts are per judge and summed
    """
    seen: dict[str, dict[str, Any]] = {str(r["report"]): r for r in got}
    sent = sum(int(r["sentences"]) for r in seen.values())
    cited = sum(int(r["cited"]) for r in seen.values())
    yes = sum(int(r["cited_yes"]) for r in got)
    judged = yes + sum(int(r["cited_partial"]) + int(r["cited_no"]) for r in got)
    broken = sum(int(r.get("planted_total", 0)) for r in got)
    caught = sum(int(r.get("planted_caught", 0)) for r in got)
    return {
        "digest": arm,
        "reports": len(seen),
        "sentences": sent,
        "carry a citation": cited,
        "coverage": round(cited / max(1, sent), 3),
        "judgings": len(got),
        "supported": yes,
        "support rate": round(yes / max(1, judged), 3),
        "broken caught": caught,
        "catch rate": round(caught / max(1, broken), 3) if broken else 0.0,
    }


def table() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    One row per digest, folded over the five questions and both judges
    """
    raw = read_json(CACHE / "graph_digest.json")
    return [_fold(raw, a) for a in ARMS]


def run() -> None:
    """
    Print the digest comparison and write the results, tables and figure
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not (CACHE / "graph_digest.json").exists():
        measure()
    rows = table()
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"arms": rows}, indent=2), encoding="utf-8"
    )
    cols = [
        "digest",
        "reports",
        "sentences",
        "carry a citation",
        "coverage",
        "judgings",
        "supported",
        "support rate",
        "broken caught",
        "catch rate",
    ]
    tables.write(
        RESULTS,
        rows,
        cols,
        [
            ("digest", "Digest"),
            ("coverage", "Coverage"),
            ("support rate", "Support"),
            ("catch rate", "Catch"),
        ],
        macro_pairs=[
            ("digestGraphSupport", rows[0]["support rate"]),
            ("digestNoGraphSupport", rows[-1]["support rate"]),
            ("digestGraphCoverage", rows[0]["coverage"]),
            ("digestNoGraphCoverage", rows[-1]["coverage"]),
        ],
        caption="Same questions, same pool, same budget; only the adjacency digest moves",
    )
    bar_chart(
        rows,
        "digest",
        [
            ("support rate", "cited sentences supported"),
            ("coverage", "sentences carrying a citation"),
        ],
        RESULTS / "graph_digest.png",
        title="Reliability with and without the citation graph",
    )
    print(tables.metrics_md(rows, cols))
