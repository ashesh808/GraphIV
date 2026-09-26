"""
An eight paper citation graph small enough to check every number by hand

p0 and p1 are the core, p4 and p5 are what they cite, p3 is what cites them, p7 is two hops out
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from src.core.parse_graph_export import GraphExport, load_graph_export
from src.core.schema import Paper

#      p0 -> p4, p5      p1 -> p4      p2 -> p5, p6      p3 -> p0, p1      p7 -> p3
EDGES = ((0, 4), (0, 5), (1, 4), (2, 5), (2, 6), (3, 0), (3, 1), (7, 3))
YEARS = (2020, 2021, 2021, 2022, 2018, 2018, 2019, 2023)
COSINE = (0.9, 0.8, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1)


def _csr(rows: list[int], cols: list[int], n: int) -> tuple[np.ndarray, np.ndarray]:
    """
    One direction of the graph as a pointer array and a flat neighbor array

    Args:
        rows: The paper each edge is keyed by.
        cols: The paper on the other end.
        n: How many papers there are.

    Returns:
        The pointer and index arrays.
    """
    order = np.argsort(np.array(rows), kind="stable")
    ptr = np.zeros(n + 1, np.int32)
    ptr[1:] = np.cumsum(np.bincount(np.array(rows), minlength=n))
    return ptr, np.array(cols, np.int32)[order]


@pytest.fixture(scope="session")
def export_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Writes the fixture graph in the format stage2_export_graph.py produces

    Args:
        tmp_path_factory: pytest's per-session temporary directory.

    Returns:
        The archive path.
    """
    n = len(YEARS)
    src = [s for s, _ in EDGES]
    tgt = [t for _, t in EDGES]
    cites_ptr, cites_idx = _csr(tgt, src, n)
    refs_ptr, refs_idx = _csr(src, tgt, n)
    path = tmp_path_factory.mktemp("graph") / "export.npy"
    with path.open("wb") as handle:
        np.savez(  # pyright: ignore[reportArgumentType]
            handle,
            ids=np.array([f"p{i}".encode() for i in range(n)], dtype="S4"),
            day=np.array(
                [
                    (np.datetime64(f"{y}-01-01") - np.datetime64("1970-01-01")).astype(int)
                    for y in YEARS
                ],
                np.int32,
            ),
            stage=np.full(n, 4, np.int8),
            survey=np.zeros(n, np.float32),
            level=np.zeros((n, 3), np.int8),
            cites_ptr=cites_ptr,
            cites_idx=cites_idx,
            refs_ptr=refs_ptr,
            refs_idx=refs_idx,
        )
    return path


@pytest.fixture(scope="session")
def graph(export_path: Path) -> GraphExport:
    """
    The fixture graph, loaded the way production loads it

    Args:
        export_path: Where the archive was written.

    Returns:
        The graph.
    """
    return load_graph_export(export_path)


@pytest.fixture
def pool() -> list[Paper]:
    """
    Every fixture paper as a filled Paper, with p0 and p1 carrying the top cosine

    Returns:
        Eight papers in row order.
    """
    return [
        Paper(
            arxiv_id=f"p{i}",
            title=f"title {i}",
            abstract=f"abstract {i}",
            date=date(YEARS[i], 1, 1),
            cosine=COSINE[i],
        )
        for i in range(len(YEARS))
    ]
