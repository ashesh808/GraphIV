"""Build the unchanged graph arrays using disk-backed SQLite pairs and NumPy maps."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

CHUNK = 100_000
INT32_MAX = np.iinfo(np.int32).max


def write_graph(connection: sqlite3.Connection, path: Path) -> int:
    """Stream distinct resolved pairs into both CSR directions without giant edge lists."""
    count, max_id = connection.execute(
        "SELECT count(*), max(length(CAST(arxiv_id AS BLOB))) FROM papers"
    ).fetchone()
    if not 0 < count <= INT32_MAX:
        raise ValueError("GraphExport needs between one and int32-max paper rows")
    connection.execute(
        "CREATE TEMP TABLE graph_nodes (arxiv_id TEXT PRIMARY KEY, ordinal INTEGER UNIQUE NOT NULL)"
    )
    connection.execute(
        "INSERT INTO graph_nodes SELECT arxiv_id,"
        "row_number() OVER (ORDER BY arxiv_id)-1 FROM papers"
    )
    connection.execute(
        "CREATE TEMP TABLE graph_pairs (source INTEGER NOT NULL,target INTEGER NOT NULL,"
        "PRIMARY KEY(source,target)) WITHOUT ROWID"
    )
    connection.execute(
        "INSERT OR IGNORE INTO graph_pairs SELECT source.ordinal,target.ordinal "
        "FROM citations c JOIN graph_nodes source ON source.arxiv_id=c.source_id "
        "JOIN graph_nodes target ON target.arxiv_id=c.target_id WHERE c.target_id IS NOT NULL"
    )
    edges = connection.execute("SELECT count(*) FROM graph_pairs").fetchone()[0]
    if edges > INT32_MAX:
        raise ValueError("GraphExport cannot represent more than int32-max distinct citation pairs")
    connection.execute("CREATE INDEX graph_pairs_target ON graph_pairs(target,source)")
    with tempfile.TemporaryDirectory(prefix=".graph-arrays-", dir=path.parent) as temporary:
        work = Path(temporary)
        maps: list[np.memmap] = []

        def mapped(name: str, dtype: Any, shape: tuple[int, ...]) -> np.ndarray:
            if not np.prod(shape):
                return np.empty(shape, dtype=dtype)
            result = np.lib.format.open_memmap(
                work / f"{name}.npy", mode="w+", dtype=dtype, shape=shape
            )
            maps.append(result)
            return result

        try:
            arrays = {
                "ids": mapped("ids", f"S{max_id}", (count,)),
                "day": mapped("day", np.int32, (count,)),
                "stage": mapped("stage", np.int8, (count,)),
                "survey": mapped("survey", np.float32, (count,)),
                "level": mapped("level", np.int8, (count, 3)),
            }
            arrays["level"][:] = -1
            cursor = connection.execute(
                "SELECT p.arxiv_id,p.date,p.stage,coalesce(p.survey_probability,-1) "
                "FROM papers p JOIN graph_nodes g ON g.arxiv_id=p.arxiv_id ORDER BY g.ordinal"
            )
            offset = 0
            while rows := cursor.fetchmany(CHUNK):
                end = offset + len(rows)
                arrays["ids"][offset:end] = [row[0].encode() for row in rows]
                days = np.asarray([row[1] or "1970-01-01" for row in rows], dtype="datetime64[D]")
                numbers = days.astype(np.int64)
                numbers[[row[1] is None for row in rows]] = -(1 << 30)
                arrays["day"][offset:end] = numbers
                arrays["stage"][offset:end] = np.fromiter((row[2] for row in rows), dtype=np.int8)
                arrays["survey"][offset:end] = np.fromiter(
                    (row[3] for row in rows), dtype=np.float32
                )
                offset = end
            cursor = connection.execute(
                "SELECT g.ordinal,t.level_0,t.level_1,t.level_2 FROM topic_tree t "
                "JOIN graph_nodes g ON g.arxiv_id=t.arxiv_id "
                "WHERE t.stage=1 AND t.level_2 IS NOT NULL"
            )
            while rows := cursor.fetchmany(CHUNK):
                for ordinal, level0, level1, level2 in rows:
                    values = (level0, level1, level2)
                    if any(value is None or not -128 <= value <= 127 for value in values):
                        raise ValueError(
                            "Topic levels must fit the GraphExport int8 representation"
                        )
                    arrays["level"][ordinal] = values
            for name, row, column in (("refs", "source", "target"), ("cites", "target", "source")):
                pointer = mapped(f"{name}_ptr", np.int32, (count + 1,))
                pointer[:] = 0
                cursor = connection.execute(
                    f"SELECT {row},count(*) FROM graph_pairs GROUP BY {row} ORDER BY {row}"
                )
                while counts := cursor.fetchmany(CHUNK):
                    positions = np.fromiter((item[0] + 1 for item in counts), dtype=np.int64)
                    pointer[positions] = np.fromiter((item[1] for item in counts), dtype=np.int32)
                np.cumsum(pointer, dtype=np.int64, out=pointer)
                indices = mapped(f"{name}_idx", np.int32, (edges,))
                cursor = connection.execute(
                    f"SELECT {column} FROM graph_pairs ORDER BY {row},{column}"
                )
                offset = 0
                while rows := cursor.fetchmany(CHUNK):
                    end = offset + len(rows)
                    indices[offset:end] = np.fromiter((item[0] for item in rows), dtype=np.int32)
                    offset = end
                if int(pointer[-1]) != edges or offset != edges:
                    raise ValueError("The streamed graph CSR counts disagree")
                arrays[f"{name}_ptr"], arrays[f"{name}_idx"] = pointer, indices
            with path.open("wb") as handle:
                np.savez_compressed(
                    handle,
                    ids=arrays["ids"],
                    day=arrays["day"],
                    stage=arrays["stage"],
                    survey=arrays["survey"],
                    level=arrays["level"],
                    cites_ptr=arrays["cites_ptr"],
                    cites_idx=arrays["cites_idx"],
                    refs_ptr=arrays["refs_ptr"],
                    refs_idx=arrays["refs_idx"],
                )
        finally:
            for array in maps:
                array.flush()
                mapping = getattr(array, "_mmap", None)
                if mapping is not None:
                    mapping.close()
            connection.execute("DROP TABLE graph_pairs")
            connection.execute("DROP TABLE graph_nodes")
    return edges
