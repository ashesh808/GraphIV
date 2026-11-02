"""Build bounded-memory FAISS candidate indexes over immutable SQLite vectors."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

BATCH_SIZE = 1024
VECTOR_DTYPES = {"float32": np.dtype("<f4"), "float16": np.dtype("<f2")}


def _batch(rows: list[Any], dimension: int, dtype: np.dtype) -> NDArray[np.float32]:
    matrix = np.empty((len(rows), dimension), dtype=np.float32)
    for number, (_, blob) in enumerate(rows):
        vector = np.frombuffer(blob, dtype=dtype)
        if len(vector) != dimension or not np.all(np.isfinite(vector)):
            raise ValueError("A stored vector does not match the index dimension/content")
        matrix[number] = vector
    if np.any(np.linalg.norm(matrix, axis=1) == 0):
        raise ValueError("A candidate index cannot contain zero vectors")
    return matrix


def build_index(
    connection: sqlite3.Connection,
    path: Path,
    dimension: int,
    *,
    index_kind: str = "flat",
    nlist: int = 1024,
    nprobe: int = 128,
    train_size: int = 65536,
    seed: int = 0,
) -> dict[str, Any]:
    """Build FlatIP or IVF/SQ8 candidates, retaining exact vectors in SQLite.

    IVF training uses a bounded, deterministic sample of actual stored vectors;
    additions stream in ordinal order. SQ8 changes candidate recall, while the
    runtime adapter rescores candidates against their original stored vectors.
    """
    import faiss

    if dimension <= 0 or nlist <= 0 or nprobe <= 0 or train_size <= 0:
        raise ValueError("Index dimensions, list/probe counts, and training size must be positive")
    if index_kind not in {"flat", "ivfsq8"}:
        raise ValueError("index_kind must be flat or ivfsq8")
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    metadata = dict(connection.execute("SELECT key,value FROM corpus_metadata"))
    dtype_name = metadata.get("vector_dtype", "float32")
    if dtype_name not in VECTOR_DTYPES:
        raise ValueError("vector_dtype must be float32 or float16")
    dtype = VECTOR_DTYPES[dtype_name]
    total, low, high = connection.execute(
        "SELECT count(*),min(faiss_id),max(faiss_id) FROM vector_ids"
    ).fetchone()
    if not total or low != 0 or high != total - 1:
        raise ValueError("vector_ids must contain contiguous, nonempty FAISS ordinals")
    started = time.perf_counter()
    training_count = 0
    effective_nlist = 0
    effective_nprobe = 0
    if index_kind == "flat":
        index = faiss.IndexFlatIP(dimension)
    else:
        training_count = min(total, train_size)
        sample_ids = (
            np.random.default_rng(seed).choice(total, training_count, replace=False).tolist()
        )
        rows = connection.execute(
            "SELECT v.faiss_id,p.embed_full FROM vector_ids v "
            "JOIN papers p ON p.arxiv_id=v.arxiv_id "
            "WHERE v.faiss_id IN (SELECT value FROM json_each(?)) ORDER BY v.faiss_id",
            (json.dumps(sample_ids),),
        ).fetchall()
        if len(rows) != training_count:
            raise ValueError("The training sample contains missing paper-vector records")
        sample = _batch(rows, dimension, dtype)
        del rows
        faiss.normalize_L2(sample)
        effective_nlist = min(nlist, max(1, training_count // 39))
        effective_nprobe = min(nprobe, effective_nlist)
        index = faiss.IndexIVFScalarQuantizer(
            faiss.IndexFlatIP(dimension),
            dimension,
            effective_nlist,
            faiss.ScalarQuantizer.QT_8bit,
            faiss.METRIC_INNER_PRODUCT,
        )
        index.cp.seed = seed
        index.train(sample)
        index.nprobe = effective_nprobe
        del sample
    trained = time.perf_counter()
    cursor = connection.execute(
        "SELECT v.faiss_id,p.embed_full FROM vector_ids v "
        "JOIN papers p ON p.arxiv_id=v.arxiv_id ORDER BY v.faiss_id"
    )
    added = 0
    while rows := cursor.fetchmany(BATCH_SIZE):
        if any(row[0] != added + number for number, row in enumerate(rows)):
            raise ValueError("The vector mapping changed or contains missing records")
        matrix = _batch(rows, dimension, dtype)
        faiss.normalize_L2(matrix)
        index.add(matrix)
        added += len(rows)
    if added != total or index.ntotal != total:
        raise ValueError("The FAISS index and SQLite vector mapping disagree")
    faiss.write_index(index, str(path))
    finished = time.perf_counter()
    settings = {
        "faiss_index_kind": index_kind,
        "faiss_nlist": str(effective_nlist),
        "faiss_nprobe": str(effective_nprobe),
        "faiss_oversample": "4",
    }
    connection.executemany(
        "INSERT INTO corpus_metadata(key,value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        settings.items(),
    )
    return {
        "kind": index_kind,
        "dimension": dimension,
        "vectors": total,
        "vector_dtype": dtype_name,
        "nlist": effective_nlist,
        "nprobe": effective_nprobe,
        "training_vectors": training_count,
        "training_seconds": round(trained - started, 3),
        "add_seconds": round(finished - trained, 3),
        "index_bytes": path.stat().st_size,
        "rerank_oversample": 4,
    }
