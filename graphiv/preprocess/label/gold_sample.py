"""
Build the human labeling queue: a class-stratified draw of unlabeled citation occurrences

Strata are the student's predicted intent, so the rare classes arrive in measurable numbers
The queue is shuffled, so a run of one class never tells the labeler what to expect
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import LiteralString, cast

import psycopg

from ._common import ARXIVKG_PG_DSN, INTENTS, LABELS_DIR

GOLD_ITEMS: Path = LABELS_DIR / "gold_items.jsonl"

# a citation this short carries no signal, and one this long is a run-on parse
MIN_CHARS: int = 40
MAX_CHARS: int = 600

# the fraction of the citation table the stratified draw reads
SAMPLE_PERCENT: float = 2.0

QUERY: LiteralString = """
SELECT citing_id, ordinal, section, sentence, cited_title
FROM (
    SELECT c.citing_id,
           c.ordinal,
           COALESCE(c.section, '') AS section,
           c.sentence,
           COALESCE(m.title, '(unresolved)') AS cited_title,
           row_number() OVER (PARTITION BY c.intent ORDER BY random()) AS rn
    FROM citation c TABLESAMPLE SYSTEM (%s) REPEATABLE (%s)
    JOIN paper p ON p.id = c.cited_id
    LEFT JOIN paper_meta m ON m.arxiv_id = p.arxiv_id
    WHERE c.intent IS NOT NULL
      AND c.sentence IS NOT NULL
      AND length(c.sentence) BETWEEN %s AND %s
      AND NOT EXISTS (
          SELECT 1 FROM gold_label g
          WHERE g.citing_id = c.citing_id AND g.ordinal = c.ordinal
      )
) t
WHERE rn <= %s
"""


def build(total: int = 1002, seed: float = 0.42, out: Path = GOLD_ITEMS) -> Path:
    """
    Draw an equal share of every predicted intent, shuffled, and write the labeling queue
    """
    per_class = max(1, total // len(INTENTS))
    with psycopg.connect(ARXIVKG_PG_DSN) as conn:
        _ = conn.execute("SELECT setseed(%s)", (seed,))
        rows = cast(
            list[tuple[int, int, str, str, str]],
            conn.execute(
                QUERY, (SAMPLE_PERCENT, seed * 100, MIN_CHARS, MAX_CHARS, per_class)
            ).fetchall(),
        )
    # the draw comes back grouped by class, which would telegraph the answer
    random.Random(seed).shuffle(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for citing_id, ordinal, section, sentence, cited_title in rows:
            item = {
                "citing_id": citing_id,
                "ordinal": ordinal,
                "context": sentence,
                "section": section or "(unknown)",
                "cited": cited_title[:160],
            }
            _ = f.write(json.dumps(item) + "\n")
    print(f"[gold] {len(rows)} items ({per_class} per intent) -> {out}", flush=True)
    return out


def main() -> None:
    """
    Build the queue from the command line
    """
    ap = argparse.ArgumentParser(description="build the human labeling queue")
    _ = ap.add_argument("--total", type=int, default=1002)
    _ = ap.add_argument("--seed", type=float, default=0.42)
    _ = ap.add_argument("--out", type=Path, default=GOLD_ITEMS)
    ns = ap.parse_args()
    _ = build(
        total=int(ns.total),  # pyright: ignore[reportAny]
        seed=float(ns.seed),  # pyright: ignore[reportAny]
        out=Path(str(ns.out)),  # pyright: ignore[reportAny]
    )


if __name__ == "__main__":
    main()
