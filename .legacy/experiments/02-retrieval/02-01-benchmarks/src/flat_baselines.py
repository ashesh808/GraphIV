"""
The flat retrievers the LitSearch protocol compares, run over our survey benchmark

Dense alone, OR-lexical alone and their RRF, each taking the top m with no graph and no grading
This is the other half of the comparison: their methods on our test, rather than ours on theirs
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path
from typing import Any

from _harness.bench.lexical import lexical_or

from graphiv.core.embed import embed_query
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store, abs_yymm

HERE = Path(__file__).parent
RRF_K = 60


def arms_for(
    store: Store, question: str, qvec: list[float], m: int, deep: int
) -> dict[str, list[str]]:
    """
    Ranked ids from each flat retriever, deep enough that the pool-stage ceiling is visible
    """
    vec = store.vector_pool(qvec, deep)
    dense = sorted(vec, key=lambda a: vec[a].score, reverse=True)
    lex = [n.arxiv_id for n in lexical_or(store, question, deep)]
    rv = {a: i for i, a in enumerate(dense)}
    rl = {a: i for i, a in enumerate(lex)}
    rrf = {
        a: (1.0 / (RRF_K + rv[a]) if a in rv else 0.0) + (1.0 / (RRF_K + rl[a]) if a in rl else 0.0)
        for a in set(rv) | set(rl)
    }
    fused = sorted(rrf, key=lambda a: rrf[a], reverse=True)
    return {"dense_flat": dense, "lexical_flat": lex, "rrf_flat": fused}


def main(deep: int) -> None:
    """
    Score the flat arms on every survey whose frozen pool already exists
    """
    battery: list[dict[str, Any]] = json.loads(
        (HERE / "data" / "battery60.json").read_text()
    )  # pyright: ignore[reportExplicitAny]
    out: dict[str, dict[str, Any]] = {}  # pyright: ignore[reportExplicitAny]
    dst = HERE / "data" / "flat.json"
    done: dict[str, dict[str, Any]] = (
        json.loads(dst.read_text()) if dst.exists() else {}
    )  # pyright: ignore[reportExplicitAny]
    for i, s in enumerate(battery, 1):
        aid = str(s["arxiv_id"])
        pk = HERE / "data" / "pools" / f"{aid}.pkl"
        if not pk.exists():
            continue
        if aid in done:
            out[aid] = done[aid]
            continue
        with pk.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        yymm = str(s["yymm"])
        cap = abs_yymm(int(yymm[:2]), int(yymm[2:]))
        t0 = time.time()
        qvec = embed_query(str(s["question"]), mode="asym")
        store = Store(PG_DSN, emb_space="asym", max_yymm=cap, exclude=frozenset({aid}))
        try:
            ranked = arms_for(store, str(s["question"]), qvec, c["m"], deep)
        finally:
            store.close()
        out[aid] = {"m": c["m"], "split": s.get("split", "dev"), "ranked": ranked}
        _ = dst.write_text(json.dumps(out))
        print(
            f"[{i}] {aid} {time.time() - t0:5.1f}s "
            + " ".join(f"{k}={len(v)}" for k, v in ranked.items()),
            flush=True,
        )


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
