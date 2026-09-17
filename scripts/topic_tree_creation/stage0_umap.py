"""
Fit the reducer on a sample of the full vectors and project the whole corpus through it

A refit moves every vector, so topic_tree is rebuilt outright rather than updated in place
The transform runs in worker processes, since one call holds one core whatever `n_jobs` is set to
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import tomllib
from collections import deque
from multiprocessing.pool import AsyncResult
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import psycopg
from numpy.typing import NDArray

_MODEL: Any = None  # pyright: ignore[reportExplicitAny]


def parse_block(raws: list[str]) -> NDArray[np.float32]:
    """
    Decode a chunk of `[a,b,c]` text vectors, one numpy call per row rather than one per float

    Args:
        raws: the column values as text, all of the same width.

    Returns:
        One row per input vector.
    """
    return np.asarray([np.fromstring(r[1:-1], dtype=np.float32, sep=",") for r in raws])


def _worker_setup(path: str) -> None:
    """
    Load the reducer into a transform worker

    Args:
        path: the fitted model.
    """
    global _MODEL
    _MODEL = joblib.load(path)  # pyright: ignore[reportAny]


def _worker_transform(block: NDArray[np.float32]) -> NDArray[np.float32]:
    """
    Reduce one block inside the worker that already holds the model

    Args:
        block: full vectors.

    Returns:
        The reduced vectors.
    """
    return _MODEL.transform(block)  # pyright: ignore[reportAny]


class Reducer:
    """
    The fitted projection and the rebuild of topic_tree it drives
    """

    def __init__(self, path: str, dim: int, seed: int) -> None:
        """
        Args:
            path: where the fitted model is saved.
            dim: output dimensionality.
            seed: fixes the projection trees and the layout sgd, at the cost of one core.
        """
        self.path = path
        self.dim = dim
        self.seed = seed

    def fit(self, pg_dest: str, sample: int) -> None:
        """
        Fit the reducer on a sample of the full vectors and save it

        Refuses to run while papers are still waiting to be embedded, since fitting on a partial
        corpus produces a valid-looking model whose neighborhoods are wrong.

        Args:
            pg_dest: libpq connection string.
            sample: how many vectors to fit on.

        Raises:
            SystemExit: if any paper is still at stage 2.
        """
        import umap  # noqa: PLC0415

        with psycopg.connect(pg_dest) as conn:
            row = conn.execute("SELECT count(*) FROM papers WHERE stage = 2").fetchone()
            waiting = int(row[0]) if row else 0
            if waiting:
                raise SystemExit(f"{waiting:,} papers still at stage 2, embed them before fitting")
            rows: list[tuple[str]] = conn.execute(
                "SELECT embed_full::text FROM papers WHERE embed_full IS NOT NULL"
                " ORDER BY random() LIMIT %s",
                (sample,),
            ).fetchall()

        train = parse_block([r[0] for r in rows])
        print(f"[stage0] fitting umap on {train.shape[0]:,} vectors", flush=True)
        model = umap.UMAP(n_components=self.dim, metric="cosine", random_state=self.seed)
        _ = model.fit(train)
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = joblib.dump(model, target)
        print(f"[stage0] saved {target}", flush=True)

    def project(self, pg_dest: str, batch: int, workers: int) -> int:
        """
        Rebuild topic_tree from every embedded paper, as a truncate and a copy

        The table holds nothing a refit can keep, so it is emptied and refilled rather than
        updated, which writes no dead rows and leaves nothing for vacuum.

        Args:
            pg_dest: libpq connection string.
            batch: rows per transform call.
            workers: transform processes, each of which loads its own copy of the model.

        Returns:
            How many papers were projected.
        """
        ctx = mp.get_context("spawn")
        done = 0
        with psycopg.connect(pg_dest) as reader, psycopg.connect(pg_dest) as writer:
            _ = writer.execute("TRUNCATE topic_tree")

            def copy_rows(ids: list[str], vecs: NDArray[np.float32]) -> int:
                with writer.cursor().copy(
                    "COPY topic_tree (arxiv_id, stage, embed_umap) FROM STDIN"
                ) as cp:
                    for arxiv_id, v in zip(ids, vecs, strict=True):
                        cp.write_row((arxiv_id, 0, "[" + ",".join(f"{x:.6g}" for x in v) + "]"))
                return len(ids)

            def drain(q: deque[tuple[list[str], AsyncResult[NDArray[np.float32]]]]) -> int:
                ids, job = q.popleft()
                n = copy_rows(ids, job.get())
                print(f"[stage0]   projected {done + n:,}", flush=True)
                return n

            with reader.cursor(name="project") as cur:
                _ = cur.execute(
                    "SELECT arxiv_id, embed_full::text FROM papers"
                    " WHERE stage >= 3 AND embed_full IS NOT NULL"
                )
                with ctx.Pool(workers, initializer=_worker_setup, initargs=(self.path,)) as pool:
                    flight: deque[tuple[list[str], AsyncResult[NDArray[np.float32]]]] = deque()
                    while True:
                        chunk: list[tuple[str, str]] = cur.fetchmany(batch)
                        if not chunk:
                            break
                        block = parse_block([raw for _, raw in chunk])
                        job = pool.apply_async(_worker_transform, (block,))
                        flight.append(([a for a, _ in chunk], job))
                        # bounded, so the reader cannot run the whole corpus ahead of the workers
                        while len(flight) >= 2 * workers:
                            done += drain(flight)
                    while flight:
                        done += drain(flight)
            writer.commit()
        print(f"[stage0] wrote {done:,} projections", flush=True)
        return done


def main() -> None:
    """
    Read the config, then fit the reducer and rebuild topic_tree through it
    """
    ap = argparse.ArgumentParser()
    _ = ap.add_argument("--config_path", default="config.toml")
    _ = ap.add_argument("--skip-fit", action="store_true", help="project with the model on disk")
    args = ap.parse_args()

    cfg = tomllib.loads(
        Path(str(args.config_path)).read_text(encoding="utf-8")
    )  # pyright: ignore[reportAny]
    um = cfg["umap"]
    dsn = str(cfg["database"]["PG_DEST"])
    reducer = Reducer(
        path=str(um["UMAP_MODEL_PATH"]), dim=int(um["UMAP_DIM"]), seed=int(um["UMAP_SEED"])
    )
    if not bool(args.skip_fit):  # pyright: ignore[reportAny]
        reducer.fit(dsn, int(um["UMAP_SAMPLE"]))
    _ = reducer.project(dsn, int(um["UMAP_BATCH"]), int(um["UMAP_WORKERS"]))


if __name__ == "__main__":
    main()
