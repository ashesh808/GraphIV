"""
Whether the checker used in 03-01 can say no when a citation is wrong

One citation per citing sentence is swapped for the most similar paper the same report cites.
That is the hard case, since a paper drawn from elsewhere would be caught on vocabulary alone.
"""

from __future__ import annotations

import json
from typing import Any

from _harness.measure import attribution
from _harness.report import tables
from _harness.report.paths import experiment, read_json
from _harness.report.viz import bar_chart

CACHE, RESULTS, REPO = experiment(__file__)


JUDGES = ("Gemma-4-26B-Batched", "Qwen3.6-35B-A3B-Batched")


def _nearest(aid: str, ids: list[str], vecs: dict[str, list[float]]) -> str | None:
    """
    The cited paper most similar to this one, which is the hardest swap a report allows
    """
    v = vecs.get(aid)
    others = [i for i in ids if i != aid and i in vecs]
    if v is None or not others:
        return None
    return max(others, key=lambda o: sum(x * y for x, y in zip(v, vecs[o], strict=True)))


def measure() -> None:
    """
    Swap one citation per sentence for the nearest cited paper, then score the result

    The judges are the same two 03-01 uses, and the verdicts share that cache under a separate
    task name, so a broken citation is never confused with a real one.
    """
    from graphiv.core.settings import HTML_DIR, PG_DSN
    from graphiv.core.store import Store

    paths = [REPO / ln for ln in (CACHE / "reports.txt").read_text().split() if ln.strip()]
    conn = attribution.open_cache(CACHE / "verdicts.db")
    out: dict[str, dict[str, int]] = {
        j: {"caught": 0, "missed": 0, "partial": 0, "skip": 0} for j in JUDGES
    }
    try:
        for rp in paths:
            name = f"{rp.parent.parent.name}/{rp.parent.name}"
            rows, _ = attribution.sentences(rp.read_text())
            cited = [(s, ids) for s, ids in rows if ids]
            ids_all = sorted({a for _, ids in cited for a in ids})
            store = Store(PG_DSN)
            try:
                vecs = store.embeddings(ids_all)
            finally:
                store.close()
            work = [
                (s, swap)
                for s, ids in cited
                if (swap := _nearest(ids[0], ids_all, vecs)) is not None
            ]
            cache: dict[str, list[str]] = {}
            for j in JUDGES:
                for sent, aid in work:
                    v = attribution.cached_ask(conn, name, j, "planted", sent, aid, HTML_DIR, cache)
                    out[j]["caught" if v == "no" else "missed" if v == "yes" else v] += 1
            conn.commit()
            print(f"  {rp.parent.parent.name[:44]:44} broken={len(work)}")
    finally:
        conn.close()
    for j in JUDGES:
        out[j]["total"] = sum(out[j].values())
    _ = (CACHE / "planted.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


def table() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    One row per judge, over the same broken citations
    """
    raw = read_json(CACHE / "planted.json")
    rows: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for judge, t in raw.items():
        total = int(t["total"])
        rows.append(
            {
                "judge": judge,
                "broken citations": total,
                "caught": int(t["caught"]),
                "called partial": int(t["partial"]),
                "missed": int(t["missed"]),
                "skipped": int(t.get("skip", 0)),
                "catch rate": round(int(t["caught"]) / max(1, total), 3),
            }
        )
    rows.sort(key=lambda r: str(r["judge"]))
    return rows


def run() -> None:
    """
    Print the catch rates and write the results, tables and figure
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not (CACHE / "planted.json").exists():
        measure()
    rows = table()
    _ = (RESULTS / "metrics.json").write_text(
        json.dumps({"judges": rows}, indent=2), encoding="utf-8"
    )
    tables.write(
        RESULTS,
        rows,
        [
            "judge",
            "broken citations",
            "caught",
            "called partial",
            "missed",
            "skipped",
            "catch rate",
        ],
        [
            ("judge", "Judge"),
            ("broken citations", "Broken"),
            ("caught", "Caught"),
            ("catch rate", "Catch rate"),
        ],
        macro_pairs=[("checkerCatch", rows[0]["catch rate"])],
        caption="The swap is the most similar paper the same report cites",
    )
    bar_chart(
        rows,
        "judge",
        [("catch rate", "broken citations caught"), ("caught", "count caught")],
        RESULTS / "checker.png",
        title="Does the checker notice a citation we broke",
    )
    print(tables.metrics_md(rows, list(rows[0].keys())))
