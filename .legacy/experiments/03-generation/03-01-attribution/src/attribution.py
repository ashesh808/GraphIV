"""
Are the sentences that cite a paper actually supported by it

A sentence passes when any one of the papers it cites supports it, which is the lax rule.
Two judges score the same sentences, and one of them wrote the reports, so the gap is the bias.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _harness.measure import attribution
from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)

AUTHOR = "Gemma-4-26B-Batched"
JUDGES = (AUTHOR, "Qwen3.6-35B-A3B-Batched")


def measure() -> None:
    """
    Score every report under both judges and write census.json plus agreement.json

    Verdicts are cached per report, judge, sentence and paper in cache/verdicts.db, so a second
    run costs nothing and a new report costs only its own sentences.
    """
    import json as _json

    from graphiv.core.settings import HTML_DIR

    paths = [REPO / ln for ln in (CACHE / "reports.txt").read_text().split() if ln.strip()]
    conn = attribution.open_cache(CACHE / "verdicts.db")
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    try:
        for judge in JUDGES:
            for rp in paths:
                run = _json.loads(
                    (rp.parent / "run.json").read_text()
                )  # pyright: ignore[reportAny]
                got = attribution.census(rp, judge, conn, HTML_DIR)
                rows.append(
                    {
                        "report": rp.parent.parent.name,
                        "judge": judge,
                        "mode": "survey" if run["rank"] == "joint" else "frontier",
                        "landmarks": run["n_landmarks"],
                        **got,
                    }
                )
                print(f"  {rp.parent.parent.name[:44]:44} [{judge[:6]}] {got}")
        agree = _agreement(paths, conn)
    finally:
        conn.close()
    _ = (CACHE / "census.json").write_text(_json.dumps(rows, indent=2), encoding="utf-8")
    _ = (CACHE / "agreement.json").write_text(_json.dumps(agree, indent=2), encoding="utf-8")


def _agreement(
    paths: list[Path], conn: Any
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    """
    How often the two judges reach the same verdict on the same sentence

    Args:
        paths: The report paths.
        conn: The verdict cache.

    Returns:
        The cross-tabulation, the raw agreement and Cohen's kappa.
    """
    import collections

    pair: collections.Counter[tuple[str, str]] = collections.Counter()
    for rp in paths:
        name = f"{rp.parent.parent.name}/{rp.parent.name}"
        rows, _ = attribution.sentences(rp.read_text())
        for sent, ids in rows:
            if not ids:
                continue
            seen: list[list[str]] = []
            for j in JUDGES:
                vs = [
                    r[0]
                    for aid in ids
                    if (
                        r := conn.execute(
                            "SELECT verdict FROM v WHERE key=?",
                            (attribution.key(name, j, "support", sent, aid),),
                        ).fetchone()
                    )
                ]
                seen.append(vs)
            if not all(seen):
                continue
            pair[
                tuple("yes" if "yes" in v else "no" for v in seen)
            ] += 1  # pyright: ignore[reportArgumentType]
    n = max(1, sum(pair.values()))
    ag = pair[("yes", "yes")] + pair[("no", "no")]
    a = sum(v for (x, _y), v in pair.items() if x == "yes") / n
    b = sum(v for (_x, y), v in pair.items() if y == "yes") / n
    exp = a * b + (1 - a) * (1 - b)
    return {
        "sentences": n,
        "both_supported": pair[("yes", "yes")],
        "both_rejected": pair[("no", "no")],
        "gemma_only": pair[("yes", "no")],
        "qwen_only": pair[("no", "yes")],
        "agreement": round(ag / n, 3),
        "kappa": round((ag / n - exp) / (1 - exp), 3),
    }


def _fold(rows: list[dict[str, Any]]) -> dict[str, int]:  # pyright: ignore[reportExplicitAny]
    keys = ("sentences", "cited", "uncited", "cited_yes", "cited_partial", "cited_no")
    return {k: sum(int(r.get(k, 0)) for r in rows) for k in keys}


def _row(
    label: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    t = _fold(rows)
    judged = t["cited_yes"] + t["cited_partial"] + t["cited_no"]
    return {
        "arm": label,
        "reports": len(rows),
        "sentences": t["sentences"],
        "cite a paper": t["cited"],
        "supported": t["cited_yes"],
        "support rate": round(t["cited_yes"] / max(1, judged), 3),
        "partial": t["cited_partial"],
        "not supported": t["cited_no"],
        "lenient rate": round((t["cited_yes"] + t["cited_partial"]) / max(1, judged), 3),
    }


def tables_for(
    raw: list[dict[str, Any]],
) -> tuple[  # pyright: ignore[reportExplicitAny]
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],  # pyright: ignore[reportExplicitAny]
]:
    """
    One row per judge, one per retrieval mode under the independent judge, and the bucket split
    """
    judges = sorted({str(r["judge"]) for r in raw})
    by_judge = [_row(j, [r for r in raw if r["judge"] == j]) for j in judges]
    other = next((j for j in judges if j != AUTHOR), judges[0])
    indep = [r for r in raw if r["judge"] == other]
    by_mode = [
        _row(m, [r for r in indep if r["mode"] == m])
        for m in ("survey", "frontier")
        if any(r["mode"] == m for r in indep)
    ]
    agree: dict[str, Any] = json.loads(  # pyright: ignore[reportExplicitAny,reportAny]
        (CACHE / "agreement.json").read_text(encoding="utf-8")
    )
    cross = [
        {"both judges say": k.replace("_", " "), "sentences": agree[k]}
        for k in ("both_supported", "both_rejected", "gemma_only", "qwen_only")
    ]
    return by_judge, by_mode, cross


def run() -> None:
    """
    Print the census and write the results, tables and figure
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not (CACHE / "census.json").exists():
        measure()
    raw = read_json(CACHE / "census.json")
    by_judge, by_mode, cross = tables_for(raw)
    agree: dict[str, Any] = json.loads(  # pyright: ignore[reportExplicitAny,reportAny]
        (CACHE / "agreement.json").read_text(encoding="utf-8")
    )
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps(
            {"by_judge": by_judge, "by_mode": by_mode, "agreement": agree, "cross": cross},
            indent=2,
        ),
        encoding="utf-8",
    )
    indep = next((r for r in by_judge if r["arm"] != AUTHOR), by_judge[0])
    cols = [
        "arm",
        "reports",
        "sentences",
        "cite a paper",
        "supported",
        "support rate",
        "partial",
        "not supported",
        "lenient rate",
    ]
    tables.write(
        RESULTS,
        by_judge + by_mode,
        cols,
        [
            ("arm", "Arm"),
            ("sentences", "Sentences"),
            ("supported", "Supported"),
            ("support rate", "Support"),
            ("not supported", "Rejected"),
            ("lenient rate", "Lenient"),
        ],
        macro_pairs=[
            ("censusSupport", indep["support rate"]),
            ("censusLenient", indep["lenient rate"]),
            ("censusAgreement", agree["agreement"]),
            ("censusKappa", agree["kappa"]),
        ],
        caption="A cited sentence passes when any one of its papers supports it",
    )
    _ = (RESULTS / "agreement.md").write_text(
        tables.metrics_md(
            cross, list(cross[0].keys()), f"kappa {agree['kappa']} over {agree['sentences']}"
        ),
        encoding="utf-8",
    )
    bar_chart(
        by_judge + by_mode,
        "arm",
        [("support rate", "cited sentences supported"), ("lenient rate", "counting partial")],
        RESULTS / "census.png",
        title="Cited sentences supported by the paper they cite",
    )
    print(tables.metrics_md(by_judge + by_mode, cols))
    print(tables.metrics_md(cross, list(cross[0].keys())))
