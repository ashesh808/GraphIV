"""
Stratified seed-deterministic sampler over the corpus, for the teacher run

Strata are (citing category, section bucket), reservoir-filled and then padded to the target
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import time
from collections import defaultdict
from typing import cast

import psycopg

from ._common import (
    ARXIV_SQLITE,
    ARXIVKG_PG_DSN,
    LABELS_DIR,
    SAMPLE_TXT,
    section_bucket,
)

"""
Categories we explicitly stratify across
Citations from papers tagged in other arxiv categories collapse into a single "other" bucket
The list is the top categories by paper count + a few thematically distinct fields
"""
TARGET_CATEGORIES: tuple[str, ...] = (
    "cs",
    "math",
    "stat",
    "eess",
    "physics",
    "cond-mat",
    "astro-ph",
    "hep-th",
    "hep-ph",
    "gr-qc",
    "quant-ph",
    "math-ph",
    "q-bio",
    "q-fin",
    "econ",
)


def load_category_map() -> dict[str, str]:
    """
    Return arxiv_id -> primary category (first categories row per paper)

        Legacy arxiv ids like 'hep-th/9201001' have no row in the categories
        table; we infer their category from the id prefix.
    """
    t0 = time.time()
    conn = sqlite3.connect(f"file:{ARXIV_SQLITE}?mode=ro", uri=True)
    rows: list[tuple[str, str]] = cast(
        list[tuple[str, str]],
        conn.execute("SELECT publication_id, category FROM categories").fetchall(),
    )
    conn.close()
    mapping: dict[str, str] = {}
    for pub_id, cat in rows:
        if pub_id not in mapping:
            mapping[pub_id] = cat
    print(f"  category rows: {len(rows):,}, distinct papers: {len(mapping):,}", flush=True)
    print(f"  load_category_map: {time.time() - t0:.1f}s", flush=True)
    return mapping


def stratum_category(cat: str | None) -> str:
    """
    Collapse a category into its sampling stratum
    """
    if cat is None:
        return "other"
    return cat if cat in TARGET_CATEGORIES else "other"


def build_paper_to_category(
    conn: psycopg.Connection[tuple[object, ...]],
    arxiv_cat: dict[str, str],
) -> dict[int, str]:
    """
    Map paper.id -> stratum_category using the PG paper dim table
    """
    t0 = time.time()
    cur = conn.cursor()
    _ = cur.execute("SELECT id, arxiv_id FROM paper")
    out: dict[int, str] = {}
    while True:
        chunk: list[tuple[int, str]] = cast(list[tuple[int, str]], cur.fetchmany(50000))
        if not chunk:
            break
        for pid, aid in chunk:
            cat: str | None = arxiv_cat.get(aid)
            if cat is None and "/" in aid:
                cat = aid.split("/", 1)[0]
            out[pid] = stratum_category(cat)
    print(
        f"  build_paper_to_category: {len(out):,} papers in {time.time() - t0:.1f}s",
        flush=True,
    )
    return out


def reservoir_add(
    reservoirs: dict[tuple[str, str], list[tuple[int, int]]],
    counters: dict[tuple[str, str], int],
    rng: random.Random,
    k: int,
    key: tuple[str, str],
    pair: tuple[int, int],
) -> None:
    """
    Algorithm R reservoir sampling for one stratum
    """
    counters[key] += 1
    res = reservoirs[key]
    if len(res) < k:
        res.append(pair)
        return
    j = rng.randint(0, counters[key] - 1)
    if j < k:
        res[j] = pair


def stream_and_sample(seed: int, per_stratum: int) -> tuple[
    dict[tuple[str, str], list[tuple[int, int]]],
    dict[tuple[str, str], int],
]:
    """
    Return (reservoirs, seen_counts) after one pass over the citation table
    """
    conn = psycopg.connect(ARXIVKG_PG_DSN)
    arxiv_cat = load_category_map()
    pid_to_cat = build_paper_to_category(conn, arxiv_cat)

    rng = random.Random(seed)
    reservoirs: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    counters: dict[tuple[str, str], int] = defaultdict(int)

    print("  streaming citation table ...", flush=True)
    t0 = time.time()
    # server-side cursor: don't materialize 68M rows in memory
    with conn.cursor(name="cit_stream") as cur:
        cur.itersize = 100_000
        _ = cur.execute(
            "SELECT citing_id, ordinal, section "
            "FROM citation "
            "WHERE cited_id IS NOT NULL "
            "  AND sentence IS NOT NULL "
            "  AND length(sentence) BETWEEN 60 AND 600"
        )
        n_streamed = 0
        for row in cur:
            citing_id_raw, ordinal_raw, section_raw = cast(tuple[int, int, str | None], row)
            citing_id = int(citing_id_raw)
            ordinal = int(ordinal_raw)
            cat = pid_to_cat.get(citing_id, "other")
            bucket = section_bucket(section_raw)
            reservoir_add(
                reservoirs,
                counters,
                rng,
                per_stratum,
                (cat, bucket),
                (citing_id, ordinal),
            )
            n_streamed += 1
            if n_streamed % 5_000_000 == 0:
                print(
                    f"    streamed {n_streamed:,} rows in {time.time() - t0:.0f}s ; "
                    f"strata filled: {sum(1 for v in reservoirs.values() if len(v) >= per_stratum)}",
                    flush=True,
                )
    conn.close()
    print(f"  total streamed: {n_streamed:,} in {time.time() - t0:.0f}s", flush=True)
    print(f"  unique strata seen: {len(reservoirs)}", flush=True)
    return reservoirs, counters


def main() -> None:
    """
    Parse the sampler arguments and write sample.txt
    """
    parser = argparse.ArgumentParser(description="Stratified citation sampler")
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--target", type=int, default=100_000, help="Target number of samples (approx)"
    )
    _ = parser.add_argument(
        "--seed", type=int, default=42
    )  # pyright: ignore[reportUnusedCallResult]
    _ = parser.add_argument(  # pyright: ignore[reportUnusedCallResult]
        "--out",
        type=str,
        default=str(SAMPLE_TXT),
        help="Output path for the (citing_id, ordinal) list",
    )
    args = parser.parse_args()
    target_n: int = args.target  # pyright: ignore[reportAny]
    seed: int = args.seed  # pyright: ignore[reportAny]
    out_path_str: str = args.out  # pyright: ignore[reportAny]

    """
    Sixteen categories against six section buckets gives ninety-six strata
    Each is over-sampled a little, which leaves headroom for the thin ones
    """
    n_strata = (len(TARGET_CATEGORIES) + 1) * 6
    per_stratum = max(1, int(target_n * 1.3 / n_strata))
    print(
        f"sampler: target={target_n} seed={seed} per_stratum={per_stratum} strata={n_strata}",
        flush=True,
    )

    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    reservoirs, _ = stream_and_sample(seed, per_stratum)

    """
    Each stratum contributes the smaller of its reservoir and its share
    Whatever a thin stratum cannot supply is redistributed to the well-populated ones
    """
    pairs: list[tuple[int, int]] = []
    strata_summary: list[tuple[str, str, int, int]] = []  # (cat, bucket, available, taken)
    base_share = target_n // n_strata
    # first pass: take base_share from each
    leftover_strata: list[tuple[str, str]] = []
    for key, res in reservoirs.items():
        take = min(base_share, len(res))
        pairs.extend(res[:take])
        strata_summary.append((key[0], key[1], len(res), take))
        if len(res) > take:
            leftover_strata.append(key)
    # second pass: fill remaining from largest-residual strata
    rng = random.Random(seed + 1)
    rng.shuffle(leftover_strata)
    deficit = max(0, target_n - len(pairs))
    for key in leftover_strata:
        if deficit == 0:
            break
        res = reservoirs[key]
        already = base_share
        avail = len(res) - already
        take_extra = min(avail, deficit)
        pairs.extend(res[already : already + take_extra])
        # update summary in place
        for i, (c, b, av, tk) in enumerate(strata_summary):
            if (c, b) == key:
                strata_summary[i] = (c, b, av, tk + take_extra)
                break
        deficit -= take_extra

    # final shuffle so output isn't grouped by stratum
    rng_final = random.Random(seed + 2)
    rng_final.shuffle(pairs)

    print(f"\n  selected {len(pairs):,} pairs (target {target_n})\n", flush=True)
    print("  per-stratum allocation:")
    strata_summary.sort(key=lambda x: (x[0], x[1]))
    for cat, bucket, avail, taken in strata_summary:
        print(
            f"    {cat:>10s} / {bucket:>10s}   avail={avail:>5d}   taken={taken:>5d}",
            flush=True,
        )

    # write sample.txt: tab-separated (citing_id\tordinal)
    out_path_str_final = out_path_str
    with open(out_path_str_final, "w", encoding="utf-8") as f:
        _ = f.write("# citing_id\tordinal\n")
        _ = f.write(f"# seed={seed} target={target_n} actual={len(pairs)}\n")
        for cid, ord_ in pairs:
            _ = f.write(f"{cid}\t{ord_}\n")
    print(f"\n  wrote {out_path_str_final}", flush=True)


if __name__ == "__main__":
    main()
