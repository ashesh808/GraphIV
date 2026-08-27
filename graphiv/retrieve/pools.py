"""
Pool builders: the candidate sets a selector can choose from

GraphPool is the production path; the flat builders exist so a baseline is the same type
A flat pool carries no edges, so any graph signal over it is zero rather than undefined
"""

from __future__ import annotations

import time

from graphiv.core.embed import embed_query
from graphiv.core.models import PoolNode
from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store
from graphiv.retrieve.api import Pool, Query
from graphiv.retrieve.hybrid import hybrid_pool
from graphiv.retrieve.recency import FrontierSpec, detect_frontier
from graphiv.retrieve.refined import frontier_pull, refined_pool
from graphiv.retrieve.subgraph import augment_with_ancestors, induce_subgraph, topical_pool
from graphiv.retrieve.topic_anchor import TopicTree

EMBED_MODE = "asym"
RECENCY = 0.4
DRILL_TARGET = 280
ANCESTOR_MAX = 120

# measured in 02-02: 0.25 to 0.35 is a plateau and 0.40 starts cutting foundational work
ANCESTOR_FLOOR = 0.30


def _store(q: Query) -> Store:
    return Store(PG_DSN, emb_space=EMBED_MODE, max_yymm=q.max_yymm, exclude=q.exclude)


def _frontier(nodes: dict[str, PoolNode], q: Query) -> FrontierSpec:
    years = [n.year for n in nodes.values() if n.year is not None]
    return detect_frontier(years, q.now.year, q.now.month, q.budget, RECENCY)


class GraphPool:
    """
    The production path: hybrid channels, topic anchor, drill, frontier pull, ancestors

        The topic anchor and the drill are what carry a pool when the vector channel is
        weak, which is why the pool survives a truncated KNN.
    """

    name = "graph"

    def __init__(self, n_pool: int = 400, no_cluster: bool = False, no_pull: bool = False) -> None:
        self.n_pool = n_pool
        self.no_cluster = no_cluster
        self.no_pull = no_pull
        self.tree = TopicTree()

    def build(self, q: Query) -> Pool:
        """
        Assemble the candidate set and induce the citation graph over it
        """
        t0 = time.time()
        store = _store(q)
        try:
            qvec = embed_query(q.text, mode=EMBED_MODE)
            nodes = hybrid_pool(store, qvec, q.text, self.n_pool)
            if q.seed:
                meta = store.meta_for(q.seed)
                if meta is not None:
                    title, year, cat, _ = meta
                    nodes[q.seed] = PoolNode(q.seed, title, year, cat, 1.0)
            fr = _frontier(nodes, q)
            leaf: str | None = None
            if not self.no_cluster:
                nodes, leaf, _ = refined_pool(
                    store, qvec, nodes, self.tree, fr.frontier_year, target=DRILL_TARGET
                )
            if not self.no_pull:
                nodes.update(
                    frontier_pull(store, qvec, fr.frontier_year, want=max(40, fr.recent_floor))
                )
            _ = augment_with_ancestors(
                store, nodes, qvec, max_add=ANCESTOR_MAX, min_cosine=ANCESTOR_FLOOR
            )
            edges = induce_subgraph(store, list(nodes))
        finally:
            store.close()
        _ = time.time() - t0
        return Pool(nodes, edges, fr, leaf)


class VectorPool:
    """
    Nearest neighbours only, the flat dense baseline the LitSearch protocol compares
    """

    name = "vector"

    def __init__(self, n_pool: int = 400, graph: bool = False) -> None:
        self.n_pool = n_pool
        self.graph = graph

    def build(self, q: Query) -> Pool:
        """
        Top-`n_pool` by cosine, with the citation graph induced only when asked
        """
        store = _store(q)
        try:
            nodes = topical_pool(store, embed_query(q.text, mode=EMBED_MODE), self.n_pool)
            edges = induce_subgraph(store, list(nodes)) if self.graph else []
        finally:
            store.close()
        return Pool(nodes, edges, _frontier(nodes, q))


class LexicalPool:
    """
    Title tsvector only, kept as the other half of the documented hybrid
    """

    name = "lexical"

    def __init__(self, n_pool: int = 400) -> None:
        self.n_pool = n_pool

    def build(self, q: Query) -> Pool:
        """
        Top-`n_pool` by title rank, with no graph
        """
        store = _store(q)
        try:
            hits = store.lexical_pool(q.text, self.n_pool)
        finally:
            store.close()
        nodes = {n.arxiv_id: n for n in hits}
        return Pool(nodes, [], _frontier(nodes, q))


POOLS: dict[str, type[GraphPool] | type[VectorPool] | type[LexicalPool]] = {
    "graph": GraphPool,
    "vector": VectorPool,
    "lexical": LexicalPool,
}
