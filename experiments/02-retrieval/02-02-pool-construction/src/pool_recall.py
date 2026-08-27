"""
Pool-stage recall on the 60 surveys, swept one lever at a time

Only asks whether a gold reference reaches the candidate pool, so no reader and no LLM run
That makes it the ceiling every selection experiment downstream is measured against
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from _harness.bench.lexical import lexical_or

from graphiv.core.embed import embed_query
from graphiv.core.models import PoolNode
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store, abs_yymm
from graphiv.retrieve.hybrid import RRF_K
from graphiv.retrieve.recency import detect_frontier
from graphiv.retrieve.refined import frontier_pull, refined_pool
from graphiv.retrieve.subgraph import augment_with_ancestors, topical_pool
from graphiv.retrieve.topic_anchor import TopicTree

HERE = Path(__file__).parent
POOLS = HERE / "data" / "pools"
OUT = HERE / "data" / "pool_recall.json"

MENTION_FLOOR = 3
TARGET = 280
EMBED_MODE = "asym"
RECENCY = 0.4

# baseline is the shipped configuration, and each arm below moves exactly one lever off it
BASE = {"ef": 1000, "lex": "plainto", "n_pool": 400, "floor": 0.30}
ARMS: list[dict[str, Any]] = [  # pyright: ignore[reportExplicitAny]
    {"name": "shipped"},
    {"name": "ef_search 40 (the old silent default)", "ef": 40},
    {"name": "lexical off", "lex": "off"},
    {"name": "lexical OR (bug fixed)", "lex": "or"},
    *({"name": f"n_pool {n}", "n_pool": n} for n in (200, 600, 800)),
    *({"name": f"ancestor floor {f}", "floor": f} for f in (0.25, 0.35, 0.40, 0.45)),
]


def hybrid(
    store: Store, qvec: list[float], question: str, n_pool: int, lex: str
) -> dict[str, PoolNode]:
    """
    The shipped hybrid pool with the lexical arm swappable between broken, fixed and off
    """
    vec = topical_pool(store, qvec, n_pool)
    if lex == "off":
        return vec
    hits = (
        store.lexical_pool(question, 400) if lex == "plainto" else lexical_or(store, question, 400)
    )
    rank_v = {a: i for i, a in enumerate(sorted(vec, key=lambda x: vec[x].score, reverse=True))}
    rank_l = {n.arxiv_id: i for i, n in enumerate(hits)}
    nodes: dict[str, PoolNode] = {n.arxiv_id: n for n in hits}
    nodes.update(vec)
    rrf = {
        a: (1.0 / (RRF_K + rank_v[a]) if a in rank_v else 0.0)
        + (1.0 / (RRF_K + rank_l[a]) if a in rank_l else 0.0)
        for a in set(rank_v) | set(rank_l)
    }
    top = sorted(rrf, key=lambda a: rrf[a], reverse=True)[:n_pool]
    return {a: PoolNode(a, nodes[a].title, nodes[a].year, nodes[a].category, rrf[a]) for a in top}


def build(
    s: dict[str, Any], tree: TopicTree, cfg: dict[str, Any]
) -> set[str]:  # pyright: ignore[reportExplicitAny]
    """
    One pool under one configuration, returning just the arxiv ids it contains
    """
    yymm = str(s["yymm"])
    cap = abs_yymm(int(yymm[:2]), int(yymm[2:]))
    now = datetime(cap // 100, cap % 100, 28)
    store = Store(
        PG_DSN, emb_space=EMBED_MODE, max_yymm=cap, exclude=frozenset({str(s["arxiv_id"])})
    )
    _ = store.conn.execute(f"SET hnsw.ef_search = {int(cfg['ef'])}")  # pyright: ignore[reportAny]
    question = str(s["question"])
    qvec = embed_query(question, mode=EMBED_MODE)
    n_pool = int(cfg["n_pool"])  # pyright: ignore[reportAny]
    pool = hybrid(store, qvec, question, n_pool, str(cfg["lex"]))
    years = [n.year for n in pool.values() if n.year is not None]
    fr = detect_frontier(years, now.year, now.month, 80, RECENCY)
    # target stays at the shipped 280 so sweeping n_pool moves one lever and not two
    pool, _, _ = refined_pool(store, qvec, pool, tree, fr.frontier_year, target=TARGET)
    pool.update(frontier_pull(store, qvec, fr.frontier_year, want=max(40, fr.recent_floor)))
    _ = augment_with_ancestors(
        store, pool, qvec, max_add=120, min_cosine=float(cfg["floor"])
    )  # pyright: ignore[reportAny]
    store.conn.close()
    return set(pool)


def main() -> None:
    """
    Sweep every arm over every survey and write per-arm gold-in-pool counts
    """
    battery: list[dict[str, Any]] = json.loads(
        (HERE / "data" / "battery60.json").read_text()
    )  # pyright: ignore[reportExplicitAny]
    gold: dict[str, set[str]] = {}
    for p in sorted(POOLS.glob("*.pkl")):
        with p.open("rb") as fh:
            c: dict[str, Any] = pickle.load(fh)  # pyright: ignore[reportExplicitAny, reportAny]
        gold[p.stem] = {a for a, n in c["qrels"].items() if int(n) >= MENTION_FLOOR}
    tree = TopicTree()
    found: dict[str, Counter[str]] = {a["name"]: Counter() for a in ARMS}
    sizes: dict[str, Counter[str]] = {a["name"]: Counter() for a in ARMS}
    total: Counter[str] = Counter()
    for i, s in enumerate(battery, 1):
        aid = str(s["arxiv_id"])
        if aid not in gold:
            continue
        sp = str(s.get("split", "dev"))
        total[sp] += len(gold[aid])
        t0 = time.time()
        line: list[str] = []
        for arm in ARMS:
            cfg = {**BASE, **{k: v for k, v in arm.items() if k != "name"}}
            try:
                ids = build(s, tree, cfg)
            except Exception as exc:  # noqa: BLE001
                print(f"  {aid} {arm['name']} FAILED {exc}", flush=True)
                continue
            found[str(arm["name"])][sp] += len(ids & gold[aid])
            sizes[str(arm["name"])][sp] += len(ids)
            line.append(f"{len(ids & gold[aid])}")
        print(f"[{i}/{len(battery)}] {aid} {time.time() - t0:5.1f}s  " + " ".join(line), flush=True)
    payload = {
        "total_gold": dict(total),
        "arms": [
            {
                "name": str(a["name"]),
                "dev": found[str(a["name"])]["dev"],
                "test": found[str(a["name"])]["test"],
                "pool_dev": sizes[str(a["name"])]["dev"],
                "pool_test": sizes[str(a["name"])]["test"],
            }
            for a in ARMS
        ],
    }
    _ = OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\ngold: dev {total['dev']}, test {total['test']}\n")
    print(f"{'arm':<38} {'DEV':>6} {'TEST':>6} {'avg pool':>9}")
    for row in payload["arms"]:
        avg = (row["pool_dev"] + row["pool_test"]) / max(1, len(battery))
        print(f"{row['name']:<38} {row['dev']:>6} {row['test']:>6} {avg:>9.0f}")


if __name__ == "__main__":
    sys.exit(main())
