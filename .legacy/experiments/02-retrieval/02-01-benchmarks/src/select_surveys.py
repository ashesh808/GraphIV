"""
Pick survey papers whose reference list is large enough to serve as an answer key

Two floors and never a ranking, since top-cited selects for age and mega-topic
Writes data/surveys.json, stratified by primary category and year
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg

from graphiv.core.settings import PG_DSN
from graphiv.core.store import id_yymm

HERE = Path(__file__).parent
MIN_REFS = 60
MIN_CITES = 20
N_PICK = 20

STEPS: list[str] = [
    "SET statement_timeout = '1800s'",
    r"""
    CREATE TEMP TABLE cand AS
    SELECT p.id, m.arxiv_id, m.title, m.abstract, m.year, m.primary_category
    FROM paper_meta m JOIN paper p ON p.arxiv_id = m.arxiv_id
    WHERE m.year BETWEEN 2022 AND 2024
      AND m.abstract IS NOT NULL
      AND m.title ~* '\m(survey|review|overview)\M'
    """,
    """
    CREATE TEMP TABLE outdeg AS
    SELECT c.id, count(DISTINCT ci.cited_id) AS n_refs
    FROM cand c JOIN citation ci ON ci.citing_id = c.id AND ci.cited_id IS NOT NULL
    GROUP BY c.id HAVING count(DISTINCT ci.cited_id) >= %(min_refs)s
    """,
    """
    CREATE TEMP TABLE indeg AS
    SELECT o.id, count(DISTINCT ci.citing_id) AS n_cites
    FROM outdeg o JOIN citation ci ON ci.cited_id = o.id
    GROUP BY o.id HAVING count(DISTINCT ci.citing_id) >= %(min_cites)s
    """,
]

FINAL = """
SELECT c.arxiv_id, c.title, c.abstract, c.year, c.primary_category, o.n_refs, i.n_cites
FROM cand c JOIN outdeg o ON o.id = c.id JOIN indeg i ON i.id = c.id
"""


def fetch() -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    Every survey clearing both floors, with its resolved reference and citation counts
    """
    args = {"min_refs": MIN_REFS, "min_cites": MIN_CITES}
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        for step in STEPS:
            _ = cur.execute(step, args)  # pyright: ignore[reportArgumentType]
        _ = cur.execute(FINAL)  # pyright: ignore[reportArgumentType]
        rows: list[tuple[Any, ...]] = cur.fetchall()  # pyright: ignore[reportExplicitAny]
    out: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    for aid, title, abstract, year, cat, n_refs, n_cites in rows:
        yymm = id_yymm(str(aid))
        if yymm == 0:
            continue
        out.append(
            {
                "arxiv_id": str(aid),
                "title": " ".join(str(title).split()),
                "abstract": " ".join(str(abstract).split()),
                "year": int(year),
                "category": str(cat),
                "n_refs": int(n_refs),
                "n_cites": int(n_cites),
                "yymm": f"{yymm % 10000:04d}",
            }
        )
    return out


def stratify(
    pool: list[dict[str, Any]], n: int, seed: int = 0
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    """
    Round-robin one survey at a time from each (archive, year) cell, shuffled inside a cell
    """
    rng = random.Random(seed)
    cells: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(
        list
    )  # pyright: ignore[reportExplicitAny]
    for s in pool:
        cells[(str(s["category"]).split(".")[0], int(s["year"]))].append(s)
    for v in cells.values():
        rng.shuffle(v)
    keys = sorted(cells, key=lambda k: (-len(cells[k]), k))
    picked: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
    while len(picked) < n and any(cells[k] for k in keys):
        for k in keys:
            if cells[k] and len(picked) < n:
                picked.append(cells[k].pop())
    return picked


if __name__ == "__main__":
    pool = fetch()
    print(f"{len(pool)} surveys clear refs>={MIN_REFS} and cites>={MIN_CITES}")
    by_arch: dict[str, int] = defaultdict(int)
    for s in pool:
        by_arch[str(s["category"]).split(".")[0]] += 1
    top = sorted(by_arch.items(), key=lambda x: -x[1])[:12]
    print("  archives: " + ", ".join(f"{k}={v}" for k, v in top))
    picked = stratify(pool, N_PICK)
    (HERE / "data").mkdir(exist_ok=True)
    _ = (HERE / "data" / "survey_pool.json").write_text(json.dumps(pool, indent=1))
    _ = (HERE / "data" / "surveys.json").write_text(json.dumps(picked, indent=1))
    print(f"\npicked {len(picked)}:")
    for s in picked:
        print(
            f"  {s['arxiv_id']}  {s['category']:<10} {s['yymm']}  "
            f"refs={s['n_refs']:<4} cites={s['n_cites']:<5} {s['title'][:68]}"
        )
