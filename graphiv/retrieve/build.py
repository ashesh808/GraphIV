"""
Builds a retriever from three stage names, so a configuration is data rather than code

Presets keep the older single `rank` flag working by expanding it to a triple
"""

from __future__ import annotations

import time

from graphiv.retrieve.api import (
    Pool,
    PoolBuilder,
    Query,
    Reader,
    Retrieved,
    Selection,
    Selector,
)
from graphiv.retrieve.pools import POOLS
from graphiv.retrieve.readers import READERS
from graphiv.retrieve.select import SELECTORS, NamedSelector

# the older --set-rank values, each expanded to (pool, reader, selector)
PRESETS: dict[str, tuple[str, str, str]] = {
    "joint": ("graph", "llm", "joint"),
    "ppr": ("graph", "llm", "ppr"),
    "frontier": ("graph", "llm", "frontier"),
    "trajectory": ("graph", "llm", "trajectory"),
    "indegree": ("graph", "llm", "indegree"),
    "dense": ("vector", "null", "topk"),
    "llmfree": ("graph", "constant", "frontier"),
}


class Pipeline:
    """
    A pool builder, a reader and a selector run in that order
    """

    def __init__(self, pool: PoolBuilder, reader: Reader, selector: Selector) -> None:
        self.pool = pool
        self.reader = reader
        self.selector = selector
        self.name = f"{pool.name}+{reader.name}+{selector.name}"

    def retrieve(self, q: Query) -> Retrieved:
        """
        Build the pool, grade it, spend the budget, and record what each stage cost

        Args:
            q: the question, budget and corpus clock.

        Returns:
            The ranked cohort plus the pool, graph and grades behind it.
        """
        t0 = time.time()
        pool: Pool = self.pool.build(q)
        t1 = time.time()
        grades = self.reader.grade(q, pool)
        t2 = time.time()
        papers = self.selector.select(Selection(pool.nodes, pool.edges, q.budget, pool.fr, grades))
        trace = {
            "pool": float(len(pool.nodes)),
            "edges": float(len(pool.edges)),
            "graded": float(len(grades)),
            "pool_seconds": round(t1 - t0, 2),
            "read_seconds": round(t2 - t1, 2),
            "select_seconds": round(time.time() - t2, 2),
        }
        return Retrieved(papers, pool.nodes, pool.edges, pool.fr, grades, pool.leaf, trace)


def build(pool: str, reader: str, selector: str, n_pool: int = 400) -> Pipeline:
    """
    Assemble a retriever from registry names

    Args:
        pool: a key of `POOLS`.
        reader: a key of `READERS`.
        selector: a key of `SELECTORS`.
        n_pool: candidate width handed to the pool builder.

    Returns:
        A Pipeline satisfying the Retriever protocol.

    Raises:
        KeyError: if any name is not registered.
    """
    for name, table in ((pool, POOLS), (reader, READERS), (selector, SELECTORS)):
        if name not in table:
            raise KeyError(f"unknown stage {name!r}, have {sorted(table)}")
    return Pipeline(POOLS[pool](n_pool), READERS[reader](), NamedSelector(selector))


def from_preset(rank: str, n_pool: int = 400) -> Pipeline:
    """
    Build the triple an older `rank` value stands for

    Args:
        rank: a key of `PRESETS`.
        n_pool: candidate width handed to the pool builder.

    Returns:
        A Pipeline satisfying the Retriever protocol.

    Raises:
        KeyError: if the preset is unknown.
    """
    if rank not in PRESETS:
        raise KeyError(f"unknown preset {rank!r}, have {sorted(PRESETS)}")
    return build(*PRESETS[rank], n_pool=n_pool)
