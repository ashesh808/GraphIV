"""Density-aware bisecting topic tree over the nomic UMAP-50 vectors.

A recursive bisecting tree with a coherence early-stop: dense/heterogeneous regions split
deep, small coherent regions become leaves. EVERY paper gets a leaf + path — there is no
noise bucket (unlike a forced uniform KMeans grid). The output drives phase-6's leaf anchor.

Output schema (TOPIC_TREE_DB):
    paper_topic(arxiv_id TEXT PK, leaf_id INT, path TEXT, depth INT)
    leaf(leaf_id INT PK, size INT, depth INT, radius REAL)
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import MiniBatchKMeans

from _common import EMB_UMAP50_NPY, OLD_SQLITE, TOPIC_TREE_DB


@dataclass
class TreeParams:
    min_leaf: int = 250
    coherence: float = 0.14  # coherence stop as fraction of root radius
    target_leaf: int = 600
    max_depth: int = 8
    max_k: int = 12


def radius(
    emb: NDArray[np.float32], idx: NDArray[np.int64], sample: int = 4000
) -> float:
    """RMS distance of points to their centroid (coherence; lower = tighter)."""
    if len(idx) > sample:
        idx = np.random.choice(idx, sample, replace=False)
    sub = emb[idx]
    c = sub.mean(axis=0)
    return float(np.sqrt(((sub - c) ** 2).sum(axis=1).mean()))


def build(
    emb: NDArray[np.float32], p: TreeParams
) -> tuple[
    NDArray[np.int64], NDArray[np.int32], list[str], list[tuple[int, int, float]]
]:
    """Return (leaf_id per row, depth per row, path-str per leaf, [(leaf,size,radius)])."""
    n = emb.shape[0]
    root_r = radius(emb, np.arange(n))
    coh_thresh = p.coherence * root_r
    print(f"[tree] root radius={root_r:.3f} coh_thresh={coh_thresh:.3f}", flush=True)

    leaf_of = np.full(n, -1, dtype=np.int64)
    depth_of = np.zeros(n, dtype=np.int32)
    leaf_path: list[str] = []
    leaves: list[tuple[int, int, float]] = []
    next_leaf = 0

    # iterative stack of (indices, depth, path)
    stack: list[tuple[NDArray[np.int64], int, tuple[int, ...]]] = [
        (np.arange(n), 0, ())
    ]
    while stack:
        idx, depth, path = stack.pop()
        m = len(idx)
        r = radius(emb, idx)
        if m <= p.min_leaf or depth >= p.max_depth or r <= coh_thresh:
            leaf_of[idx] = next_leaf
            depth_of[idx] = depth
            leaf_path.append(".".join(str(q) for q in path) or "root")
            leaves.append((next_leaf, m, r))
            next_leaf += 1
            if next_leaf % 500 == 0:
                print(f"[tree] {next_leaf} leaves, stack={len(stack)}", flush=True)
            continue
        k = int(np.clip(round(m / p.target_leaf), 2, p.max_k))
        km = MiniBatchKMeans(n_clusters=k, batch_size=10000, n_init=3, random_state=42)  # pyright: ignore[reportArgumentType]  # fmt: skip
        labels = km.fit_predict(emb[idx])
        for j in range(k):
            child = idx[labels == j]
            if len(child) == 0:
                continue
            stack.append((child, depth + 1, path + (j,)))
    return leaf_of, depth_of, leaf_path, leaves


def _write_db(
    ids: list[str],
    leaf_of: NDArray[np.int64],
    depth_of: NDArray[np.int32],
    leaf_path: list[str],
    leaves: list[tuple[int, int, float]],
) -> None:
    """Write paper_topic + leaf tables to TOPIC_TREE_DB (overwrites)."""
    if TOPIC_TREE_DB.exists():
        TOPIC_TREE_DB.unlink()
    TOPIC_TREE_DB.parent.mkdir(parents=True, exist_ok=True)
    out = sqlite3.connect(TOPIC_TREE_DB)
    _ = out.execute(
        "CREATE TABLE paper_topic (arxiv_id TEXT PRIMARY KEY, leaf_id INT, "
        "path TEXT, depth INT)"
    )
    _ = out.execute(
        "CREATE TABLE leaf (leaf_id INT PRIMARY KEY, size INT, depth INT, radius REAL)"
    )
    paper_rows = (
        (ids[i], int(leaf_of[i]), leaf_path[int(leaf_of[i])], int(depth_of[i]))
        for i in range(len(ids))
    )
    _ = out.executemany("INSERT INTO paper_topic VALUES (?,?,?,?)", paper_rows)
    _ = out.executemany(
        "INSERT INTO leaf VALUES (?,?,?,?)",
        ((lid, s, 0, r) for lid, s, r in leaves),
    )
    _ = out.execute("CREATE INDEX idx_leaf ON paper_topic(leaf_id)")
    out.commit()
    out.close()
    print(f"[tree] wrote {TOPIC_TREE_DB}", flush=True)


def run_build(p: TreeParams) -> None:
    """Load UMAP-50 vectors + id list, build the tree, write TOPIC_TREE_DB."""
    print(f"[tree] loading {EMB_UMAP50_NPY} ...", flush=True)
    emb = np.load(EMB_UMAP50_NPY).astype(np.float32)
    print(f"[tree] emb {emb.shape}; loading ids ...", flush=True)
    conn = sqlite3.connect(f"file:{OLD_SQLITE}?mode=ro", uri=True)
    ids: list[str] = [r[0] for r in conn.execute("SELECT id FROM publication")]
    conn.close()
    assert len(ids) == emb.shape[0], f"id/emb mismatch {len(ids)} vs {emb.shape[0]}"

    t0 = time.time()
    leaf_of, depth_of, leaf_path, leaves = build(emb, p)
    dt = time.time() - t0
    sizes = np.array([s for _, s, _ in leaves])
    print(f"[tree] built {len(leaves)} leaves in {dt:.0f}s", flush=True)
    print(
        f"[tree] leaf size: min={sizes.min()} median={int(np.median(sizes))} "
        f"p90={int(np.percentile(sizes, 90))} max={sizes.max()} "
        f"({sizes.max() / emb.shape[0] * 100:.2f}% of corpus)",
        flush=True,
    )
    print(
        f"[tree] depth: min={depth_of.min()} median={int(np.median(depth_of))} "
        f"max={depth_of.max()}",
        flush=True,
    )
    _write_db(ids, leaf_of, depth_of, leaf_path, leaves)
