"""
Oversample the rare intent classes for a label refresh

The relational classes are thin next to background and uses, which biases the student
"""

from __future__ import annotations

import argparse
import random
import time
from collections import defaultdict
from typing import cast

import psycopg

from ._common import ARXIVKG_PG_DSN, LABELS_DIR

RARE = ("critiques", "extends", "compares", "motivates")
# strong relational cues that v1 may have buried under background/uses
KW = (
    "however|unlike|in contrast|contrary to|limitation|drawback|shortcoming|"
    "fails? to|cannot|suffers? from|outperforms?|worse than|better than|"
    "extends?|extended|builds? upon|building upon|improves? upon|generaliz|"
    "inspired by|motivated by"
)


def _reservoir(rows: object, per_class: int, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    res: dict[str, list[tuple[int, int]]] = defaultdict(list)
    seen: dict[str, int] = defaultdict(int)
    for row in cast("list[tuple[int, int, str]]", rows):
        cid, ordi, k = int(row[0]), int(row[1]), str(row[2])
        seen[k] += 1
        r = res[k]
        if len(r) < per_class:
            r.append((cid, ordi))
        else:
            j = rng.randint(0, seen[k] - 1)
            if j < per_class:
                r[j] = (cid, ordi)
    for k in sorted(res):
        print(f"    {k:>12s}: seen={seen[k]:>8,} kept={len(res[k]):>6,}", flush=True)
    return [p for v in res.values() for p in v]


def main() -> None:
    """
    Parse the arguments and write the rare-class batch
    """
    parser = argparse.ArgumentParser(description="rare-class oversampler")
    _ = parser.add_argument("--per-class", type=int, default=6000)
    _ = parser.add_argument("--seed", type=int, default=7)
    _ = parser.add_argument("--out", type=str, default=str(LABELS_DIR / "sample_rare.txt"))
    args = parser.parse_args()
    per_class: int = args.per_class  # pyright: ignore[reportAny]
    seed: int = args.seed  # pyright: ignore[reportAny]
    out: str = args.out  # pyright: ignore[reportAny]

    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    conn = psycopg.connect(ARXIVKG_PG_DSN)

    print("[1/2] reservoir over v1 rare-class predictions ...", flush=True)
    t0 = time.time()
    with conn.cursor(name="rare") as cur:
        cur.itersize = 100_000
        _ = cur.execute(
            "SELECT citing_id, ordinal, intent FROM citation "
            "WHERE intent = ANY(%s) AND sentence IS NOT NULL "
            "AND length(sentence) BETWEEN 60 AND 600",
            (list(RARE),),
        )
        precision_pairs = _reservoir(cur, per_class, seed)
    print(
        f"    precision set: {len(precision_pairs):,} in {time.time() - t0:.0f}s",
        flush=True,
    )

    print("[2/2] keyword-recall scan over background/uses (TABLESAMPLE) ...", flush=True)
    t0 = time.time()
    with conn.cursor(name="kw") as cur:
        cur.itersize = 50_000
        _ = cur.execute(
            "SELECT citing_id, ordinal, 'kw_miss' AS k FROM citation "
            "TABLESAMPLE SYSTEM (4) "
            "WHERE intent IN ('background','uses') AND sentence IS NOT NULL "
            "AND length(sentence) BETWEEN 60 AND 600 AND sentence ~* %s",
            (KW,),
        )
        recall_pairs = _reservoir(cur, per_class * 2, seed + 1)
    print(f"    recall set: {len(recall_pairs):,} in {time.time() - t0:.0f}s", flush=True)
    conn.close()

    pairs = precision_pairs + recall_pairs
    rng = random.Random(seed + 2)
    rng.shuffle(pairs)
    # de-dup (a pair can't appear in both sets, but be safe)
    seen_pairs: set[tuple[int, int]] = set()
    uniq = [p for p in pairs if not (p in seen_pairs or seen_pairs.add(p))]

    with open(out, "w", encoding="utf-8") as f:
        _ = f.write("# citing_id\tordinal\n")
        _ = f.write(f"# rare-class refresh seed={seed} per_class={per_class} n={len(uniq)}\n")
        for cid, ordi in uniq:
            _ = f.write(f"{cid}\t{ordi}\n")
    print(f"\n  wrote {len(uniq):,} pairs -> {out}", flush=True)


if __name__ == "__main__":
    main()
