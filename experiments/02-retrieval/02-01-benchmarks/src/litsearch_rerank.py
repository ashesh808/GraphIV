"""
Our joint selector as a reranker on LitSearch, in the slot their GPT-4 rerank arms occupy

Dense top-100 is reranked on their citation graph and our reader's relevance grade
The graph term is computed on their edges and never on ours
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd  # pyright: ignore[reportMissingTypeStubs]

from graphiv.core.embed import embed_query
from graphiv.core.models import PoolNode
from graphiv.retrieve.grade import Grade, grade_many

B = Path("/mnt/Vault-Storage/research/arxiv/benchmarks/litsearch")
TOP_K = 100
NOW_YEAR = 2024
W_REL = 0.35


def pctile(vals: dict[int, float]) -> dict[int, float]:
    """
    Rank percentile, so a graph score and a grade can be blended on one scale
    """
    o = sorted(vals, key=lambda a: (-vals[a], a))
    n = max(1, len(o) - 1)
    return {a: 1.0 - i / n for i, a in enumerate(o)}


def load() -> tuple[np.ndarray, list[int], dict[int, tuple[str, str, int]], dict[int, list[int]]]:
    """
    The exact index matrix, its corpusids, per-doc text and year, and the citation edges
    """
    mat = np.load(B / "exact_embeddings.npy")
    ids: list[int] = json.loads((B / "exact_ids.json").read_text())
    c = cast(Any, pd).read_parquet(
        B / "corpus_clean", columns=["corpusid", "title", "abstract"]
    )  # pyright: ignore[reportExplicitAny]
    s = cast(Any, pd).read_parquet(
        B / "corpus.parquet", columns=["corpusid", "year"]
    )  # pyright: ignore[reportExplicitAny]
    yr = {
        int(a): int(b) for a, b in zip(s["corpusid"], s["year"], strict=True)
    }  # pyright: ignore[reportAny]
    meta = {
        int(a): (str(t), str(ab), yr.get(int(a), 0))
        for a, t, ab in zip(
            c["corpusid"], c["title"], c["abstract"], strict=True
        )  # pyright: ignore[reportAny]
    }
    e = cast(Any, pd).read_parquet(B / "edges.parquet")  # pyright: ignore[reportExplicitAny]
    out: dict[int, list[int]] = {}
    for s_, d_ in zip(e["src"], e["dst"], strict=True):  # pyright: ignore[reportAny]
        out.setdefault(int(s_), []).append(int(d_))
    return mat, ids, meta, out


def rank_arms(
    cand: list[int],
    cos: dict[int, float],
    meta: dict[int, tuple[str, str, int]],
    adj: dict[int, list[int]],
    grades: dict[str, Grade],
) -> dict[str, list[int]]:
    """
    Dense order, plus reranks by graph alone, grade alone and the joint score
    """
    cs = set(cand)
    indeg: dict[int, int] = {a: 0 for a in cand}
    for src in cand:
        for dst in adj.get(src, ()):
            if dst in cs:
                indeg[dst] += 1
    agen = {
        a: indeg[a] / max(1, NOW_YEAR - meta[a][2] + 1) if meta[a][2] else float(indeg[a])
        for a in cand
    }
    rel = {a: float(grades[str(a)].relevance) if str(a) in grades else 0.0 for a in cand}
    p_agen = pctile(agen)
    joint = {a: (1 - W_REL) * p_agen[a] + W_REL * (rel[a] + 2) / 4 for a in cand}
    order = lambda d: sorted(cand, key=lambda a: (-d[a], a))  # noqa: E731
    return {
        "dense": order(cos),
        "graph only (citations-per-year)": order(agen),
        "grade only (reader rerank)": order({a: rel[a] + 1e-6 * cos[a] for a in cand}),
        "joint (graph + grade)": order(joint),
    }


def main(limit: int) -> None:
    """
    Rerank every query's dense top-100 and print recall per arm against the published table
    """
    mat, ids, meta, adj = load()
    idx_of = {c: i for i, c in enumerate(ids)}
    _ = idx_of
    q = cast(Any, pd).read_parquet(B / "query")  # pyright: ignore[reportExplicitAny]
    rows = list(zip(q["query"], q["specificity"], q["corpusids"], strict=True))[
        :limit
    ]  # pyright: ignore[reportAny]
    rec: dict[str, dict[tuple[int, int], list[float]]] = {}
    t0 = time.time()
    for n, (query, spec, gold) in enumerate(rows):
        qv = np.array(embed_query(str(query), mode="asym"), dtype=np.float32)
        qv /= np.linalg.norm(qv) + 1e-9
        sims = mat @ qv
        top = np.argsort(-sims)[:TOP_K]
        cand = [ids[i] for i in top]
        cos = {ids[i]: float(sims[i]) for i in top}
        pool = {
            str(a): PoolNode(str(a), meta[a][0], meta[a][2] or None, None, cos[a]) for a in cand
        }
        abstracts = {str(a): meta[a][1] for a in cand}
        qh = hashlib.sha1(f"litsearch::{query}".encode()).hexdigest()[:12]
        grades = asyncio.run(grade_many(str(query), qh, pool, [str(a) for a in cand], abstracts))
        g = {int(x) for x in gold}  # pyright: ignore[reportAny]
        for name, order in rank_arms(cand, cos, meta, adj, grades).items():
            for k in (5, 20):
                hit = len(set(order[:k]) & g) / len(g)
                rec.setdefault(name, {}).setdefault((int(spec), k), []).append(
                    hit
                )  # pyright: ignore[reportAny]
        if n % 10 == 0:
            el = time.time() - t0
            print(
                f"  {n}/{len(rows)}  {el / max(1, n):.1f}s/q  eta {(len(rows) - n) * el / max(1, n) / 60:.0f}m",
                flush=True,
            )

    print(f"\nLitSearch, {len(rows)} queries, dense top-{TOP_K} reranked, their corpus and edges\n")
    print(f"{'arm':<34} {'spec R@5':>9} {'broad R@20':>11} {'spec R@20':>10} {'broad R@5':>10}")

    def m(cells: dict[tuple[int, int], list[float]], s: int, k: int) -> str:
        """
        One recall cell as a percentage, or a dash when the arm never produced it
        """
        v = cells.get((s, k))
        return f"{100 * float(np.mean(v)):.1f}" if v else "-"

    for name, cells in rec.items():
        print(
            f"{name:<34} {m(cells, 1, 5):>9} {m(cells, 0, 20):>11} "
            f"{m(cells, 1, 20):>10} {m(cells, 0, 5):>10}"
        )
    print("\npublished, same corpus: BM25 50.0 / 39.9, GPT-4 rerank over BM25 68.0 / 59.9,")
    print("GritLM-7B 74.8 / 70.8, GPT-4 rerank over GritLM 79.2 / 75.3")
    _ = (B / "rerank_recall.json").write_text(
        json.dumps(
            {n: {f"{s}_{k}": float(np.mean(v)) for (s, k), v in c.items()} for n, c in rec.items()}
        )
    )


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10**6)
