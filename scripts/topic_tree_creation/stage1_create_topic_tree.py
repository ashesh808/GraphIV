"""
Cluster the projected vectors into a fixed-depth topic tree and write one label per level

Each level runs its own method over its parent's members only, so labels are scoped to a parent
Every run reclusters the whole corpus, since two independent fits share one integer namespace
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import psycopg
from numpy.typing import NDArray
from sklearn.cluster import HDBSCAN, MiniBatchKMeans
from threadpoolctl import threadpool_limits

from src.core.config import load_config

LEVELS = ("level_0", "level_1", "level_2")


def parse_block(raws: list[str]) -> NDArray[np.float32]:
    """
    Decode a chunk of `[a,b,c]` text vectors, one numpy call per row rather than one per float

    Args:
        raws: the column values as text, all of the same width.

    Returns:
        One row per input vector.
    """
    return np.asarray([np.fromstring(r[1:-1], dtype=np.float32, sep=",") for r in raws])


class TopicTree:
    """
    A recursive clustering over the UMAP vectors, one method per level
    """

    def __init__(self, k: int, min_cluster_size: int, seed: int, parallel: int = 1) -> None:
        """
        Args:
            k: cluster count for every kmeans level.
            min_cluster_size: smallest group hdbscan will call a cluster.
            seed: fixes the kmeans initialization, so a rerun on the same input repeats it.
            parallel: groups clustered at once within a level.
        """
        self.k = k
        self.min_cluster_size = min_cluster_size
        self.seed = seed
        self.parallel = parallel

    def cluster_one(self, vecs: NDArray[np.float32], method: str) -> NDArray[np.int32]:
        """
        Run one clustering method over one group and return a label per row

        Args:
            vecs: the group's vectors.
            method: either `kmeans` or `hdbscan`.

        Returns:
            One label per row, where hdbscan marks noise as -1.

        Raises:
            ValueError: if the method is not one of the two supported names.
        """
        if len(vecs) <= 1:
            return np.zeros(len(vecs), dtype=np.int32)
        if method == "kmeans":
            k = min(self.k, len(vecs))
            model = MiniBatchKMeans(
                n_clusters=k,
                batch_size=10_000,
                n_init=3,  # pyright: ignore[reportArgumentType]
                random_state=self.seed,
            )
            return model.fit_predict(vecs).astype(np.int32)
        if method == "hdbscan":
            if len(vecs) < self.min_cluster_size:
                return np.zeros(len(vecs), dtype=np.int32)
            model = HDBSCAN(min_cluster_size=self.min_cluster_size)
            return model.fit_predict(vecs).astype(np.int32)
        raise ValueError(f"unknown method {method!r}")

    def cluster(self, pg_dest: str, methods: list[str], batch: int) -> int:
        """
        Label every projected paper, then rewrite the table with its place in the tree

        Args:
            pg_dest: libpq connection string.
            methods: one method name per level, in order.
            batch: rows per COPY row group when writing back.

        Returns:
            How many papers were labeled.

        Raises:
            ValueError: if there are more methods than level columns.
        """
        if len(methods) > len(LEVELS):
            raise ValueError(f"{len(methods)} methods but only {len(LEVELS)} level columns")

        with psycopg.connect(pg_dest) as conn:
            rows: list[tuple[str, str]] = conn.execute(
                "SELECT arxiv_id, embed_umap::text FROM topic_tree"
            ).fetchall()
        if not rows:
            print("[stage1] nothing projected to cluster", flush=True)
            return 0

        ids = [r[0] for r in rows]
        vecs = parse_block([r[1] for r in rows])
        print(f"[stage1] clustering {len(ids):,} papers over {len(methods)} levels", flush=True)

        labels = np.full((len(ids), len(methods)), -1, dtype=np.int32)
        groups: list[NDArray[np.int64]] = [np.arange(len(ids))]
        for depth, method in enumerate(methods):
            nxt: list[NDArray[np.int64]] = []
            """
            Groups within a level never interact, so they run concurrently.
            The inner BLAS pool is pinned to one thread, otherwise each worker spawns its own
            and the two layers of parallelism oversubscribe every core.
            """

            def run(members: NDArray[np.int64], _method: str = method) -> NDArray[np.int32]:
                return self.cluster_one(vecs[members], _method)

            with threadpool_limits(limits=1):
                with ThreadPoolExecutor(max_workers=self.parallel) as pool:
                    done = list(pool.map(run, groups))
            for members, got in zip(groups, done, strict=True):
                labels[members, depth] = got
                for value in np.unique(got):
                    nxt.append(members[got == value])
            groups = nxt
            print(f"[stage1]   level {depth} ({method}): {len(groups):,} groups", flush=True)

        cols = ", ".join(LEVELS[: len(methods)])
        with psycopg.connect(pg_dest) as conn:
            _ = conn.execute("TRUNCATE topic_tree")
            with conn.cursor().copy(
                f"COPY topic_tree (arxiv_id, stage, embed_umap, {cols}) FROM STDIN"
            ) as cp:
                for i, arxiv_id in enumerate(ids):
                    vector = "[" + ",".join(f"{x:.6g}" for x in vecs[i]) + "]"
                    cp.write_row((arxiv_id, 1, vector, *(int(x) for x in labels[i])))
            conn.commit()
        print(f"[stage1] placed {len(ids):,} papers", flush=True)
        return len(ids)


def main() -> None:
    """
    Read the config, then build the tree over every projected paper
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()

    cfg = load_config(str(args.config_path))
    tree = TopicTree(
        k=int(cfg["topics"]["TREE_K"]),
        min_cluster_size=int(cfg["topics"]["TREE_MIN_CLUSTER_SIZE"]),
        seed=int(cfg["topics"]["TREE_SEED"]),
        parallel=int(cfg["topics"]["TREE_N_PARALLEL"]),
    )
    _ = tree.cluster(
        str(cfg["database"]["PG_DEST"]),
        methods=[str(m) for m in cfg["topics"]["TREE_METHODS"]],
        batch=int(cfg["topics"]["TREE_BATCH"]),
    )


if __name__ == "__main__":
    main()
