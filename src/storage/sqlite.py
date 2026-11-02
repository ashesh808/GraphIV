"""Read immutable SQLite metadata with optional normalized FAISS vector search."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from datetime import date
from functools import lru_cache
from heapq import heappush, heapreplace
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.storage.corpus import (
    CitingRow,
    DetailRow,
    EdgeRow,
    RecordRow,
    ScoredPaperRow,
    SeedRow,
    SuccessorRow,
    VectorRow,
)


@lru_cache(maxsize=128)
def _like_pattern(pattern: str) -> re.Pattern[str]:
    parts: list[str] = []
    escaped = False
    for char in pattern:
        if escaped:
            parts.append(re.escape(char))
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "%":
            parts.append(".*")
        elif char == "_":
            parts.append(".")
        else:
            parts.append(re.escape(char))
    if escaped:
        raise ValueError("An ILIKE pattern cannot end with an escape character")
    return re.compile("".join(parts), re.IGNORECASE | re.DOTALL)


def _ilike(pattern: str, value: str | None) -> int:
    return int(value is not None and _like_pattern(pattern).fullmatch(value) is not None)


def _ids(values: list[str] | list[int]) -> str:
    return json.dumps(values, ensure_ascii=False)


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None


class SQLiteCorpus:
    """A read-only schema-v1 snapshot, safe to reuse across request threads.

    Each operation opens its own read-only SQLite connection. FAISS indexes are
    read once and searched without mutation. Without an index, small local
    corpora use an exact scan of their stored vectors with the same filters.
    """

    def __init__(
        self,
        database: Path,
        index_path: Path | None = None,
        *,
        embedding_dimension: int | None = None,
    ) -> None:
        """Validate metadata and, when supplied, its FAISS index before serving.

        Args:
            database: Immutable metadata.sqlite produced using schema.sql.
            index_path: An inner-product FAISS index of normalized vectors.
            embedding_dimension: The manifest's expected vector dimension.

        Raises:
            FileNotFoundError: When an artifact does not exist.
            ValueError: When the schema, dimensions or index mapping disagree.
            RuntimeError: When a supplied index requires an unavailable FAISS package.
        """
        self.database = Path(database).resolve()
        if not self.database.is_file():
            raise FileNotFoundError(self.database)
        self.index_path = Path(index_path).resolve() if index_path is not None else None
        self._index: Any = None
        metadata = dict(self._rows("SELECT key, value FROM corpus_metadata"))
        if metadata.get("schema_version") != "1":
            raise ValueError("The corpus requires SQLite schema_version 1")
        self.vector_dtype = metadata.get("vector_dtype", "float32")
        if self.vector_dtype not in {"float32", "float16"}:
            raise ValueError("SQLite vector_dtype must be float32 or float16")
        self._dtype = np.dtype("<f2" if self.vector_dtype == "float16" else "<f4")
        self.oversample = int(metadata.get("faiss_oversample", "4"))
        if not 1 <= self.oversample <= 64:
            raise ValueError("FAISS exact-rerank oversampling must be between 1 and 64")
        self.index_kind = metadata.get("faiss_index_kind", "flat")
        self.nprobe = 0
        self._nlist = 0
        stored = metadata.get("embedding_dimension")
        dimension = int(stored) if stored is not None else None
        first = self._rows(
            "SELECT length(embed_full) FROM papers WHERE embed_full IS NOT NULL LIMIT 1"
        )
        if first:
            size = int(first[0][0])
            if size == 0 or size % self._dtype.itemsize:
                raise ValueError("Paper vectors do not match their declared vector_dtype")
            inferred = size // self._dtype.itemsize
            if dimension is not None and dimension != inferred:
                raise ValueError("SQLite embedding_dimension does not match its vectors")
            dimension = inferred
        if embedding_dimension is not None:
            if embedding_dimension <= 0:
                raise ValueError("embedding_dimension must be positive")
            if dimension is not None and dimension != embedding_dimension:
                raise ValueError("Manifest embedding dimension does not match SQLite")
            dimension = embedding_dimension
        if dimension is not None and dimension <= 0:
            raise ValueError("SQLite embedding_dimension must be positive")
        self.dimension = dimension
        if dimension is not None and self._rows(
            "SELECT 1 FROM papers WHERE embed_full IS NOT NULL AND length(embed_full) != ? LIMIT 1",
            (dimension * self._dtype.itemsize,),
        ):
            raise ValueError("SQLite contains inconsistent vector dimensions")
        if self.index_path is not None:
            if not self.index_path.is_file():
                raise FileNotFoundError(self.index_path)
            try:
                import faiss
            except ImportError as error:
                raise RuntimeError("Install faiss-cpu to open a corpus vector index") from error
            self._index = faiss.read_index(str(self.index_path))
            if self._index.metric_type != faiss.METRIC_INNER_PRODUCT:
                raise ValueError("The FAISS index must use inner product over normalized vectors")
            if self.dimension is not None and self._index.d != self.dimension:
                raise ValueError("FAISS dimension does not match SQLite/manifest")
            self.dimension = int(self._index.d)
            self._nlist = int(getattr(self._index, "nlist", 0))
            if self._nlist:
                self.nprobe = int(metadata.get("faiss_nprobe", str(min(128, self._nlist))))
                if not 1 <= self.nprobe <= self._nlist:
                    raise ValueError("FAISS nprobe must be within the index's inverted-list count")
                expected_lists = int(metadata.get("faiss_nlist", str(self._nlist)))
                if expected_lists != self._nlist:
                    raise ValueError("SQLite FAISS list count does not match the index")
            count, low, high = self._rows(
                "SELECT count(*), min(faiss_id), max(faiss_id) FROM vector_ids"
            )[0]
            if count != self._index.ntotal or (count and (low != 0 or high != count - 1)):
                raise ValueError("vector_ids must map every FAISS ordinal exactly once")
            if self._rows(
                "SELECT 1 FROM vector_ids v LEFT JOIN papers p ON p.arxiv_id = v.arxiv_id "
                "WHERE p.arxiv_id IS NULL OR p.stage < 3 OR p.embed_full IS NULL LIMIT 1"
            ):
                raise ValueError("FAISS labels must reference embedded paper records")

    def _rows(self, query: str, parameters: tuple[Any, ...] = ()) -> list[Any]:
        uri = f"{self.database.as_uri()}?mode=ro&immutable=1"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            _ = connection.execute("PRAGMA query_only = ON")
            connection.create_function("pg_ilike", 2, _ilike, deterministic=True)
            return connection.execute(query, parameters).fetchall()

    def _query(self, vector: list[float]) -> NDArray[np.float64]:
        values = np.asarray(vector, dtype=np.float64)
        if values.ndim != 1 or not np.all(np.isfinite(values)):
            raise ValueError("Query vectors must be finite one-dimensional arrays")
        if self.dimension is not None and len(values) != self.dimension:
            raise ValueError(
                f"Query dimension {len(values)} does not match corpus {self.dimension}"
            )
        norm = float(np.linalg.norm(values))
        return values / norm if norm else values

    def _cosine(self, query: NDArray[np.float64], blob: bytes) -> float:
        vector = np.frombuffer(blob, dtype=self._dtype).astype(np.float64)
        if len(vector) != len(query) or not np.all(np.isfinite(vector)):
            raise ValueError("Stored and query vector dimensions/content disagree")
        norm = float(np.linalg.norm(vector))
        return float(np.dot(query, vector) / norm) if norm else 0.0

    def _paper_rows(self, query: NDArray[np.float64], rows: list[Any]) -> list[ScoredPaperRow]:
        return [
            (arxiv_id, title, abstract, date.fromisoformat(when), self._cosine(query, blob))
            for arxiv_id, title, abstract, when, blob in rows
        ]

    def search(
        self, vector: list[float], cap: date | None, blocked: list[str], limit: int
    ) -> list[ScoredPaperRow]:
        """Retrieve candidates, apply metadata filters, then return exact stored-vector cosines."""
        if limit <= 0:
            return []
        query = self._query(vector)
        cutoff = cap.isoformat() if cap is not None else None
        if self._index is None:
            return self._exact_search(query, cutoff, blocked, limit)
        total = int(self._index.ntotal)
        if not total:
            return []
        rerank_count = max(limit * self.oversample, 64)
        count = min(total, rerank_count)
        candidate_cap = min(total, max(65536, rerank_count * 16))
        probes = self.nprobe
        normalized = np.ascontiguousarray(query.reshape(1, -1), dtype=np.float32)
        while True:
            if self._nlist:
                import faiss

                parameters = faiss.SearchParametersIVF()
                parameters.nprobe = probes
                _, labels = self._index.search(normalized, count, params=parameters)
            else:
                _, labels = self._index.search(normalized, count)
            wanted = [int(label) for label in labels[0] if label >= 0]
            rows = self._rows(
                "SELECT v.faiss_id, p.arxiv_id "
                "FROM vector_ids v JOIN papers p ON p.arxiv_id = v.arxiv_id "
                "WHERE v.faiss_id IN (SELECT value FROM json_each(?)) AND p.stage >= 3 "
                "AND (? IS NULL OR p.date <= ?) "
                "AND p.arxiv_id NOT IN (SELECT value FROM json_each(?))",
                (_ids(wanted), cutoff, cutoff, _ids(blocked)),
            )
            eligible = dict(rows)
            ordered = [eligible[label] for label in wanted if label in eligible]
            exhaustive = count == total and (not self._nlist or probes == self._nlist)
            if len(ordered) >= limit or exhaustive:
                return self._rerank(query, ordered[:rerank_count], limit)
            if count >= candidate_cap or (self._nlist and probes == self._nlist):
                # A very selective historical filter can exclude every ANN hit.
                # Stream the eligible set exactly instead of silently shortening
                # the pool or materializing millions of candidate vector blobs.
                return self._exact_search(query, cutoff, blocked, limit)
            count = min(total, candidate_cap, count * 2)
            probes = min(self._nlist, max(1, probes * 2))

    def _rerank(
        self, query: NDArray[np.float64], arxiv_ids: list[str], limit: int
    ) -> list[ScoredPaperRow]:
        vectors = dict(
            self._rows(
                "SELECT arxiv_id,embed_full FROM papers "
                "WHERE arxiv_id IN (SELECT value FROM json_each(?))",
                (_ids(arxiv_ids),),
            )
        )
        ranked = sorted(
            [(arxiv_id, self._cosine(query, vectors[arxiv_id])) for arxiv_id in arxiv_ids],
            key=lambda row: -row[1],
        )[:limit]
        details = {row[0]: row[1:] for row in self.paper_details([row[0] for row in ranked])}
        return [
            (
                arxiv_id,
                details[arxiv_id][0],
                details[arxiv_id][1],
                date.fromisoformat(str(details[arxiv_id][2])),
                cosine,
            )
            for arxiv_id, cosine in ranked
        ]

    def _exact_search(
        self, query: NDArray[np.float64], cutoff: str | None, blocked: list[str], limit: int
    ) -> list[ScoredPaperRow]:
        heap: list[tuple[float, int, ScoredPaperRow]] = []
        uri = f"{self.database.as_uri()}?mode=ro&immutable=1"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            _ = connection.execute("PRAGMA query_only = ON")
            cursor = connection.execute(
                "SELECT arxiv_id,title,abstract,date,embed_full FROM papers "
                "WHERE stage>=3 AND embed_full IS NOT NULL AND (? IS NULL OR date<=?) "
                "AND arxiv_id NOT IN (SELECT value FROM json_each(?))",
                (cutoff, cutoff, _ids(blocked)),
            )
            number = 0
            while rows := cursor.fetchmany(512):
                for row in self._paper_rows(query, rows):
                    entry = (row[4], -number, row)
                    if len(heap) < limit:
                        heappush(heap, entry)
                    elif entry[:2] > heap[0][:2]:
                        heapreplace(heap, entry)
                    number += 1
        return [entry[2] for entry in sorted(heap, reverse=True)]

    def edges(self, arxiv_ids: list[str]) -> list[EdgeRow]:
        """Read labeled occurrences with both ends inside the requested set."""
        return self._rows(
            "SELECT source_id, target_id, intent, sentence FROM citations WHERE stage = 1 "
            "AND source_id IN (SELECT value FROM json_each(?)) "
            "AND target_id IN (SELECT value FROM json_each(?)) AND target_id IS NOT NULL",
            (_ids(arxiv_ids), _ids(arxiv_ids)),
        )

    def edge_records(
        self, arxiv_ids: list[str]
    ) -> list[tuple[str, str, str | None, str | None, float | None]]:
        """Preserve per-occurrence confidence alongside the precomputed intent label."""
        return self._rows(
            "SELECT source_id,target_id,intent,sentence,intent_score FROM citations "
            "WHERE stage=1 AND source_id IN (SELECT value FROM json_each(?)) "
            "AND target_id IN (SELECT value FROM json_each(?)) AND target_id IS NOT NULL",
            (_ids(arxiv_ids), _ids(arxiv_ids)),
        )

    def cosines(self, vector: list[float], arxiv_ids: list[str]) -> list[tuple[str, float]]:
        """Compute exact cosine from the original stored vector values."""
        query = self._query(vector)
        rows = self._rows(
            "SELECT arxiv_id, embed_full FROM papers "
            "WHERE arxiv_id IN (SELECT value FROM json_each(?)) AND stage >= 3",
            (_ids(arxiv_ids),),
        )
        return [(arxiv_id, self._cosine(query, blob)) for arxiv_id, blob in rows]

    def papers(self, vector: list[float], arxiv_ids: list[str]) -> list[ScoredPaperRow]:
        """Read complete embedded paper rows in metadata query order."""
        return self._paper_rows(
            self._query(vector),
            self._rows(
                "SELECT arxiv_id, title, abstract, date, embed_full FROM papers "
                "WHERE arxiv_id IN (SELECT value FROM json_each(?)) AND stage >= 3",
                (_ids(arxiv_ids),),
            ),
        )

    def seed(self, arxiv_id: str) -> SeedRow | None:
        """Read one embedded paper and its unnormalized stored vector."""
        rows = self._rows(
            "SELECT arxiv_id, title, abstract, date, embed_full FROM papers "
            "WHERE arxiv_id = ? AND stage >= 3",
            (arxiv_id,),
        )
        if not rows:
            return None
        arxiv_id, title, abstract, when, blob = rows[0]
        return (
            arxiv_id,
            title,
            abstract,
            date.fromisoformat(when),
            np.frombuffer(blob, dtype=self._dtype).tolist(),
        )

    def vectors(self, arxiv_ids: list[str]) -> list[VectorRow]:
        """Read original vectors only from embedded papers."""
        rows = self._rows(
            "SELECT arxiv_id, embed_full FROM papers "
            "WHERE arxiv_id IN (SELECT value FROM json_each(?)) AND stage >= 3",
            (_ids(arxiv_ids),),
        )
        return [
            (arxiv_id, np.frombuffer(blob, dtype=self._dtype).tolist()) for arxiv_id, blob in rows
        ]

    def successors(
        self,
        vector: list[float],
        arxiv_ids: list[str],
        since: date,
        until: date,
        intents: tuple[str, ...],
        floor: float,
    ) -> list[SuccessorRow]:
        """Keep citation multiplicity, label/score gates and the (since, until] window."""
        query = self._query(vector)
        rows = self._rows(
            "SELECT c.source_id, c.target_id, c.intent, c.sentence, p.date, p.title, "
            "p.abstract, p.embed_full FROM citations c JOIN papers p ON p.arxiv_id = c.source_id "
            "WHERE c.stage = 1 AND c.target_id IN (SELECT value FROM json_each(?)) "
            "AND c.intent IN (SELECT value FROM json_each(?)) AND c.intent_score >= ? "
            "AND p.date > ? AND p.date <= ? AND p.stage >= 3",
            (_ids(arxiv_ids), _ids(list(intents)), floor, since.isoformat(), until.isoformat()),
        )
        return [
            (
                source,
                target,
                intent,
                sentence,
                date.fromisoformat(when),
                title,
                abstract,
                self._cosine(query, blob),
            )
            for source, target, intent, sentence, when, title, abstract, blob in rows
        ]

    def records(self, arxiv_ids: list[str]) -> list[RecordRow]:
        """Read all-stage paper metadata using the same topic joins as PostgreSQL."""
        rows = self._rows(
            "SELECT p.arxiv_id, p.title, p.abstract, p.date, p.primary_category, p.authors, "
            "t.level_0, t.level_1, t.level_2, g.name, m.name, l.name FROM papers p "
            "LEFT JOIN topic_tree t ON t.arxiv_id = p.arxiv_id AND t.stage = 1 "
            "LEFT JOIN topic_names g ON g.level_0 = t.level_0 AND g.level_1 IS NULL "
            "LEFT JOIN topic_names m ON m.level_0 = t.level_0 AND m.level_1 = t.level_1 "
            "AND m.level_2 IS NULL "
            "LEFT JOIN topic_names l ON l.level_0 = t.level_0 AND l.level_1 = t.level_1 "
            "AND l.level_2 = t.level_2 "
            "WHERE p.arxiv_id IN (SELECT value FROM json_each(?))",
            (_ids(arxiv_ids),),
        )
        return [
            (
                row[0],
                row[1],
                row[2],
                _date(row[3]),
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
                row[10],
                row[11],
            )
            for row in rows
        ]

    def author_candidates(self, surname: str, pattern: str) -> list[tuple[str, str | None]]:
        """Use the exact surname index, followed by case-insensitive SQL-pattern matching."""
        return self._rows(
            "SELECT arxiv_id, authors FROM papers WHERE arxiv_id IN "
            "(SELECT arxiv_id FROM paper_surnames WHERE surname = ?) "
            "AND pg_ilike(?, authors) AND stage >= 3",
            (surname, pattern),
        )

    def references(self, arxiv_ids: list[str]) -> list[tuple[str, str]]:
        """Read distinct resolved references at every citation stage."""
        return self._rows(
            "SELECT DISTINCT source_id, target_id FROM citations "
            "WHERE source_id IN (SELECT value FROM json_each(?)) AND target_id IS NOT NULL",
            (_ids(arxiv_ids),),
        )

    def topics(self, arxiv_ids: list[str]) -> list[tuple[str, int, int]]:
        """Read only completed parent-topic placements."""
        return self._rows(
            "SELECT arxiv_id, level_0, level_1 FROM topic_tree "
            "WHERE arxiv_id IN (SELECT value FROM json_each(?)) AND stage = 1",
            (_ids(arxiv_ids),),
        )

    def topic_names(self) -> list[tuple[int, int, str]]:
        """Read parent-topic names, excluding roots and leaves."""
        return self._rows(
            "SELECT level_0, level_1, name FROM topic_names "
            "WHERE level_2 IS NULL AND level_1 IS NOT NULL"
        )

    def existing_ids(self, arxiv_ids: list[str]) -> list[tuple[str]]:
        """Find known identifiers without an embedding-stage restriction."""
        return self._rows(
            "SELECT arxiv_id FROM papers WHERE arxiv_id IN (SELECT value FROM json_each(?))",
            (_ids(arxiv_ids),),
        )

    def paper_details(self, arxiv_ids: list[str]) -> list[DetailRow]:
        """Read metadata at every paper stage, preserving nullable dates."""
        rows = self._rows(
            "SELECT arxiv_id, title, abstract, date FROM papers "
            "WHERE arxiv_id IN (SELECT value FROM json_each(?))",
            (_ids(arxiv_ids),),
        )
        return [
            (arxiv_id, title, abstract, _date(when)) for arxiv_id, title, abstract, when in rows
        ]

    def abstract_authors(self, arxiv_ids: list[str]) -> list[tuple[str, str | None, str | None]]:
        """Read recall metadata without filtering unembedded papers."""
        return self._rows(
            "SELECT arxiv_id, abstract, authors FROM papers "
            "WHERE arxiv_id IN (SELECT value FROM json_each(?))",
            (_ids(arxiv_ids),),
        )

    def citing_papers(
        self,
        arxiv_id: str,
        intents: list[str],
        floor: float,
        since: str | None,
        limit: int,
    ) -> list[CitingRow]:
        """Read occurrences newest first with an inclusive floor, without a paper-stage gate."""
        cutoff = date.fromisoformat(since).isoformat() if since else None
        rows = self._rows(
            "SELECT c.source_id, c.intent, c.sentence, p.date, p.title "
            "FROM citations c JOIN papers p ON p.arxiv_id = c.source_id "
            "WHERE c.stage = 1 AND c.target_id = ? "
            "AND c.intent IN (SELECT value FROM json_each(?)) "
            "AND c.intent_score >= ? AND (? IS NULL OR p.date >= ?) ORDER BY p.date DESC LIMIT ?",
            (arxiv_id, _ids(intents), floor, cutoff, cutoff, limit),
        )
        return [
            (source, intent, sentence, date.fromisoformat(when), title)
            for source, intent, sentence, when, title in rows
        ]
