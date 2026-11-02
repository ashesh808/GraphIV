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

from offline.index_build.graph import write_graph
from offline.index_build.indexes import build_index
from offline.index_build.parquet import ParquetSource
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
    dimension: int | None,
    vector_dtype: str,
) -> tuple[int, int, int]:
    dtype = "<f2" if vector_dtype == "float16" else "<f4"
    count = 0
    embedded = 0
    for record in records:
        arxiv_id = _identifier(record.get("arxiv_id", record.get("id")))
        raw = record.get("embed_full", record.get("embedding"))
        vector = np.asarray(raw, dtype=dtype) if raw is not None else None
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
            if not float(np.linalg.norm(vector.astype(np.float32))):
                raise ValueError(f"Embedded paper {arxiv_id} has a zero vector")
            connection.execute("INSERT INTO vector_ids VALUES (?,?)", (embedded, arxiv_id))
            embedded += 1
    if not embedded or dimension is None:
        raise ValueError("A snapshot requires at least one real embedded paper")
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
    return write_graph(connection, path)


def _bulk_settings(connection: sqlite3.Connection) -> list[str]:
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("PRAGMA cache_size=-131072")
    connection.execute("PRAGMA mmap_size=0")
    deferred = [
        row[0]
        for row in connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='citations' "
            "AND sql IS NOT NULL"
        )
    ]
    for (name,) in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='citations' "
        "AND sql IS NOT NULL"
    ).fetchall():
        connection.execute(f'DROP INDEX "{name}"')
    trigger = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='papers_surnames_insert'"
    ).fetchone()
    if trigger:
        deferred.append(trigger[0])
        connection.execute("DROP TRIGGER papers_surnames_insert")
    return deferred


def _finish_indexes(connection: sqlite3.Connection, deferred: list[str]) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO paper_surnames(surname,arxiv_id) "
        "SELECT value,p.arxiv_id FROM papers p,json_each(p.surnames) "
        "ORDER BY value,p.arxiv_id"
    )
    for statement in deferred:
        connection.execute(statement)


def _counts(connection: sqlite3.Connection) -> tuple[dict[str, int], dict[str, int]]:
    citations, labelled, confidence, sentences, unresolved = connection.execute(
        "SELECT count(*),coalesce(sum(stage=1 AND intent IS NOT NULL),0),"
        "coalesce(sum(intent_score IS NOT NULL),0),"
        "coalesce(sum(sentence IS NOT NULL AND sentence!=''),0),"
        "coalesce(sum(target_id IS NULL),0) FROM citations"
    ).fetchone()
    counts = {
        "citations": citations,
        "topics": connection.execute("SELECT count(*) FROM topic_tree").fetchone()[0],
        "topic_names": connection.execute("SELECT count(*) FROM topic_names").fetchone()[0],
    }
    quality = {
        "citation_occurrences": citations,
        "precomputed_intent_rows": labelled,
        "confidence_rows": confidence,
        "citation_sentence_rows": sentences,
        "unresolved_targets": unresolved,
    }
    return counts, quality


def _connect_build_database(database: Path) -> sqlite3.Connection:
    """Keep locking for private builds on shares without POSIX advisory locks."""
    vfs = os.environ.get("GRAPHIV_SQLITE_WRITE_VFS", "")
    if vfs not in {"", "unix-dotfile"}:
        raise ValueError("GRAPHIV_SQLITE_WRITE_VFS must be empty or unix-dotfile")
    if vfs:
        return sqlite3.connect(database.as_uri() + "?mode=rwc&vfs=unix-dotfile", uri=True)
    return sqlite3.connect(database)


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
    vector_dtype: str = "float32",
    index_kind: str = "flat",
    nlist: int = 1024,
    nprobe: int = 128,
    train_size: int = 65536,
    seed: int = 0,
    provenance: dict[str, Any] | None = None,
    capabilities: dict[str, bool] | None = None,
    expected_counts: dict[str, int] | None = None,
) -> Path:
    """Atomically publish locally built, validated artifacts and their SHA-256 manifest.

    Existing output directories are never overwritten. Cloud publication is a
    separate, explicit operation in publish.py.
    """
    validate_segment(snapshot_id)
    if vector_dtype not in {"float16", "float32"}:
        raise ValueError("vector_dtype must be float16 or float32")
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
        with closing(_connect_build_database(database)) as connection:
            connection.executescript(SCHEMA.read_text())
            deferred = _bulk_settings(connection)
            with connection:
                count, embedded, dimension = _insert_papers(
                    connection, papers, embedding_dimension, vector_dtype
                )
                _insert_citations(connection, citations)
                _insert_topics(connection, topics, topic_names)
                _finish_indexes(connection, deferred)
                connection.executemany(
                    "INSERT INTO corpus_metadata VALUES (?,?)",
                    [
                        ("embedding_dimension", str(dimension)),
                        ("embedding_model", embedding_model),
                        ("vector_dtype", vector_dtype),
                    ],
                )
                source_counts, quality = _counts(connection)
                if expected_counts is not None:
                    actual = {
                        "papers": count,
                        "citations": source_counts["citations"],
                        "topics": source_counts["topics"],
                    }
                    if actual != expected_counts:
                        raise ValueError("Imported rows do not match the complete source counts")
                index_metrics = build_index(
                    connection,
                    staging / ARTIFACT_FILENAMES["vectors"],
                    dimension,
                    index_kind=index_kind,
                    nlist=nlist,
                    nprobe=nprobe,
                    train_size=train_size,
                    seed=seed,
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
            "counts": {"papers": count, "embedded": embedded, "edges": edges, **source_counts},
            "quality": quality,
            "index": index_metrics,
            "build": {
                "index_kind": index_kind,
                "nlist": nlist,
                "nprobe": nprobe,
                "train_size": train_size,
                "seed": seed,
                "vector_dtype": vector_dtype,
            },
            "storage": {"vector_dtype": vector_dtype},
            "capabilities": capabilities
            or {
                "precomputed_intents": quality["precomputed_intent_rows"] > 0,
                "intent_confidence": quality["confidence_rows"] > 0,
                "citation_sentences": quality["citation_sentence_rows"] > 0,
            },
            **({"source": provenance} if provenance is not None else {}),
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
        "--parquet-root", type=Path, help="complete local published Parquet snapshot"
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
    parser.add_argument("--vector-dtype", choices=["float16", "float32"])
    parser.add_argument("--index-kind", choices=["flat", "ivfsq8"], default="flat")
    parser.add_argument("--nlist", type=int, default=1024)
    parser.add_argument("--nprobe", type=int, default=128)
    parser.add_argument("--train-size", type=int, default=65536)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--source-repository", default="kkuroma/GraphIV")
    parser.add_argument("--source-revision", default="GraphIV-2026-10-01")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--source-manifest", type=Path)
    args = parser.parse_args()
    options = {
        "snapshot_id": args.snapshot_id,
        "embedding_model": args.embedding_model,
        "embedding_dimension": args.dimension,
        "vector_container": args.vector_container,
        "metadata_container": args.metadata_container,
        "graph_container": args.graph_container,
        "vector_dtype": args.vector_dtype or ("float16" if args.parquet_root else "float32"),
        "index_kind": args.index_kind,
        "nlist": args.nlist,
        "nprobe": args.nprobe,
        "train_size": args.train_size,
        "seed": args.seed,
    }
    if args.parquet_root:
        parquet = ParquetSource(
            args.parquet_root,
            repository=args.source_repository,
            revision=args.source_revision,
            commit=args.source_commit,
            source_manifest=args.source_manifest,
        )
        manifest = build_snapshot(
            parquet.paper_rows(),
            parquet.citation_rows(),
            args.output,
            topics=parquet.topic_rows(),
            topic_names=parquet.topic_name_rows(),
            provenance=parquet.provenance(),
            expected_counts=parquet.expected_rows,
            capabilities={
                "precomputed_intents": True,
                "intent_confidence": True,
                "citation_sentences": False,
            },
            **options,
        )
        parquet.verify_counts()
    elif args.postgres:
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
