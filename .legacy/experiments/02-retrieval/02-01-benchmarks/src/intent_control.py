"""
Control for the survey intent profile: do non-survey papers show the same background gradient

Matched on resolved reference count and year, so only the survey-ness differs
A gradient that survives here is a classifier artifact and not a property of surveys
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import psycopg

from graphiv.core.settings import PG_DSN
from graphiv.core.store import id_yymm

HERE = Path(__file__).parent
CLASSES = ["background", "uses", "compares", "extends", "motivates", "critiques"]
N_CONTROL = 40

PICK_CONTROL = r"""
    SELECT m.arxiv_id, m.title, m.primary_category, n.n_refs
    FROM (
        SELECT c.citing_id AS id, count(DISTINCT c.cited_id) AS n_refs
        FROM citation c
        WHERE c.citing_id IN (
            SELECT p.id FROM paper_meta m2 JOIN paper p ON p.arxiv_id = m2.arxiv_id
            WHERE m2.year BETWEEN 2022 AND 2024
              AND m2.title !~* '\m(survey|review|overview)\M'
              AND m2.primary_category = ANY(%(cats)s)
            ORDER BY p.id LIMIT %(scan)s
        ) AND c.cited_id IS NOT NULL
        GROUP BY c.citing_id
        HAVING count(DISTINCT c.cited_id) >= 60
    ) n JOIN paper p2 ON p2.id = n.id JOIN paper_meta m ON m.arxiv_id = p2.arxiv_id
    LIMIT %(lim)s
"""


def profile(
    cur: psycopg.Cursor[tuple[Any, ...]], arxiv_id: str
) -> tuple[Counter[str], dict[str, Counter[str]]]:  # pyright: ignore[reportExplicitAny]
    """
    Paper-level intent counts and the intent-by-mention-bucket cross-tab for one citing paper
    """
    _ = cur.execute(
        """
        SELECT c.cited_id, c.intent FROM paper ps
        JOIN citation c ON c.citing_id = ps.id AND c.cited_id IS NOT NULL
        WHERE ps.arxiv_id = %s
        """,
        (arxiv_id,),
    )
    rows: list[tuple[Any, ...]] = cur.fetchall()  # pyright: ignore[reportExplicitAny]
    per: dict[int, list[str]] = defaultdict(list)
    for cid, intent in rows:
        per[int(cid)].append(str(intent) if intent else "")
    papc: Counter[str] = Counter()
    by_bucket: dict[str, Counter[str]] = defaultdict(Counter)
    for ints in per.values():
        lab = [i for i in ints if i]
        if not lab:
            continue
        top = Counter(lab).most_common(1)[0][0]
        papc[top] += 1
        n = len(ints)
        b = "1" if n == 1 else "2" if n == 2 else "3-4" if n <= 4 else "5+"
        by_bucket[b].update([top])
    return papc, by_bucket


def share(c: Counter[str]) -> float:
    """
    Background share over the labeled papers of one citing paper
    """
    tot = sum(c[k] for k in CLASSES)
    return 100.0 * c["background"] / tot if tot else 0.0


if __name__ == "__main__":
    surveys: list[dict[str, Any]] = json.loads(
        (HERE / "data" / "surveys.json").read_text()
    )  # pyright: ignore[reportExplicitAny]
    cats = sorted({str(s["category"]) for s in surveys})
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        _ = cur.execute("SET statement_timeout = '900s'")
        _ = cur.execute(
            PICK_CONTROL, {"cats": cats, "scan": 400000, "lim": N_CONTROL}
        )  # pyright: ignore[reportArgumentType]
        ctrl: list[tuple[Any, ...]] = cur.fetchall()  # pyright: ignore[reportExplicitAny]
        print(
            f"{len(ctrl)} control papers, non-survey titles, >=60 resolved refs, same categories\n"
        )

        agg: dict[str, dict[str, Counter[str]]] = {
            "survey": defaultdict(Counter),
            "control": defaultdict(Counter),
        }
        rows_out: list[dict[str, Any]] = []  # pyright: ignore[reportExplicitAny]
        for arm, ids in (
            (
                "survey",
                [(str(s["arxiv_id"]), str(s["category"]), int(s["n_refs"])) for s in surveys],
            ),
            ("control", [(str(r[0]), str(r[2]), int(r[3])) for r in ctrl]),
        ):
            shares: list[float] = []
            for aid, cat, nref in ids:
                if id_yymm(aid) == 0:
                    continue
                papc, bb = profile(cur, aid)
                if not sum(papc.values()):
                    continue
                shares.append(share(papc))
                for b, c in bb.items():
                    agg[arm][b].update(c)
                rows_out.append(
                    {"arm": arm, "arxiv_id": aid, "cat": cat, "n_refs": nref, "bg": share(papc)}
                )
            shares.sort()
            med = shares[len(shares) // 2] if shares else 0.0
            print(
                f"{arm:<8} n={len(shares):<3} background share  "
                f"median {med:5.1f}  min {min(shares):5.1f}  max {max(shares):5.1f}"
            )

        print("\nbackground share by mention bucket, pooled\n")
        print(f"{'mentions':<10} {'survey':>18} {'control':>18}")
        for b in ("1", "2", "3-4", "5+"):
            cells: list[str] = []
            for arm in ("survey", "control"):
                c = agg[arm][b]
                tot = sum(c[k] for k in CLASSES)
                cells.append(f"{share(c):5.1f}  (n={tot:>6})" if tot else "     -")
            print(f"{b:<10} {cells[0]:>18} {cells[1]:>18}")
        _ = (HERE / "data" / "intent_control.json").write_text(json.dumps(rows_out, indent=1))
