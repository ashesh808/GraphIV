"""
LitSearch with the corpus held equal: exact cosine over their arXiv-resolvable documents only

Our full index is 48x their corpus, so a top-k over 3.10M is not the same measurement
Restricting to the intersection removes distractors we have and they never had
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import psycopg

from graphiv.core.embed import embed_query
from graphiv.core.settings import PG_DSN

HERE = Path(__file__).parent
RAW = HERE / "external" / "raw" / "litsearch"
KS = (5, 20, 100)


def _norm(t: str) -> str:
    """
    LitSearch's own title key: lowercase, letters only
    """
    return "".join(c for c in t.lower() if c.isalpha())


def corpus_ids() -> list[str]:
    """
    ArXiv ids for LitSearch's corpus, matched on the letters-only title key

        The released s2 map covers only the 574 gold papers, so the 64,183 corpus rows
        have to be bridged by title.
    """
    import pandas as pd  # pyright: ignore[reportMissingTypeStubs]

    df = cast(Any, pd).read_parquet(
        RAW / "corpus_clean_ids_titles.parquet"
    )  # pyright: ignore[reportExplicitAny]
    want = {_norm(str(t)) for t in df["title"].tolist() if t}  # pyright: ignore[reportAny]
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        _ = cur.execute("SET statement_timeout = '1800s'")
        _ = cur.execute("CREATE TEMP TABLE lt (k text)")
        with cur.copy("COPY lt (k) FROM STDIN") as cp:
            for k in want:
                cp.write_row((k,))
        _ = cur.execute("CREATE INDEX ON lt (left(k, 120))")
        _ = cur.execute(
            "SELECT DISTINCT m.arxiv_id FROM paper_meta m JOIN lt "
            "ON left(lt.k, 120) = left(regexp_replace(lower(m.title), '[^a-z]', '', 'g'), 120)"
        )
        rows: list[tuple[Any, ...]] = cur.fetchall()  # pyright: ignore[reportExplicitAny]
    print(f"  bridged {len(rows)} of {len(want)} LitSearch corpus titles to arXiv ids")
    return sorted({str(r[0]) for r in rows})


def load_matrix(ids: list[str]) -> tuple[list[str], np.ndarray]:
    """
    Unit-normalized embedding matrix for the ids present in the production space
    """
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        _ = cur.execute(
            "SELECT arxiv_id, embedding_asym::text FROM paper_embedding_asym WHERE arxiv_id = ANY(%s)",
            (ids,),
        )
        rows: list[tuple[Any, ...]] = cur.fetchall()  # pyright: ignore[reportExplicitAny]
    keep = [str(r[0]) for r in rows]
    mat = np.array(
        [json.loads(str(r[1])) for r in rows], dtype=np.float32
    )  # pyright: ignore[reportAny]
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
    return keep, mat


def main() -> None:
    """
    Score exact top-k over the shared corpus and print recall at each cutoff
    """
    cids = corpus_ids()
    keep, mat = load_matrix(cids)
    print(f"LitSearch corpus: {len(cids)} arXiv-resolvable ids, {len(keep)} embedded in our space")
    rows: list[dict[str, Any]] = [  # pyright: ignore[reportExplicitAny]
        json.loads(x)
        for x in (HERE / "external" / "litsearch_mapped.jsonl").read_text().splitlines()
        if x.strip()
    ]
    idx = {a: i for i, a in enumerate(keep)}
    usable = [r for r in rows if r["gold_arxiv_ids"] and all(g in idx for g in r["gold_arxiv_ids"])]
    print(f"queries scored: {len(usable)} (gold entirely inside the shared corpus)\n")
    """
    Their corpus is 64,183 docs and only 14,982 resolve to arXiv, so the shared corpus has
    77 percent of the distractors deleted.
    Padding with random arXiv papers restores the haystack size without restoring identity.
    """
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        _ = cur.execute("SET statement_timeout = '900s'")
        _ = cur.execute(
            "SELECT e.arxiv_id, e.embedding_asym::text FROM paper_embedding_asym e "
            "JOIN paper_meta m USING (arxiv_id) WHERE m.primary_category = 'cs' "
            "AND m.year BETWEEN 2015 AND 2024 AND NOT (e.arxiv_id = ANY(%s)) LIMIT %s",
            (keep, 64183 - len(keep)),
        )
        prows: list[tuple[Any, ...]] = cur.fetchall()  # pyright: ignore[reportExplicitAny]
    pad_ids = [str(r[0]) for r in prows]
    pad = np.array(
        [json.loads(str(r[1])) for r in prows], dtype=np.float32
    )  # pyright: ignore[reportAny]
    pad /= np.linalg.norm(pad, axis=1, keepdims=True) + 1e-9
    keep_pad = keep + pad_ids
    mat_pad = np.vstack([mat, pad])
    print(f"size-matched corpus: {len(keep_pad)} docs ({len(pad_ids)} random cs padding)\n")

    spec = {0: "specificity 0", 1: "specificity 1"}
    groups: dict[str, list[dict[str, Any]]] = {"all": usable}  # pyright: ignore[reportExplicitAny]
    for v, name in spec.items():
        groups[name] = [r for r in usable if r.get("specificity") == v]

    for label, kp, mt in (("shared corpus", keep, mat), ("size-matched", keep_pad, mat_pad)):
        print(f"--- {label}, {len(kp)} docs ---")
        print(f"{'query subset':<18} {'n':>5} " + " ".join(f"{'R@' + str(k):>8}" for k in KS))
        for gname, rs in groups.items():
            if not rs:
                continue
            h = {k: 0 for k in KS}
            for r in rs:
                qv = np.array(embed_query(str(r["query"]), mode="asym"), dtype=np.float32)
                qv /= np.linalg.norm(qv) + 1e-9
                order = np.argsort(-(mt @ qv))
                gold = set(r["gold_arxiv_ids"])
                for k in KS:
                    if gold & {kp[i] for i in order[:k]}:
                        h[k] += 1
            print(
                f"{gname:<18} {len(rs):>5} " + " ".join(f"{100 * h[k] / len(rs):>8.1f}" for k in KS)
            )
        print()


if __name__ == "__main__":
    main()
