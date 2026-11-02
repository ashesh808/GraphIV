"""
The first step, which picks the pool the rest of the pipeline works on

PostgreSQL retains the original approximate iterative HNSW scan
Local snapshots supply cosine-ranked rows through their FAISS corpus adapter
"""

from __future__ import annotations

from src.core.schema import Paper, Query
from src.storage.corpus import CorpusSource, open_corpus


class CosineRetriever:
    """
    Reads the top of the corpus by cosine, under the query's date cap
    """

    def __init__(self, pg_dest: CorpusSource, *, blocked: list[str] | None = None) -> None:
        """
        Holds the connection string and whatever the query may never return

        Args:
            pg_dest: A libpq connection string or corpus adapter.
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
        rows = open_corpus(self.pg_dest).search(query.emb, query.max_date, self.blocked, limit)
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
