"""
The first step, which picks the pool the rest of the pipeline works on

The seed is approximate, and an iterative index scan holds 198 of the exact top 200
It costs a twentieth of the exact scan it replaces
"""

from __future__ import annotations

import psycopg
from psycopg import sql

from src.core.schema import Paper, Query

SEED = """
SELECT arxiv_id, title, abstract, date, 1 - (embed_full <=> %s::halfvec)
FROM papers
WHERE stage >= 3 AND (%s::date IS NULL OR date <= %s) AND NOT (arxiv_id = ANY(%s))
ORDER BY embed_full <=> %s::halfvec LIMIT %s
"""

# pgvector returns at most ef_search rows whatever the LIMIT says, and iterative scan lifts that
EF_SEARCH = 1000
MAX_SCAN_TUPLES = 200000


class CosineRetriever:
    """
    Reads the top of the corpus by cosine, under the query's date cap
    """

    def __init__(self, pg_dest: str, *, blocked: list[str] | None = None) -> None:
        """
        Holds the connection string and whatever the query may never return

        Args:
            pg_dest: libpq connection string, used once per call.
            blocked: Papers this query must never retrieve, such as an eval case's own surveys.
        """
        self.pg_dest = pg_dest
        self.blocked = blocked or []

    def retrieve(self, query: Query, limit: int) -> list[Paper]:
        """
        Returns the highest `limit` papers by cosine, best first

        Args:
            query: The embedded question.
            limit: The most papers to return.

        Returns:
            At most `limit` papers, every field filled.
        """
        vector = "[" + ",".join(f"{x:.6f}" for x in query.emb) + "]"
        cap = query.max_date
        with psycopg.connect(self.pg_dest) as conn:
            _ = conn.execute(sql.SQL("SET hnsw.ef_search = {}").format(EF_SEARCH))
            _ = conn.execute(sql.SQL("SET hnsw.max_scan_tuples = {}").format(MAX_SCAN_TUPLES))
            _ = conn.execute("SET hnsw.iterative_scan = relaxed_order")
            rows = conn.execute(SEED, (vector, cap, cap, self.blocked, vector, limit)).fetchall()
        return [
            Paper(
                arxiv_id=str(a),
                title=str(t or ""),
                abstract=str(abstract or ""),
                date=when,
                cosine=float(cosine),
            )
            for a, t, abstract, when, cosine in rows
        ]
