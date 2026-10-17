"""
Lays a sample of the corpus out in 2-d from the topic tree's projection, for the poster's map

The layout is cached in assets/data/field_map.npz, since the fit holds one core for minutes
Fields are grouped into disciplines by their 50-d centers, so a refit tree regroups on its own
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
import umap
from sklearn.cluster import KMeans
from style import DATA

CACHE = DATA / "field_map.npz"
SAMPLE = 250_000
DISCIPLINES = 5
# one seed so a refit lands on the same layout
SEED = 0
# sixteen centers into five groups depend on where k-means starts, so it starts many times
RESTARTS = 20


def fit(dsn: str) -> dict[str, Any]:
    """
    Samples papers with the store's own repeatable sampler and lays their projections out in 2-d

    Args:
        dsn: libpq connection string of the store.

    Returns:
        Each sampled paper's field and position, every field's 50-d center and every field's name.
    """
    with psycopg.connect(dsn) as conn:
        row = conn.execute("SELECT count(*) FROM topic_tree").fetchone()
        share = round(100 * SAMPLE / int(row[0] if row else 1), 4)
        rows = conn.execute(
            "SELECT level_0, embed_umap::text FROM topic_tree"
            " TABLESAMPLE SYSTEM (%s) REPEATABLE (%s)",
            (share, SEED),
        ).fetchall()
        names = conn.execute(
            "SELECT level_0, name FROM topic_names WHERE level_1 IS NULL ORDER BY level_0"
        ).fetchall()
    print(f"[field_map] laying out {len(rows):,} papers", flush=True)
    field = np.array([r[0] for r in rows], dtype=np.int16)
    vectors = np.stack([np.array(json.loads(r[1]), dtype=np.float32) for r in rows])
    layout = umap.UMAP(
        n_components=2, n_neighbors=30, min_dist=0.3, random_state=SEED, low_memory=True
    )
    xy = np.asarray(layout.fit_transform(vectors), dtype=np.float32)
    centers = np.stack([vectors[field == f].mean(axis=0) for f, _ in names])
    return {
        "field": field,
        "xy": xy,
        "centers": centers,
        "names": np.array([n for _, n in names]),
    }


def load(config: Path) -> dict[str, Any]:
    """
    The cached layout, fitted from the store first when there is none

    Args:
        config: The config whose PG_DEST names the store.

    Returns:
        The layout, plus each field's discipline, numbered biggest first.
    """
    if CACHE.is_file():
        with np.load(CACHE) as held:
            out: dict[str, Any] = {key: held[key] for key in held.files}
    else:
        dsn = str(tomllib.loads(config.read_text(encoding="utf-8"))["database"]["PG_DEST"])
        out = fit(dsn)
        np.savez_compressed(CACHE, **out)
    clusters = KMeans(DISCIPLINES, random_state=SEED).set_params(n_init=RESTARTS)
    group = clusters.fit_predict(out["centers"])
    sizes = np.bincount(group[out["field"]], minlength=DISCIPLINES)
    order = np.argsort(-sizes)
    out["discipline"] = np.argsort(order)[group]
    return out
