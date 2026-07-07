"""PG + pgvector retrieval store: the serve-side data access that replaces the Neo4j session.

Graph *algorithms* (PPR, eras, main-path, tensions) stay in Python (pagerank.py / subgraph.py);
this only performs the DB fetches the Cypher used to do, against the single project Postgres:

  - vector_pool / vector_pool_recent : pgvector cosine KNN (HNSW), optional year filter
  - lexical_pool                     : tsvector full-text over titles (the RRF lexical arm)
  - edges_among                      : CITES edges with both endpoints in an id set
  - ancestors                        : most-cited one-hop-back papers (lineage recovery)
  - drill                            : leaf members with a CITES edge to the pool, by similarity
  - recent_members                   : leaf members >= year, by similarity (recency inject)
  - abstracts                        : abstract text by arxiv_id (replaces the SQLite join)

Citations are stored by integer paper id; callers work in arxiv_id strings, so the edge methods
map arxiv_id<->id through the `paper` table once per call.
"""

from __future__ import annotations

from typing import Any, LiteralString, cast

import psycopg

from subgraph import PoolNode


def _vec(qvec: list[float]) -> str:
    """pgvector text literal for a query vector."""
    return "[" + ",".join(repr(float(x)) for x in qvec) + "]"


def _node(r: tuple[Any, ...]) -> PoolNode:
    """Row (arxiv_id, title, year, category, sim) -> PoolNode."""
    return PoolNode(
        arxiv_id=str(r[0]),
        title=str(r[1] or ""),
        year=int(r[2]) if r[2] is not None else None,
        category=str(r[3]) if r[3] is not None else None,
        score=float(r[4]),
    )


class Store:
    conn: psycopg.Connection[tuple[Any, ...]]
    emb_table: str
    emb_col: str

    def __init__(self, dsn: str, emb_space: str = "sym") -> None:
        self.conn = psycopg.connect(dsn, autocommit=True)
        # hot-swap the embedding space by TABLE: asym lives in a separate paper_embedding_asym
        # (filling a 2nd column on paper_embedding rewrites every row -> forces sym-HNSW
        # maintenance per row -> pathologically slow). Both tables are (arxiv_id, <vec>) so the
        # downstream paper/paper_meta joins are identical.
        if emb_space == "asym":
            self.emb_table, self.emb_col = "paper_embedding_asym", "embedding_asym"
        else:
            self.emb_table, self.emb_col = "paper_embedding", "embedding"
        # pgvector HNSW returns at most hnsw.ef_search rows regardless of LIMIT; the default
        # (40) silently truncated every KNN below its LIMIT. 1000 is the parameter's maximum.
        _ = self.conn.execute("SET hnsw.ef_search = 1000")

    def close(self) -> None:
        self.conn.close()

    # --- id mapping -------------------------------------------------------
    def _ids_for(self, arxiv_ids: list[str]) -> dict[str, int]:
        rows: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT arxiv_id, id FROM paper WHERE arxiv_id = ANY(%s)", (arxiv_ids,)
        ).fetchall()
        return {str(a): int(i) for a, i in rows}

    def global_citations(self, arxiv_ids: list[str]) -> dict[str, int]:
        """Corpus-wide citation count per paper (global popularity, for the hub-specificity penalty)."""
        idmap = self._ids_for(arxiv_ids)
        inv = {i: a for a, i in idmap.items()}
        if not idmap:
            return {}
        rows: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT cited_id, count(*) FROM citation WHERE cited_id = ANY(%s) GROUP BY cited_id",
            (list(idmap.values()),),
        ).fetchall()
        return {inv[int(c)]: int(n) for c, n in rows if int(c) in inv}

    # --- vector pools -----------------------------------------------------
    def vector_pool(self, qvec: list[float], n: int) -> dict[str, PoolNode]:
        """Top-`n` papers by cosine similarity (HNSW), keyed by arxiv_id."""
        v = _vec(qvec)
        q = (
            f"SELECT e.arxiv_id, m.title, m.year, m.primary_category, "
            f"1 - (e.{self.emb_col} <=> %s::halfvec) "
            f"FROM {self.emb_table} e JOIN paper_meta m USING (arxiv_id) "
            f"ORDER BY e.{self.emb_col} <=> %s::halfvec LIMIT %s"
        )
        rows: list[tuple[Any, ...]] = self.conn.execute(
            cast(LiteralString, q), (v, v, n)
        ).fetchall()
        return {str(r[0]): _node(r) for r in rows}

    def vector_pool_recent(
        self, qvec: list[float], year_min: int, probe: int
    ) -> list[PoolNode]:
        """The `probe` nearest papers, then keep those with year >= `year_min`.

        Mirrors the Cypher `queryNodes(probe)` + year filter so frontier_select can pick
        newest-cohort-first downstream — leaf-independent, the only path for leaf-less work.
        """
        v = _vec(qvec)
        q = (
            f"SELECT k.arxiv_id, m.title, m.year, m.primary_category, k.sim FROM "
            f"(SELECT arxiv_id, 1 - ({self.emb_col} <=> %s::halfvec) AS sim "
            f" FROM {self.emb_table} ORDER BY {self.emb_col} <=> %s::halfvec LIMIT %s) k "
            f"JOIN paper_meta m USING (arxiv_id) "
            f"WHERE m.year >= %s ORDER BY k.sim DESC"
        )
        rows: list[tuple[Any, ...]] = self.conn.execute(
            cast(LiteralString, q), (v, v, probe, year_min)
        ).fetchall()
        return [_node(r) for r in rows]

    # --- lexical pool -----------------------------------------------------
    def lexical_pool(self, query: str, k: int) -> list[PoolNode]:
        """Top-`k` papers by tsvector rank over titles (the RRF lexical arm)."""
        rows: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT m.arxiv_id, m.title, m.year, m.primary_category, "
            "ts_rank(to_tsvector('english', coalesce(m.title, '')), q) AS r "
            "FROM paper_meta m, plainto_tsquery('english', %s) q "
            "WHERE to_tsvector('english', coalesce(m.title, '')) @@ q "
            "ORDER BY r DESC LIMIT %s",
            (query, k),
        ).fetchall()
        return [_node(r) for r in rows]

    # --- graph fetches ----------------------------------------------------
    def edges_among(self, arxiv_ids: list[str]) -> list[tuple[str, str, Any, Any]]:
        """Raw (src, dst, intent, polarity) for CITES edges with both ends in the set."""
        idmap = self._ids_for(arxiv_ids)
        if not idmap:
            return []
        rev = {i: a for a, i in idmap.items()}
        ints = list(idmap.values())
        rows: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT citing_id, cited_id, intent, polarity FROM citation "
            "WHERE citing_id = ANY(%s) AND cited_id = ANY(%s)",
            (ints, ints),
        ).fetchall()
        out: list[tuple[str, str, Any, Any]] = []
        for citing, cited, intent, polarity in rows:
            s, d = rev.get(int(citing)), rev.get(int(cited))
            if s is not None and d is not None:
                out.append((s, d, intent, polarity))
        return out

    def ancestors(
        self,
        pool_ids: list[str],
        qvec: list[float],
        max_add: int,
        min_citers: int,
        category_prefix: str | None,
    ) -> list[PoolNode]:
        """Most-cited one-hop-back papers (by # distinct pool citers), scored by similarity."""
        idmap = self._ids_for(pool_ids)
        if not idmap:
            return []
        anc: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT cited_id, count(DISTINCT citing_id) AS pc FROM citation "
            "WHERE citing_id = ANY(%s) AND cited_id IS NOT NULL "
            "GROUP BY cited_id HAVING count(DISTINCT citing_id) >= %s "
            "ORDER BY pc DESC LIMIT %s",
            (list(idmap.values()), min_citers, max_add),
        ).fetchall()
        if not anc:
            return []
        anc_int = [int(r[0]) for r in anc]
        v = _vec(qvec)
        cat = f"{category_prefix}%" if category_prefix else None
        clause = "AND m.primary_category LIKE %s " if cat else ""
        params: list[Any] = [v, anc_int]
        if cat:
            params.append(cat)
        q = (
            f"SELECT p.arxiv_id, m.title, m.year, m.primary_category, "
            f"1 - (e.{self.emb_col} <=> %s::halfvec) "
            f"FROM paper p JOIN paper_meta m ON m.arxiv_id = p.arxiv_id "
            f"JOIN {self.emb_table} e ON e.arxiv_id = p.arxiv_id "
            f"WHERE p.id = ANY(%s) {clause}"
        )
        rows: list[tuple[Any, ...]] = self.conn.execute(
            cast(LiteralString, q), tuple(params)
        ).fetchall()
        return [_node(r) for r in rows]

    def drill(
        self, cand: list[str], pool: list[str], qvec: list[float], limit: int
    ) -> list[PoolNode]:
        """Candidate leaf members with a CITES edge to the pool, scored by similarity."""
        if limit <= 0 or not cand:
            return []
        ids = self._ids_for(cand + pool)
        cand_i = [ids[a] for a in cand if a in ids]
        pool_i = [ids[a] for a in pool if a in ids]
        if not cand_i or not pool_i:
            return []
        hit: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT DISTINCT a FROM ("
            "  SELECT citing_id AS a FROM citation WHERE citing_id = ANY(%s) AND cited_id = ANY(%s)"
            "  UNION"
            "  SELECT cited_id AS a FROM citation WHERE cited_id = ANY(%s) AND citing_id = ANY(%s)"
            ") t",
            (cand_i, pool_i, cand_i, pool_i),
        ).fetchall()
        hit_ids = [int(r[0]) for r in hit]
        if not hit_ids:
            return []
        v = _vec(qvec)
        q = (
            f"SELECT p.arxiv_id, m.title, m.year, m.primary_category, "
            f"1 - (e.{self.emb_col} <=> %s::halfvec) AS sim "
            f"FROM paper p JOIN paper_meta m ON m.arxiv_id = p.arxiv_id "
            f"JOIN {self.emb_table} e ON e.arxiv_id = p.arxiv_id "
            f"WHERE p.id = ANY(%s) ORDER BY sim DESC LIMIT %s"
        )
        rows: list[tuple[Any, ...]] = self.conn.execute(
            cast(LiteralString, q), (v, hit_ids, limit)
        ).fetchall()
        return [_node(r) for r in rows]

    def recent_members(
        self, cand: list[str], qvec: list[float], year_min: int
    ) -> list[PoolNode]:
        """Leaf members with year >= `year_min`, scored by similarity (recency inject)."""
        if not cand:
            return []
        v = _vec(qvec)
        q = (
            f"SELECT m.arxiv_id, m.title, m.year, m.primary_category, "
            f"1 - (e.{self.emb_col} <=> %s::halfvec) "
            f"FROM paper_meta m JOIN {self.emb_table} e USING (arxiv_id) "
            f"WHERE m.arxiv_id = ANY(%s) AND m.year >= %s"
        )
        rows: list[tuple[Any, ...]] = self.conn.execute(
            cast(LiteralString, q), (v, cand, year_min)
        ).fetchall()
        return [_node(r) for r in rows]

    # --- text -------------------------------------------------------------
    def abstracts(self, arxiv_ids: list[str]) -> dict[str, str]:
        """Abstract text by arxiv_id (replaces the SQLite publication join)."""
        if not arxiv_ids:
            return {}
        rows: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT arxiv_id, abstract FROM paper_meta WHERE arxiv_id = ANY(%s)",
            (arxiv_ids,),
        ).fetchall()
        return {str(a): str(ab or "") for a, ab in rows}

    def authors(self, arxiv_ids: list[str]) -> dict[str, str]:
        """Raw comma-separated author string by arxiv_id (for the bibliography)."""
        if not arxiv_ids:
            return {}
        rows: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT arxiv_id, authors FROM paper_meta"
            " WHERE arxiv_id = ANY(%s) AND authors IS NOT NULL",
            (arxiv_ids,),
        ).fetchall()
        return {str(a): str(au) for a, au in rows}

    def embeddings(self, arxiv_ids: list[str]) -> dict[str, list[float]]:
        """Raw embedding vectors by arxiv_id (current emb space) — for set-selection math."""
        if not arxiv_ids:
            return {}
        q = (
            f"SELECT arxiv_id, {self.emb_col}::text FROM {self.emb_table} "
            f"WHERE arxiv_id = ANY(%s)"
        )
        rows: list[tuple[Any, ...]] = self.conn.execute(
            cast(LiteralString, q), (arxiv_ids,)
        ).fetchall()
        out: dict[str, list[float]] = {}
        for aid, txt in rows:
            out[str(aid)] = [float(x) for x in str(txt).strip("[]").split(",")]
        return out

    def meta_for(self, arxiv_id: str) -> tuple[str, int | None, str | None, str] | None:
        """(title, year, category, abstract) for one paper, or None if unknown (seed lookup)."""
        row: tuple[Any, ...] | None = self.conn.execute(
            "SELECT title, year, primary_category, abstract FROM paper_meta"
            " WHERE arxiv_id = %s",
            (arxiv_id,),
        ).fetchone()
        if row is None:
            return None
        return (
            str(row[0] or ""),
            int(row[1]) if row[1] is not None else None,
            str(row[2]) if row[2] is not None else None,
            str(row[3] or ""),
        )

    # --- existence check (narrate id verification) ------------------------
    def existing(self, arxiv_ids: list[str]) -> set[str]:
        """Subset of `arxiv_ids` present in the corpus (paper table)."""
        if not arxiv_ids:
            return set()
        rows: list[tuple[Any, ...]] = self.conn.execute(
            "SELECT arxiv_id FROM paper WHERE arxiv_id = ANY(%s)", (arxiv_ids,)
        ).fetchall()
        return {str(r[0]) for r in rows}
