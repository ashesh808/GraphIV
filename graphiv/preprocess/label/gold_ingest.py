"""
Load the human labeling queue into gold_label, accepting the student hint where no human ruled

A hand label always wins over the hint, and the labeler column records which of the two it was
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, LiteralString, cast

import psycopg

from ._common import ARXIVKG_PG_DSN, INTENTS, LABELS_DIR

GOLD_ITEMS: Path = LABELS_DIR / "gold_items.jsonl"
GOLD_LABELS: Path = LABELS_DIR / "gold_labels.jsonl"

HINT_SQL: LiteralString = (
    "SELECT c.citing_id, c.ordinal, c.intent FROM citation c "
    "JOIN (VALUES {values}) AS v(cid, ord) ON c.citing_id = v.cid AND c.ordinal = v.ord "
    "WHERE c.intent IS NOT NULL"
)

UPSERT_SQL: LiteralString = (
    "INSERT INTO gold_label (citing_id, ordinal, intent, labeler) VALUES (%s, %s, %s, %s) "
    "ON CONFLICT (citing_id, ordinal) DO UPDATE SET intent = EXCLUDED.intent, "
    "labeler = EXCLUDED.labeler, labeled_at = now()"
)


def read_queue(path: Path) -> list[tuple[int, int]]:
    """
    The (citing_id, ordinal) pairs the labeler was shown, in queue order
    """
    out: list[tuple[int, int]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = cast(dict[str, Any], json.loads(line))  # pyright: ignore[reportExplicitAny]
            out.append((int(row["citing_id"]), int(row["ordinal"])))  # pyright: ignore[reportAny]
    return out


def read_human(path: Path) -> dict[tuple[int, int], str]:
    """
    Every hand label that named an intent, keyed by occurrence
    """
    out: dict[tuple[int, int], str] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = cast(dict[str, Any], json.loads(line))  # pyright: ignore[reportExplicitAny]
            labels = cast(
                dict[str, Any], row.get("labels", {})
            )  # pyright: ignore[reportExplicitAny]
            intent = labels.get("intent")  # pyright: ignore[reportAny]
            if "citing_id" not in row or "_skipped" in labels or intent not in INTENTS:
                continue
            out[(int(row["citing_id"]), int(row["ordinal"]))] = str(
                intent
            )  # pyright: ignore[reportAny]
    return out


def read_hints(pairs: list[tuple[int, int]]) -> dict[tuple[int, int], str]:
    """
    The shipped student's label for each queued occurrence, which is the hint the labeler saw
    """
    out: dict[tuple[int, int], str] = {}
    with psycopg.connect(ARXIVKG_PG_DSN) as conn:
        for start in range(0, len(pairs), 5000):
            chunk = pairs[start : start + 5000]
            values = ",".join("(%s,%s)" for _ in chunk)
            params = [v for pair in chunk for v in pair]
            rows = cast(
                list[tuple[int, int, str]],
                conn.execute(
                    cast(LiteralString, HINT_SQL.format(values=values)), params
                ).fetchall(),
            )
            for cid, ordn, intent in rows:
                out[(cid, ordn)] = intent
    return out


def ingest(queue: Path = GOLD_ITEMS, labels: Path = GOLD_LABELS) -> int:
    """
    Write one gold_label row per queued occurrence and report how far the hints were trusted
    """
    pairs = read_queue(queue)
    human = read_human(labels)
    hints = read_hints(pairs)
    rows: list[tuple[int, int, str, str]] = []
    agree = 0
    for pair in pairs:
        by_hand = human.get(pair)
        hint = hints.get(pair)
        if by_hand is not None:
            agree += int(by_hand == hint)
            rows.append((pair[0], pair[1], by_hand, "human"))
        elif hint is not None:
            rows.append((pair[0], pair[1], hint, "accepted"))
    with psycopg.connect(ARXIVKG_PG_DSN) as conn:
        _ = conn.cursor().executemany(UPSERT_SQL, rows)
        conn.commit()
    n_human = len(human)
    print(
        f"[gold] {len(rows)} rows: {n_human} by hand, {len(rows) - n_human} accepted hints",
        flush=True,
    )
    if n_human:
        print(f"[gold] hand labels agreeing with the hint: {agree}/{n_human}", flush=True)
    return len(rows)


def main() -> None:
    """
    Ingest the queue from the command line
    """
    ap = argparse.ArgumentParser(description="load the labeling queue into gold_label")
    _ = ap.add_argument("--queue", type=Path, default=GOLD_ITEMS)
    _ = ap.add_argument("--labels", type=Path, default=GOLD_LABELS)
    ns = ap.parse_args()
    _ = ingest(
        queue=Path(str(ns.queue)),  # pyright: ignore[reportAny]
        labels=Path(str(ns.labels)),  # pyright: ignore[reportAny]
    )


if __name__ == "__main__":
    main()
