"""
Reads the citation graph export into flat arrays a query can slice

Every array is keyed by one row number per paper, so a hop is a slice and never a query
The export is written by offline/citation_preprocess/stage2_export_graph.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

EPOCH = np.datetime64("1970-01-01")
DAY = np.timedelta64(1, "D")
EMPTY: NDArray[np.int32] = np.zeros(0, np.int32)


def gather_rows(
    values: NDArray[np.int32], start: NDArray[np.int32], count: NDArray[np.int32]
) -> NDArray[np.int32]:
    """
    Concatenates one variable length run per row out of a flat array

    Args:
        values: The flat array the runs live in.
        start: Where each run begins.
        count: How long each run is.

    Returns:
        Every run end to end, empty when no row was asked for.
    """
    if not len(start):
        return EMPTY
    return np.concatenate([values[a : a + c] for a, c in zip(start, count, strict=True)])


@dataclass(frozen=True)
class GraphExport:
    """
    The citation graph and the per-paper columns a ranking reads at query time

    `cites` is indexed by the paper being cited and `refs` by the paper doing the citing.
    """

    ids: NDArray[np.bytes_]
    index: dict[str, int]
    day: NDArray[np.int32]
    stage: NDArray[np.int8]
    survey: NDArray[np.float32]
    level: NDArray[np.int8]
    cites_ptr: NDArray[np.int32]
    cites_idx: NDArray[np.int32]
    refs_ptr: NDArray[np.int32]
    refs_idx: NDArray[np.int32]

    @property
    def n_papers(self) -> int:
        """
        Papers in the export
        """
        return len(self.ids)

    def get_day_number(self, when: date | str) -> int:
        """
        A date as the integer this export stores

        Args:
            when: Anything numpy reads as a date.

        Returns:
            Days since the epoch.
        """
        return int((np.datetime64(when) - EPOCH) // DAY)

    def get_citing_papers(self, row: int) -> NDArray[np.int32]:
        """
        Every paper that cites paper `row`

        Args:
            row: A paper row.

        Returns:
            The citing rows.
        """
        return self.cites_idx[self.cites_ptr[row] : self.cites_ptr[row + 1]]

    def get_cited_papers(self, row: int) -> NDArray[np.int32]:
        """
        Every paper that paper `row` cites

        Args:
            row: A paper row.

        Returns:
            The cited rows.
        """
        return self.refs_idx[self.refs_ptr[row] : self.refs_ptr[row + 1]]

    def get_citation_counts(self) -> NDArray[np.int32]:
        """
        Distinct citers per paper, over the whole export

        Returns:
            One count per paper.
        """
        return np.diff(self.cites_ptr).astype(np.int32)

    def get_citation_counts_before(
        self, rows: NDArray[np.int32], cutoff: int, blocked: NDArray[np.int32] | None = None
    ) -> NDArray[np.float64]:
        """
        Citations each paper held at a cutoff, which is what the hub denominator divides by

        Counting to today would let a case be helped by a citation that had not happened yet.

        Args:
            rows: The papers to count.
            cutoff: The latest day a citer may carry.
            blocked: Papers never counted as a citer, usually the case's own surveys.

        Returns:
            One count per row.
        """
        start = self.cites_ptr[rows]
        count = self.cites_ptr[rows + 1] - start
        citers = gather_rows(self.cites_idx, start, count)
        out = np.zeros(len(rows))
        if not len(citers):
            return out
        before = self.day[citers] <= cutoff
        if blocked is not None and len(blocked):
            before &= ~np.isin(citers, blocked)
        edges = np.zeros(len(rows) + 1, np.int64)
        edges[1:] = np.cumsum(count)
        live = np.flatnonzero(count)
        out[live] = np.add.reduceat(before.astype(np.int64), edges[:-1][live])
        return out

    def get_neighbors(
        self, rows: NDArray[np.int32], forward: bool, limit: int
    ) -> NDArray[np.int32]:
        """
        One citation hop off a set of papers, keeping the neighbors the most of them reached

        Args:
            rows: The papers to hop from.
            forward: True walks to papers that cite `rows`, False to papers `rows` cite.
            limit: The most neighbors to keep.

        Returns:
            Neighbor rows, most reached first.
        """
        if not len(rows):
            return EMPTY
        ptr, idx = (self.cites_ptr, self.cites_idx) if forward else (self.refs_ptr, self.refs_idx)
        start = ptr[rows]
        reached = gather_rows(idx, start, ptr[rows + 1] - start)
        if not len(reached):
            return EMPTY
        uniq, hits = np.unique(reached, return_counts=True)
        if len(uniq) <= limit:
            return uniq[np.argsort(-hits)].astype(np.int32)
        keep = np.argpartition(-hits, limit)[:limit]
        return uniq[keep][np.argsort(-hits[keep])].astype(np.int32)

    def walk_one_step(self, weights: NDArray[np.float64], forward: bool) -> NDArray[np.float64]:
        """
        One weighted step along the whole graph, which is what a channel is built from

        Args:
            weights: A weight per paper.
            forward: True walks to papers that cite the weighted set, False to what it cites.

        Returns:
            One value per paper.
        """
        ptr, idx = (self.refs_ptr, self.refs_idx) if forward else (self.cites_ptr, self.cites_idx)
        out = np.zeros(self.n_papers)
        live = np.flatnonzero(np.diff(ptr))
        if not len(live):
            return out
        out[live] = np.add.reduceat(weights[idx], ptr[:-1][live].astype(np.int64))
        return out


def load_graph_export(path: str | Path) -> GraphExport:
    """
    Reads the export off disk

    Args:
        path: The archive written by stage2_export_graph.py.

    Returns:
        The graph, with the id to row map already built.
    """
    with np.load(Path(path)) as archive:
        arrays = {name: archive[name] for name in archive.files}
    ids: NDArray[np.bytes_] = arrays["ids"]
    return GraphExport(
        ids=ids,
        index={a.decode(): i for i, a in enumerate(ids)},
        day=arrays["day"],
        stage=arrays["stage"],
        survey=arrays["survey"],
        level=arrays["level"],
        cites_ptr=arrays["cites_ptr"],
        cites_idx=arrays["cites_idx"],
        refs_ptr=arrays["refs_ptr"],
        refs_idx=arrays["refs_idx"],
    )
