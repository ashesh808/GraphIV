"""Production hybrid retrieval: fuse the vector pool with a lexical (BM25 over
titles) pool by reciprocal-rank fusion, then category-anchor to the dominant
field of the top seeds. This is the validated fix for polysemous-query hijack
(spintronics -> cond-mat not particle-physics; photonic IC -> physics.optics not
quantum optics). Promoted from the kg_rag_lab experiments.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from neo4j import Session

from subgraph import PoolNode, topical_pool

LEXICAL_INDEX = "paper_title"
RRF_K = 60


def group_of(cat: str | None) -> str:
    """arXiv category group/archive: 'cond-mat.mes-hall' -> 'cond-mat'."""
    return (cat or "").split(".")[0]


def dominant_group(pool: dict[str, PoolNode], top_k: int = 30) -> str | None:
    top = sorted(pool.values(), key=lambda n: n.score, reverse=True)[:top_k]
    c = Counter(group_of(n.category) for n in top if n.category)
    return c.most_common(1)[0][0] if c else None


def lexical_pool(session: Session, query: str, k: int) -> list[PoolNode]:
    cypher = (
        f"CALL db.index.fulltext.queryNodes('{LEXICAL_INDEX}', $q) YIELD node, score "
        "RETURN node.arxiv_id AS arxiv_id, node.title AS title, node.year AS year, "
        "node.primary_category AS category, score ORDER BY score DESC LIMIT $k"
    )
    out: list[PoolNode] = []
    for rec in session.run(cypher, q=query, k=k):  # pyright: ignore[reportArgumentType]
        row: dict[str, Any] = dict(rec)
        yr: Any = row["year"]  # pyright: ignore[reportAny]
        out.append(
            PoolNode(
                arxiv_id=str(row["arxiv_id"]),  # pyright: ignore[reportAny]
                title=str(row["title"] or ""),  # pyright: ignore[reportAny]
                year=int(yr) if yr is not None else None,
                category=(
                    str(row["category"]) if row["category"] is not None else None
                ),  # pyright: ignore[reportAny]
                score=float(row["score"]),  # pyright: ignore[reportAny]
            )
        )
    return out


def hybrid_pool(
    session: Session, qvec: list[float], query: str, n_pool: int, k_lexical: int = 400
) -> dict[str, PoolNode]:
    """Vector ∪ lexical pools fused by RRF; `.score` becomes the fused rank score."""
    vec = topical_pool(session, qvec, n_pool)
    lex = lexical_pool(session, query, k_lexical)
    rank_v = {
        aid: i
        for i, aid in enumerate(sorted(vec, key=lambda a: vec[a].score, reverse=True))
    }
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
