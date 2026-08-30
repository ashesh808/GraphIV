"""
Cluster the reduced vectors into a fixed-depth topic tree and write one label per level

Each level runs its own method over its parent's members only, so labels are scoped to a parent
Every run refits the whole corpus, since two independent fits share one integer namespace
"""

from __future__ import annotations

import argparse
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import psycopg
from numpy.typing import NDArray
from sklearn.cluster import HDBSCAN, MiniBatchKMeans
from threadpoolctl import threadpool_limits

LEVELS = ("level_0", "level_1", "level_2")


def parse_vector(raw: str) -> list[float]:
    """
    Decode the `[a,b,c]` text form pgvector returns without its own adapter

    Args:
        raw: the column value as text.

    Returns:
        The vector as plain floats.
    """
    return [float(x) for x in raw.strip("[]").split(",")]


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
        Label every embedded paper, then write the levels back and advance the stage

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
                "SELECT arxiv_id, embed_umap::text FROM papers"
                " WHERE stage >= 3 AND embed_umap IS NOT NULL"
            ).fetchall()
        if not rows:
            print("[stage4] nothing embedded with a reduced vector", flush=True)
            return 0

        ids = [r[0] for r in rows]
        vecs = np.asarray([parse_vector(r[1]) for r in rows], dtype=np.float32)
        print(f"[stage4] clustering {len(ids):,} papers over {len(methods)} levels", flush=True)

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
            print(f"[stage4]   level {depth} ({method}): {len(groups):,} groups", flush=True)

        cols = ", ".join(LEVELS[: len(methods)])
        with psycopg.connect(pg_dest) as conn:
            _ = conn.execute(
                f"CREATE TEMP TABLE t (arxiv_id text PRIMARY KEY, {
                    ', '.join(f'{c} smallint' for c in LEVELS[: len(methods)])
                })"
            )
            with conn.cursor().copy(f"COPY t (arxiv_id, {cols}) FROM STDIN") as cp:
                for i, arxiv_id in enumerate(ids):
                    cp.write_row((arxiv_id, *(int(x) for x in labels[i])))
            sets = ", ".join(f"{c} = t.{c}" for c in LEVELS[: len(methods)])
            n = conn.execute(
                f"UPDATE papers p SET {sets}, stage = 4 FROM t WHERE p.arxiv_id = t.arxiv_id"
            ).rowcount
            conn.commit()
        print(f"[stage4] labeled {n:,} papers", flush=True)
        return n


def main() -> None:
    """
    Read the config, then build the tree over every embedded paper
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    args = ap.parse_args()

    cfg = tomllib.loads(
        Path(str(args.config_path)).read_text(encoding="utf-8")
    )  # pyright: ignore[reportAny]
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
