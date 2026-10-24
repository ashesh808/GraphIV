"""
Reads the exported benchmarks and one worked case per benchmark for the benchmark card figures

Cached in assets/data/benchmarks.json, so a redraw needs neither the export nor the store
"""

from __future__ import annotations

import json
import statistics
import tomllib
from pathlib import Path
from typing import Any

import psycopg
import pyarrow.parquet as pq
from style import DATA, ROOT

CACHE = DATA / "benchmarks.json"
FOLDERS = ("surveymatch", "frontiermatch", "consensusmatch")
SPLITS = ("train", "val", "test")
# the worked case each construction figure draws, one per benchmark
EXAMPLES = {
    "surveymatch": "2403.14734",
    "frontiermatch": "1907.04444_1912.12033",
    "consensusmatch": "2305.19860_2306.05817_2307.02046",
}
REFERENCES = """
SELECT DISTINCT c.source_id, c.target_id, t.date::text
FROM citations c
JOIN papers s ON s.arxiv_id = c.source_id
JOIN papers t ON t.arxiv_id = c.target_id
WHERE c.source_id = ANY(%s) AND t.stage >= 3 AND t.date < s.date
"""


def summarize(root: Path, folder: str) -> dict[str, Any]:
    """
    One benchmark's split sizes, answer sizes, years and topics, plus its worked case

    Args:
        root: The benchmark release.
        folder: The benchmark's directory.

    Returns:
        The summary.
    """
    rows = [r for s in SPLITS for r in pq.read_table(root / folder / f"{s}.parquet").to_pylist()]
    example = next(r for r in rows if r["case_id"] == EXAMPLES[folder])
    return {
        "splits": {s: sum(r["split"] == s for r in rows) for s in SPLITS},
        "answer_median": statistics.median(r["n_citations"] for r in rows),
        "years": [min(r["date_max"].year for r in rows), max(r["date_max"].year for r in rows)],
        "topics": len({r["split_group"] for r in rows}),
        "leaves": len({(r["topic_l0"], r["topic_l1"], r["topic_l2"]) for r in rows}),
        "headline_k": rows[0]["headline_k"],
        "example": {
            "case_id": example["case_id"],
            "query": example["query_text"],
            "anchors": example["anchors"],
            "titles": [" ".join(t.split()) for t in example["anchor_titles"]],
            "dates": [d.isoformat() for d in example["anchor_dates"]],
            "date_max": example["date_max"].isoformat(),
            "citations": example["citations"],
        },
    }


def load(config_path: Path) -> dict[str, Any]:
    """
    The cached summaries, read from the export and the store when the cache is missing

    Args:
        config_path: The config naming the export directory, the cutoff and the store.

    Returns:
        The settings, one summary per benchmark, and each worked case's references.
    """
    if CACHE.is_file():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    cutoff = str(cfg["benchmarks"]["CUTOFF"])
    export = Path(str(cfg["export"]["EXPORT_PATH"]))
    root = (export if export.is_absolute() else ROOT / export) / f"graphiv-benchmarks-{cutoff}"
    data: dict[str, Any] = {"settings": cfg["benchmarks"]}
    dsn = str(cfg["database"]["PG_DEST"]).replace("host=.pg", f"host={ROOT / '.pg'}")
    with psycopg.connect(dsn) as conn:
        for folder in FOLDERS:
            data[folder] = summarize(root, folder)
            anchors = data[folder]["example"]["anchors"]
            refs: dict[str, dict[str, Any]] = {}
            for source, target, day in conn.execute(REFERENCES, (anchors,)).fetchall():
                refs.setdefault(str(target), {"date": day, "by": []})["by"].append(str(source))
            data[folder]["example"]["references"] = refs
    CACHE.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    return data
