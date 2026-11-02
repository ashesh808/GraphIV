"""Gate an actual corpus index against exact search and its original Nomic document space."""

from __future__ import annotations

import argparse
import json
import resource
import sqlite3
import sys
import time
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from src.core.query_encoder import NomicQueryEncoder
from src.storage.blobs import file_sha256
from src.storage.sqlite import SQLiteCorpus


class DocumentEncoder(Protocol):
    """The bounded document-validation surface of the original query encoder."""

    model_id: str
    revision: str
    code_revision: str

    def encode_document(self, title: str, abstract: str) -> list[float]:
        """Encode the original published title/abstract representation."""
        ...


def _unit(values: list[float], dimension: int) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float64)
    if vector.shape != (dimension,) or not np.all(np.isfinite(vector)):
        raise ValueError(
            "Benchmark queries must match the corpus dimension and contain finite values"
        )
    norm = float(np.linalg.norm(vector))
    if not norm:
        raise ValueError("Benchmark queries cannot be zero vectors")
    return vector / norm


def exact_neighbors(
    corpus: SQLiteCorpus,
    queries: list[dict[str, Any]],
    top_k: int,
    batch_size: int = 2048,
) -> list[list[tuple[str, float]]]:
    """Compute all query baselines in one bounded-memory scan of actual stored vectors."""
    dimension = corpus.dimension
    if dimension is None or top_k <= 0 or batch_size <= 0 or not queries:
        raise ValueError("Benchmark needs a dimensional corpus, queries and positive sizes")
    vectors = np.stack([_unit(query["embedding"], dimension) for query in queries])
    dtype = np.dtype("<f2" if corpus.vector_dtype == "float16" else "<f4")
    held: list[list[tuple[str, float]]] = [[] for _ in queries]
    uri = f"{corpus.database.as_uri()}?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        cursor = connection.execute(
            "SELECT arxiv_id,date,embed_full FROM papers WHERE stage>=3 AND embed_full IS NOT NULL"
        )
        while rows := cursor.fetchmany(batch_size):
            matrix = np.empty((len(rows), dimension), dtype=np.float64)
            for number, (_, _, blob) in enumerate(rows):
                matrix[number] = np.frombuffer(blob, dtype=dtype)
            norms = np.linalg.norm(matrix, axis=1)
            if np.any(norms == 0) or not np.all(np.isfinite(matrix)):
                raise ValueError("The actual corpus contains invalid embedding values")
            scores = (matrix @ vectors.T) / norms[:, None]
            for query_number, query in enumerate(queries):
                blocked = set(query.get("blocked", []))
                cap = query.get("date_max")
                valid = np.array(
                    [
                        identifier not in blocked
                        and (cap is None or (when is not None and when <= cap))
                        for identifier, when, _ in rows
                    ],
                    dtype=bool,
                )
                indexes = np.flatnonzero(valid)
                if len(indexes) > top_k:
                    indexes = indexes[
                        np.argpartition(-scores[indexes, query_number], top_k - 1)[:top_k]
                    ]
                candidates = held[query_number] + [
                    (rows[index][0], float(scores[index, query_number])) for index in indexes
                ]
                held[query_number] = sorted(candidates, key=lambda item: -item[1])[:top_k]
    return held


def evaluate_index(
    corpus: SQLiteCorpus,
    queries: list[dict[str, Any]],
    *,
    top_k: int = 200,
    nprobes: list[int] | None = None,
    min_recall: float = 0.98,
) -> dict[str, Any]:
    """Measure ANN recall, exact-score error, filter validity and latency against real vectors."""
    if not 0 <= min_recall <= 1:
        raise ValueError("Minimum recall must be between zero and one")
    dimension = corpus.dimension
    if dimension is None:
        raise ValueError("Benchmark requires a dimensional corpus")
    started = time.perf_counter()
    gold = exact_neighbors(corpus, queries, top_k)
    baseline_seconds = time.perf_counter() - started
    original_probe = corpus.nprobe
    tested: list[int] = []
    for probe in [original_probe, *(nprobes or [])]:
        if probe not in tested:
            tested.append(probe)
    configurations = []
    try:
        for probe in tested:
            if corpus._nlist and not 1 <= probe <= corpus._nlist:
                raise ValueError("A benchmark nprobe is outside the actual index list count")
            if not corpus._nlist and probe != 0:
                raise ValueError("nprobe applies only to an IVF candidate index")
            corpus.nprobe = probe
            results = []
            for number, query in enumerate(queries):
                vector = _unit(query["embedding"], dimension)
                cap = date.fromisoformat(query["date_max"]) if query.get("date_max") else None
                blocked = query.get("blocked", [])
                started = time.perf_counter()
                found = corpus.search(query["embedding"], cap, blocked, top_k)
                duration = time.perf_counter() - started
                identifiers = {row[0] for row in found}
                expected = {row[0] for row in gold[number]}
                recall = (
                    len(identifiers & expected) / len(expected) if expected else float(not found)
                )
                dtype = np.dtype("<f2" if corpus.vector_dtype == "float16" else "<f4")
                uri = f"{corpus.database.as_uri()}?mode=ro&immutable=1"
                with closing(sqlite3.connect(uri, uri=True)) as connection:
                    raw = dict(
                        connection.execute(
                            "SELECT arxiv_id,embed_full FROM papers "
                            "WHERE arxiv_id IN (SELECT value FROM json_each(?))",
                            (json.dumps(list(identifiers)),),
                        )
                    )
                errors = []
                for identifier, _, _, when, score in found:
                    if identifier in blocked or (cap is not None and when > cap):
                        raise ValueError(
                            "The candidate adapter returned a paper outside query eligibility"
                        )
                    stored = np.frombuffer(raw[identifier], dtype=dtype).astype(np.float64)
                    exact = float(np.dot(vector, stored) / np.linalg.norm(stored))
                    errors.append(abs(score - exact))
                results.append(
                    {
                        "query_id": query.get("id", str(number + 1)),
                        "query_kind": query.get("kind", "provided-query-embedding"),
                        "date_max": query.get("date_max"),
                        "blocked_count": len(blocked),
                        "returned": len(found),
                        "eligible_gold": len(gold[number]),
                        "recall_at_k": recall,
                        "max_abs_score_error": max(errors, default=0.0),
                        "seconds": round(duration, 4),
                    }
                )
            recall_values = [result["recall_at_k"] for result in results]
            max_error = max(result["max_abs_score_error"] for result in results)
            configurations.append(
                {
                    "nprobe": probe,
                    "minimum_recall_at_k": min(recall_values),
                    "mean_recall_at_k": sum(recall_values) / len(recall_values),
                    "max_abs_score_error": max_error,
                    "passed": min(recall_values) >= min_recall and max_error <= 1e-8,
                    "queries": results,
                }
            )
    finally:
        corpus.nprobe = original_probe
    memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    active = next(config for config in configurations if config["nprobe"] == original_probe)
    passing = [config["nprobe"] for config in configurations if config["passed"]]
    return {
        "top_k": top_k,
        "minimum_required_recall": min_recall,
        "query_count": len(queries),
        "vector_dtype": corpus.vector_dtype,
        "dimension": corpus.dimension,
        "index_kind": corpus.index_kind,
        "active_nprobe": original_probe,
        "rerank_oversample": corpus.oversample,
        "exact_baseline_seconds": round(baseline_seconds, 4),
        "sqlite_bytes": corpus.database.stat().st_size,
        "index_bytes": corpus.index_path.stat().st_size if corpus.index_path else 0,
        "peak_process_rss_bytes": int(memory if sys.platform == "darwin" else memory * 1024),
        "active_configuration_passed": active["passed"],
        "recommended_nprobe": min(passing) if passing else None,
        "configurations": configurations,
    }


def validate_document_space(
    corpus: SQLiteCorpus,
    encoder: DocumentEncoder,
    *,
    samples: int = 16,
    min_cosine: float = 0.999,
    seed: int = 0,
) -> dict[str, Any]:
    """Compare bounded actual published paper vectors to their original document encoding."""
    if samples <= 0 or not -1 <= min_cosine <= 1:
        raise ValueError(
            "Document validation needs a positive sample count and valid cosine threshold"
        )
    uri = f"{corpus.database.as_uri()}?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        total = connection.execute("SELECT count(*) FROM vector_ids").fetchone()[0]
        if total == 0:
            raise ValueError("Document validation requires actual published paper vectors")
        selected = (
            np.random.default_rng(seed).choice(total, min(samples, total), replace=False).tolist()
        )
        rows = connection.execute(
            "SELECT p.arxiv_id,p.title,p.abstract,p.embed_full FROM vector_ids v "
            "JOIN papers p ON p.arxiv_id=v.arxiv_id "
            "WHERE v.faiss_id IN (SELECT value FROM json_each(?)) ORDER BY v.faiss_id",
            (json.dumps(selected),),
        ).fetchall()
    if len(rows) != len(selected):
        raise ValueError("Document validation found missing published paper vectors")
    dtype = np.dtype("<f2" if corpus.vector_dtype == "float16" else "<f4")
    results = []
    for identifier, title, abstract, blob in rows:
        expected = np.frombuffer(blob, dtype=dtype).astype(np.float64)
        encoded = np.asarray(encoder.encode_document(title or "", abstract or ""), dtype=np.float64)
        if expected.shape != encoded.shape:
            raise ValueError("The Nomic encoder and actual corpus have different dimensions")
        if (
            not np.all(np.isfinite(expected))
            or not np.all(np.isfinite(encoded))
            or not np.linalg.norm(expected)
            or not np.linalg.norm(encoded)
        ):
            raise ValueError("Document validation encountered non-finite or zero vectors")
        cosine = float(
            np.dot(expected, encoded) / (np.linalg.norm(expected) * np.linalg.norm(encoded))
        )
        results.append({"arxiv_id": identifier, "cosine": cosine})
    minimum = min(result["cosine"] for result in results)
    return {
        "sample_count": len(results),
        "seed": seed,
        "required_cosine": min_cosine,
        "minimum_cosine": minimum,
        "mean_cosine": sum(result["cosine"] for result in results) / len(results),
        "passed": minimum >= min_cosine,
        "papers": results,
        "input_format": "search_document: Title: <title>\nAbstract: <abstract>",
        "max_tokens": 512,
        "model": encoder.model_id,
        "revision": encoder.revision,
        "code_revision": encoder.code_revision,
    }


def main() -> None:
    """Write an auditable quality receipt for supplied real queries and corpus artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-path", type=Path, required=True)
    parser.add_argument(
        "--queries", type=Path, required=True, help="JSONL id/text/embedding/date_max/blocked"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=200)
    parser.add_argument("--min-recall", type=float, default=0.98)
    parser.add_argument("--nprobe", type=int, action="append")
    parser.add_argument("--model-cache", type=Path)
    parser.add_argument("--validate-documents", type=int, default=16)
    parser.add_argument("--min-document-cosine", type=float, default=0.999)
    parser.add_argument(
        "--index-only", action="store_true", help="omit model-space gate; not deployment validation"
    )
    args = parser.parse_args()
    corpus = SQLiteCorpus(
        args.snapshot_path / "metadata.sqlite", args.snapshot_path / "index.faiss"
    )
    encoder = NomicQueryEncoder(cache=args.model_cache)
    queries = []
    for line in args.queries.read_text().splitlines():
        if not line.strip():
            continue
        query = json.loads(line)
        if "embedding" not in query:
            query["embedding"] = encoder.embed(query["text"])
            query["kind"] = "nomic-search-query"
        queries.append(query)
    receipt = evaluate_index(
        corpus,
        queries,
        top_k=args.top_k,
        nprobes=args.nprobe,
        min_recall=args.min_recall,
    )
    receipt["queries_sha256"] = file_sha256(args.queries)
    receipt["manifest_sha256"] = file_sha256(args.snapshot_path / "manifest.json")
    if not args.index_only:
        receipt["document_space"] = validate_document_space(
            corpus,
            encoder,
            samples=args.validate_documents,
            min_cosine=args.min_document_cosine,
        )
    receipt["deployment_gate_passed"] = bool(
        receipt["active_configuration_passed"] and receipt.get("document_space", {}).get("passed")
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    passed = (
        receipt["active_configuration_passed"]
        if args.index_only
        else receipt["deployment_gate_passed"]
    )
    print(f"Quality receipt: {args.out}; {'passed' if passed else 'failed'}", flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
