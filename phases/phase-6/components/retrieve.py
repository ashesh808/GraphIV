"""Step 6 — the thin RAG path: embed a query, find seed papers via the native
vector index, then expand an intent-labeled CITES subtree with Cypher.

No LLM yet — this is the retrieval plumbing the narrative layer will sit on.

Query embedding MUST use the same nomic model + prompt prefix the documents were
encoded with (see _common.NOMIC_PROMPT), or query/doc vectors won't be comparable.
Docs were encoded as "Title: {title}\nAbstract: {abstract}"; the query is the bare
topic (asymmetric query->doc retrieval). Only the nomic set is indexed in Neo4j.
"""

from __future__ import annotations

import sqlite3
from typing import Any, LiteralString, cast

from _common import (  # noqa: E402
    NEO4J_DB,
    NOMIC_MAX_SEQ,
    NOMIC_MODEL,
    NOMIC_PROMPT,
    SQLITE_DB,
    VECTOR_INDEX,
    neo4j_driver,
)

_MODEL: Any = None


def _get_model() -> Any:
    """Lazy-load the nomic SentenceTransformer onto CUDA (cached)."""
    global _MODEL
    if _MODEL is None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[retrieve] loading nomic on {device} ...", flush=True)
        _MODEL = SentenceTransformer(
            str(NOMIC_MODEL), trust_remote_code=True, device=device
        )
        _MODEL.max_seq_length = NOMIC_MAX_SEQ
    return _MODEL


def free_model() -> None:
    """Release the embedding model + CUDA cache (to hand VRAM back to Gemma)."""
    global _MODEL
    if _MODEL is not None:
        import torch

        del _MODEL
        _MODEL = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def embed_query(text: str) -> list[float]:
    """Encode a query into the document embedding space (normalized, 768D)."""
    vec = _get_model().encode(
        [text],
        prompt=NOMIC_PROMPT,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]
    return [float(x) for x in vec]


def retrieve_and_expand(
    question: str,
    k: int = 10,
    hops: int = 2,
    direction: str = "out",
    intents: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Vector-retrieve `k` seed papers, then expand a CITES subtree.

    direction: 'out' = papers the seeds build on (seed -> cited);
               'in'  = papers building on the seeds (citing -> seed);
               'both'.
    intents: if given, only traverse CITES edges whose intent is in the list.
    """
    hops = max(1, int(hops))  # bound must be a literal in Cypher
    arrow = {
        "out": "-[c:CITES*1..%d]->",
        "in": "<-[c:CITES*1..%d]-",
        "both": "-[c:CITES*1..%d]-",
    }
    rel = arrow[direction] % hops
    intent_filter = (
        " WHERE all(r IN relationships(path) WHERE r.intent IN $intents)"
        if intents
        else ""
    )
    qvec = embed_query(question)

    seed_q = (
        f"CALL db.index.vector.queryNodes('{VECTOR_INDEX}', $k, $qvec) YIELD node, score "
        "RETURN node.arxiv_id AS arxiv_id, node.title AS title, "
        "node.year AS year, node.primary_category AS category, score "
        "ORDER BY score DESC"
    )
    expand_q = (
        f"CALL db.index.vector.queryNodes('{VECTOR_INDEX}', $k, $qvec) YIELD node "
        f"MATCH path = (node){rel}(m:Paper){intent_filter} "
        "WITH node, relationships(path) AS rels, m "
        "UNWIND rels AS c "
        "RETURN DISTINCT startNode(c).arxiv_id AS src, endNode(c).arxiv_id AS dst, "
        "c.intent AS intent, c.polarity AS polarity, c.intent_score AS intent_score "
        "LIMIT 500"
    )

    with neo4j_driver() as drv, drv.session(database=NEO4J_DB) as session:
        # cast: query is an f-string over internal constants, not user input
        seed_rows = session.run(cast(LiteralString, seed_q), k=k, qvec=qvec)
        edge_rows = session.run(
            cast(LiteralString, expand_q), k=k, qvec=qvec, intents=intents
        )
        seeds = [dict(r) for r in seed_rows]
        edges = [dict(r) for r in edge_rows]
    return {"seeds": seeds, "edges": edges}


def fetch_abstracts(arxiv_ids: list[str]) -> dict[str, str]:
    """Pull abstracts from SQLite by arxiv_id (the lean-store join back to text)."""
    if not arxiv_ids:
        return {}
    conn = sqlite3.connect(f"file:{SQLITE_DB}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" * len(arxiv_ids))
        rows = conn.execute(
            f"SELECT id, abstract FROM publication WHERE id IN ({placeholders})",
            arxiv_ids,
        ).fetchall()
    finally:
        conn.close()
    return {axid: (abs or "") for axid, abs in rows}
