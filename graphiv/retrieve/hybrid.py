"""
Fuse the vector and lexical pools by reciprocal rank, then anchor to the dominant field

The category anchor is the validated fix for a polysemous query hijacking the wrong field
"""

from __future__ import annotations

from collections import Counter

from graphiv.core.models import PoolNode
from graphiv.core.store import Store
from graphiv.retrieve.subgraph import topical_pool

RRF_K = 60


def group_of(cat: str | None) -> str:
    """
    ArXiv category group/archive: 'cond-mat.mes-hall' -> 'cond-mat'
    """
    return (cat or "").split(".")[0]


def dominant_group(pool: dict[str, PoolNode], top_k: int = 30) -> str | None:
    """
    The arXiv group most common among the top-scoring pool papers
    """
    top = sorted(pool.values(), key=lambda n: n.score, reverse=True)[:top_k]
    c = Counter(group_of(n.category) for n in top if n.category)
    return c.most_common(1)[0][0] if c else None


def hybrid_pool(
    store: Store, qvec: list[float], query: str, n_pool: int, k_lexical: int = 400
) -> dict[str, PoolNode]:
    """
    Vector ∪ lexical pools fused by RRF; `.score` becomes the fused rank score
    """
    vec = topical_pool(store, qvec, n_pool)
    lex = store.lexical_pool(query, k_lexical)
    rank_v = {aid: i for i, aid in enumerate(sorted(vec, key=lambda a: vec[a].score, reverse=True))}
    rank_l = {n.arxiv_id: i for i, n in enumerate(lex)}
    nodes: dict[str, PoolNode] = {n.arxiv_id: n for n in lex}
    nodes.update(vec)
    rrf: dict[str, float] = {}
    for aid in set(rank_v) | set(rank_l):
        s = 0.0
        if aid in rank_v:
            s += 1.0 / (RRF_K + rank_v[aid])
        if aid in rank_l:
            s += 1.0 / (RRF_K + rank_l[aid])
        rrf[aid] = s
    top = sorted(rrf, key=lambda a: rrf[a], reverse=True)[:n_pool]
    out: dict[str, PoolNode] = {}
    for aid in top:
        n = nodes[aid]
        out[aid] = PoolNode(n.arxiv_id, n.title, n.year, n.category, rrf[aid])
    return out
