"""Build an immutable SQLite/FAISS/GraphExport snapshot from real supplied corpus rows.

JSONL inputs use the original PostgreSQL paper/citation/topic column names;
``embedding`` is also accepted as an alias for papers.embed_full. Embeddings are
required input data: this builder never manufactures vectors or sample papers.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any, LiteralString

import numpy as np
import psycopg

from src.core.config import load_config
from src.core.parse_graph_export import load_graph_export
from src.core.paths import OFFLINE_CONFIG
from src.storage.artifacts import ARTIFACT_FILENAMES, parse_manifest
from src.storage.blobs import file_sha256, validate_container, validate_segment
from src.storage.sqlite import SQLiteCorpus

SCHEMA = Path(__file__).resolve().parents[2] / "src" / "storage" / "schema.sql"
BATCH = 1024
EDGE_CHUNK = 100_000
POSTGRES_READS: dict[str, LiteralString] = {
    "papers": (
        "SELECT arxiv_id, stage, title, abstract, date, primary_category, authors, surnames, "
        "embed_full::vector::real[] AS embed_full, survey_probability FROM papers ORDER BY arxiv_id"
    ),
    "citations": (
        "SELECT citation_id, source_id, target_id, stage, sentence, intent, intent_score "
        "FROM citations ORDER BY citation_id"
    ),
    "topics": "SELECT arxiv_id, stage, level_0, level_1, level_2 FROM topic_tree",
    "topic_names": "SELECT level_0, level_1, level_2, name FROM topic_names",
}


def jsonl_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Stream object records, identifying invalid source lines without loading the input."""
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on {path.name} line {number}") from error
            if not isinstance(record, dict):
                raise ValueError(f"Expected an object on {path.name} line {number}")
            yield record


def postgres_rows(connection: psycopg.Connection, table: str) -> Iterator[dict[str, Any]]:
    """Stream one known source table within the caller's read-only consistent transaction."""
    query = POSTGRES_READS[table]
    with connection.cursor(name=f"snapshot_{table}") as cursor:
        cursor.itersize = EDGE_CHUNK
        cursor.execute(query)
        columns = [column.name for column in cursor.description or ()]
        for row in cursor:
            yield dict(zip(columns, row, strict=True))


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("Every corpus row needs a nonempty arxiv_id/source_id")
    return value


def _day(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return date.fromisoformat(str(value)).isoformat()


def _insert_papers(
    connection: sqlite3.Connection,
    records: Iterable[dict[str, Any]],
    index_path: Path,
    dimension: int | None,
) -> tuple[int, int, int]:
    import faiss

    index: Any = None
    vectors: list[np.ndarray] = []
    count = 0
    embedded = 0
    for record in records:
        arxiv_id = _identifier(record.get("arxiv_id", record.get("id")))
        raw = record.get("embed_full", record.get("embedding"))
        vector = np.asarray(raw, dtype="<f4") if raw is not None else None
        if vector is not None:
            if vector.ndim != 1 or not len(vector) or not np.all(np.isfinite(vector)):
                raise ValueError(f"Paper {arxiv_id} needs a finite one-dimensional vector")
            if dimension is None:
                dimension = len(vector)
            if len(vector) != dimension:
                raise ValueError(f"Paper {arxiv_id} has an inconsistent embedding dimension")
        stage = int(record.get("stage", 3 if vector is not None else 0))
        when = _day(record.get("date"))
        if stage >= 3 and (vector is None or when is None):
            raise ValueError(
                f"Embedded paper {arxiv_id} needs both a vector and a publication date"
            )
        authors = record.get("authors")
        if isinstance(authors, list):
            authors = ", ".join(str(author) for author in authors)
        surnames = record.get("surnames")
        if surnames is None:
            surnames = []
        if not isinstance(surnames, list) or any(not isinstance(name, str) for name in surnames):
            raise ValueError(f"Paper {arxiv_id} surnames must be an array of strings")
        survey = record.get("survey_probability")
        if survey is not None and not math.isfinite(float(survey)):
            raise ValueError(f"Paper {arxiv_id} has a nonfinite survey probability")
        connection.execute(
            "INSERT INTO papers(arxiv_id,stage,title,abstract,date,primary_category,authors,"
            "surnames,embed_full,survey_probability) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                arxiv_id,
                stage,
                record.get("title"),
                record.get("abstract"),
                when,
                record.get("primary_category", record.get("category")),
                authors,
                json.dumps(surnames, ensure_ascii=False),
                vector.tobytes() if vector is not None else None,
                survey,
            ),
        )
        count += 1
        if stage >= 3 and vector is not None:
            if not float(np.linalg.norm(vector)):
                raise ValueError(f"Embedded paper {arxiv_id} has a zero vector")
            if index is None:
                index = faiss.IndexFlatIP(len(vector))
            connection.execute("INSERT INTO vector_ids VALUES (?,?)", (embedded, arxiv_id))
            vectors.append(vector)
            embedded += 1
            if len(vectors) == BATCH:
                batch = np.ascontiguousarray(np.stack(vectors), dtype="float32")
                faiss.normalize_L2(batch)
                index.add(batch)
                vectors.clear()
    if index is None or dimension is None:
        raise ValueError("A snapshot requires at least one real embedded paper")
    if vectors:
        batch = np.ascontiguousarray(np.stack(vectors), dtype="float32")
        faiss.normalize_L2(batch)
        index.add(batch)
    faiss.write_index(index, str(index_path))
    return count, embedded, dimension


def _insert_citations(connection: sqlite3.Connection, records: Iterable[dict[str, Any]]) -> None:
    connection.executemany(
        "INSERT INTO citations(citation_id,source_id,target_id,stage,sentence,intent,intent_score) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            (
                record.get("citation_id", number),
                _identifier(record.get("source_id")),
                record.get("target_id"),
                int(record.get("stage", 0)),
                record.get("sentence"),
                record.get("intent"),
                record.get("intent_score"),
            )
            for number, record in enumerate(records, 1)
        ),
    )


def _insert_topics(
    connection: sqlite3.Connection,
    topics: Iterable[dict[str, Any]],
    names: Iterable[dict[str, Any]],
) -> None:
    connection.executemany(
        "INSERT INTO topic_tree VALUES (?,?,?,?,?)",
        (
            (
                _identifier(record.get("arxiv_id")),
                int(record.get("stage", 1)),
                record.get("level_0"),
                record.get("level_1"),
                record.get("level_2"),
            )
            for record in topics
        ),
    )
    connection.executemany(
        "INSERT INTO topic_names VALUES (?,?,?,?)",
        (
            (record["level_0"], record.get("level_1"), record.get("level_2"), record["name"])
            for record in names
        ),
    )


def _write_graph(connection: sqlite3.Connection, path: Path) -> int:
    rows = connection.execute(
        "SELECT arxiv_id,date,stage,coalesce(survey_probability,-1) FROM papers ORDER BY arxiv_id"
    ).fetchall()
    index = {row[0]: number for number, row in enumerate(rows)}
    epoch = np.datetime64("1970-01-01")
    day = np.timedelta64(1, "D")
    arrays: dict[str, np.ndarray] = {
        "ids": np.array([row[0].encode() for row in rows], dtype="S"),
        "day": np.array(
            [
                -(1 << 30) if row[1] is None else (np.datetime64(row[1]) - epoch) // day
                for row in rows
            ],
            np.int32,
        ),
        "stage": np.array([row[2] for row in rows], np.int8),
        "survey": np.array([row[3] for row in rows], np.float32),
    }
    sources: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    cursor = connection.execute(
        "SELECT source_id,target_id FROM citations WHERE target_id IS NOT NULL"
    )
    while chunk := cursor.fetchmany(EDGE_CHUNK):
        sources.append(np.array([index.get(source, -1) for source, _ in chunk], np.int32))
        targets.append(np.array([index.get(target, -1) for _, target in chunk], np.int32))
    source = np.concatenate(sources) if sources else np.empty(0, np.int32)
    target = np.concatenate(targets) if targets else np.empty(0, np.int32)
    keep = (source >= 0) & (target >= 0)
    pairs = np.unique(source[keep].astype(np.int64) * len(rows) + target[keep])
    source = (pairs // len(rows)).astype(np.int32)
    target = (pairs % len(rows)).astype(np.int32)
    levels = np.full((len(rows), 3), -1, np.int8)
    for arxiv_id, l0, l1, l2 in connection.execute(
        "SELECT arxiv_id,level_0,level_1,level_2 FROM topic_tree "
        "WHERE stage=1 AND level_2 IS NOT NULL"
    ):
        if any(value is None or not -128 <= value <= 127 for value in (l0, l1, l2)):
            raise ValueError("Topic levels must fit the GraphExport int8 representation")
        levels[index[arxiv_id]] = l0, l1, l2
    arrays["level"] = levels
    for name, row, column in (("cites", target, source), ("refs", source, target)):
        order = np.argsort(row, kind="stable")
        pointer = np.zeros(len(rows) + 1, np.int32)
        pointer[1:] = np.cumsum(np.bincount(row, minlength=len(rows)))
        arrays[f"{name}_ptr"] = pointer
        arrays[f"{name}_idx"] = column[order]
    with path.open("wb") as handle:
        np.savez(
            handle,
            ids=arrays["ids"],
            day=arrays["day"],
            stage=arrays["stage"],
            survey=arrays["survey"],
            level=arrays["level"],
            cites_ptr=arrays["cites_ptr"],
            cites_idx=arrays["cites_idx"],
            refs_ptr=arrays["refs_ptr"],
            refs_idx=arrays["refs_idx"],
        )
    return len(source)


def build_snapshot(
    papers: Iterable[dict[str, Any]],
    citations: Iterable[dict[str, Any]],
    destination: Path,
    *,
    snapshot_id: str,
    embedding_model: str,
    topics: Iterable[dict[str, Any]] = (),
    topic_names: Iterable[dict[str, Any]] = (),
    embedding_dimension: int | None = None,
    vector_container: str = "vector-indexes",
    metadata_container: str = "metadata",
    graph_container: str = "citation-graphs",
) -> Path:
    """Atomically publish locally built, validated artifacts and their SHA-256 manifest.

    Existing output directories are never overwritten. Cloud publication is a
    separate, explicit operation in publish.py.
    """
    validate_segment(snapshot_id)
    for container in (vector_container, metadata_container, graph_container):
        validate_container(container)
    if not embedding_model.strip():
        raise ValueError("embedding_model must identify the model that produced these vectors")
    if embedding_dimension is not None and embedding_dimension <= 0:
        raise ValueError("embedding_dimension must be positive")
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-", dir=destination.parent
    ) as temporary:
        staging = Path(temporary) / "complete"
        staging.mkdir()
        database = staging / ARTIFACT_FILENAMES["metadata"]
        with closing(sqlite3.connect(database)) as connection:
            connection.executescript(SCHEMA.read_text())
            with connection:
                count, embedded, dimension = _insert_papers(
                    connection, papers, staging / ARTIFACT_FILENAMES["vectors"], embedding_dimension
                )
                _insert_citations(connection, citations)
                _insert_topics(connection, topics, topic_names)
                connection.executemany(
                    "INSERT INTO corpus_metadata VALUES (?,?)",
                    [("embedding_dimension", str(dimension)), ("embedding_model", embedding_model)],
                )
                edges = _write_graph(connection, staging / ARTIFACT_FILENAMES["graph"])
        # Use the actual runtime loaders before a directory can become visible.
        SQLiteCorpus(
            database, staging / ARTIFACT_FILENAMES["vectors"], embedding_dimension=dimension
        )
        graph = load_graph_export(staging / ARTIFACT_FILENAMES["graph"])
        if graph.n_papers != count:
            raise ValueError("Graph and SQLite paper counts disagree")
        locations = {
            "vectors": vector_container,
            "metadata": metadata_container,
            "graph": graph_container,
        }
        manifest = {
            "version": 1,
            "snapshot_id": snapshot_id,
            "embedding": {"dimension": dimension, "model": embedding_model},
            "artifacts": {
                role: {
                    "container": locations[role],
                    "blob": f"snapshots/{snapshot_id}/{filename}",
                    "sha256": file_sha256(staging / filename),
                }
                for role, filename in ARTIFACT_FILENAMES.items()
            },
            "counts": {"papers": count, "embedded": embedded, "edges": edges},
        }
        body = (json.dumps(manifest, indent=2) + "\n").encode()
        parse_manifest(body)
        (staging / "manifest.json").write_bytes(body)
        os.rename(staging, destination)
    return destination / "manifest.json"


def main() -> None:
    """Build from JSONL files or a read-only PostgreSQL snapshot; never upload automatically."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--papers", type=Path, help="paper JSONL with real embed_full/embedding arrays"
    )
    source.add_argument(
        "--postgres", action="store_true", help="read the configured PostgreSQL corpus"
    )
    parser.add_argument(
        "--citations", type=Path, help="citation-occurrence JSONL, including unresolved rows"
    )
    parser.add_argument("--topics", type=Path, help="optional topic-tree JSONL")
    parser.add_argument("--topic-names", type=Path, help="optional topic-name JSONL")
    parser.add_argument("--config-path", type=Path, default=OFFLINE_CONFIG)
    parser.add_argument("--out", "--output", dest="output", type=Path, required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--embedding-model", required=True)
    parser.add_argument("--dimension", type=int)
    parser.add_argument("--vector-container", default="vector-indexes")
    parser.add_argument("--metadata-container", default="metadata")
    parser.add_argument("--graph-container", default="citation-graphs")
    args = parser.parse_args()
    options = {
        "snapshot_id": args.snapshot_id,
        "embedding_model": args.embedding_model,
        "embedding_dimension": args.dimension,
        "vector_container": args.vector_container,
        "metadata_container": args.metadata_container,
        "graph_container": args.graph_container,
    }
    if args.postgres:
        dsn = os.environ.get("GRAPHIV_POSTGRES_DSN") or str(
            load_config(args.config_path)["database"]["PG_DEST"]
        )
        with psycopg.connect(dsn) as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            manifest = build_snapshot(
                postgres_rows(connection, "papers"),
                postgres_rows(connection, "citations"),
                args.output,
                topics=postgres_rows(connection, "topics"),
                topic_names=postgres_rows(connection, "topic_names"),
                **options,
            )
    else:
        if args.citations is None:
            parser.error("--citations is required with --papers (an empty JSONL file is allowed)")
        manifest = build_snapshot(
            jsonl_rows(args.papers),
            jsonl_rows(args.citations),
            args.output,
            topics=jsonl_rows(args.topics) if args.topics else (),
            topic_names=jsonl_rows(args.topic_names) if args.topic_names else (),
            **options,
        )
    print(f"Built immutable snapshot: {manifest}", flush=True)


if __name__ == "__main__":
    main()
