"""Review a published snapshot and quality receipt; activate only with --execute."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from src.storage.artifacts import ARTIFACT_FILENAMES, parse_manifest
from src.storage.blobs import (
    BlobNotFoundError,
    blob_info,
    blob_service_from_environment,
    read_blob,
    upload_blob,
    validate_blob_name,
    validate_checksum,
    validate_container,
    validate_segment,
)

COUNTS = {"papers": 3_165_827, "citations": 74_764_672, "topics": 3_165_827}
SOURCE = ("kkuroma/GraphIV", "GraphIV-2026-10-01", "cc781313c13b9cbd08110c97eb84b7e1a62180e1")
VALIDATION_QUERIES = Path(__file__).with_name("validation_queries.jsonl")
VALIDATION_QUERIES_SHA256 = "feaf62345fd4601fefa601cf7b1dcb4a44436f6c4e53b65392bdda8848b1b6a8"
VALIDATION_QUERY_COUNT = 13
VALIDATION_TOP_K = 200


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _number(value: Any, label: str, minimum: float, maximum: float = math.inf) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} must be a measured number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{label} is outside the required bounds")
    return float(value)


def _size(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _validation_queries() -> dict[str, dict[str, Any]]:
    body = VALIDATION_QUERIES.read_bytes()
    if hashlib.sha256(body).hexdigest() != VALIDATION_QUERIES_SHA256:
        raise ValueError("Packaged validation queries differ from the committed evaluation set")
    rows = [json.loads(line) for line in body.splitlines() if line.strip()]
    expected = {row["id"]: row for row in rows}
    if len(rows) != VALIDATION_QUERY_COUNT or len(expected) != VALIDATION_QUERY_COUNT:
        raise ValueError("The committed evaluation must identify 13 distinct queries")
    return expected


def _query_rows(
    config: dict[str, Any], expected: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = config.get("queries")
    if not isinstance(rows, list) or len(rows) != VALIDATION_QUERY_COUNT:
        raise ValueError("Every benchmark configuration requires all 13 committed query rows")
    queries = []
    seen: set[str] = set()
    for raw in rows:
        query = _object(raw, "Benchmark query")
        identifier = query.get("query_id")
        if not isinstance(identifier, str) or identifier not in expected or identifier in seen:
            raise ValueError("Benchmark query identifiers must match the distinct committed set")
        seen.add(identifier)
        if query.get("query_kind") != "nomic-search-query":
            raise ValueError("Every committed query must use the original Nomic query encoder")
        source = expected[identifier]
        if query.get("date_max") != source.get("date_max"):
            raise ValueError("Benchmark historical filters disagree with the committed queries")
        blocked = query.get("blocked_count")
        if type(blocked) is not int or blocked != len(source.get("blocked", [])):
            raise ValueError("Benchmark exclusions disagree with the committed queries")
        if any(
            _size(query.get(key), f"Query {key}") != VALIDATION_TOP_K
            for key in ("returned", "eligible_gold")
        ):
            raise ValueError("Every committed query requires a complete top-200 comparison")
        queries.append(query)
    return queries


def _quality(receipt: dict[str, Any], manifest: dict[str, Any]) -> None:
    if any(
        receipt.get(key) is not True
        for key in ("deployment_gate_passed", "active_configuration_passed")
    ):
        raise ValueError("The real benchmark deployment and active-configuration gates must pass")
    if receipt.get("queries_sha256") != VALIDATION_QUERIES_SHA256:
        raise ValueError("Benchmark queries do not match the committed evaluation checksum")
    if (
        _size(receipt.get("top_k"), "Benchmark top-k") != VALIDATION_TOP_K
        or _size(receipt.get("query_count"), "Benchmark query count") != VALIDATION_QUERY_COUNT
    ):
        raise ValueError("The committed benchmark requires 13 queries evaluated at top-200")
    expected_queries = _validation_queries()
    required = _number(receipt.get("minimum_required_recall"), "Required recall", 0.98, 1)
    index = _object(manifest.get("index"), "Manifest index metrics")
    probe = index.get("nprobe")
    if (
        index.get("kind") not in {"flat", "ivfsq8"}
        or isinstance(probe, bool)
        or not isinstance(probe, int)
        or probe < 0
        or (index.get("kind") == "ivfsq8" and probe == 0)
    ):
        raise ValueError("Manifest index kind/probe settings are missing or invalid")
    if (
        receipt.get("active_nprobe") != index.get("nprobe")
        or receipt.get("index_kind") != index.get("kind")
        or receipt.get("dimension") != index.get("dimension")
        or receipt.get("dimension") != 768
        or receipt.get("vector_dtype") != index.get("vector_dtype")
        or receipt.get("vector_dtype") != "float16"
    ):
        raise ValueError("Benchmark active index settings disagree with the immutable manifest")
    configurations = receipt.get("configurations")
    if not isinstance(configurations, list):
        raise ValueError("Benchmark configurations are missing")
    active = []
    for raw in configurations:
        item = _object(raw, "Benchmark configuration")
        _query_rows(item, expected_queries)
        if item.get("nprobe") == index.get("nprobe"):
            active.append(item)
    if len(active) != 1 or active[0].get("passed") is not True:
        raise ValueError("Exactly one passing active benchmark configuration is required")
    config = active[0]
    queries = _query_rows(config, expected_queries)
    _number(config.get("minimum_recall_at_k"), "Active minimum recall", required, 1)
    _number(config.get("max_abs_score_error"), "Active score error", 0, 1e-8)
    for raw in queries:
        query = _object(raw, "Benchmark query")
        _number(query.get("recall_at_k"), "Query recall", required, 1)
        _number(query.get("max_abs_score_error"), "Query score error", 0, 1e-8)
    documents = _object(receipt.get("document_space"), "Document-space benchmark")
    if documents.get("passed") is not True:
        raise ValueError("Document-space compatibility must pass")
    count = _size(documents.get("sample_count"), "Document sample count")
    papers = documents.get("papers")
    if count < 16 or not isinstance(papers, list) or len(papers) != count:
        raise ValueError("At least 16 actual document comparisons are required")
    cosine = _number(documents.get("required_cosine"), "Required document cosine", 0.999, 1)
    _number(documents.get("minimum_cosine"), "Minimum document cosine", cosine, 1 + 1e-9)
    for raw in papers:
        paper = _object(raw, "Document comparison")
        if not isinstance(paper.get("arxiv_id"), str) or not paper["arxiv_id"]:
            raise ValueError("Document comparison lacks an actual paper identifier")
        _number(paper.get("cosine"), "Document cosine", cosine, 1 + 1e-9)
    if len({paper["arxiv_id"] for paper in papers}) != count:
        raise ValueError("Document comparisons repeat paper identifiers")


def _published_source(manifest: dict[str, Any]) -> None:
    source = _object(manifest.get("source"), "Published source")
    if tuple(source.get(key) for key in ("repository", "revision", "commit")) != SOURCE:
        raise ValueError("The snapshot does not identify the pinned published GraphIV release")
    counts = _object(manifest.get("counts"), "Published counts")
    if (
        any(counts.get(key) != value for key, value in COUNTS.items())
        or counts.get("embedded") != COUNTS["papers"]
    ):
        raise ValueError(
            "The snapshot does not contain every published paper/vector/citation/topic"
        )
    if source.get("rows") != COUNTS:
        raise ValueError("Published source rows disagree with the complete release")
    if manifest.get("embedding") != {"dimension": 768, "model": "nomic-embed-text-v2-moe"}:
        raise ValueError("The published Nomic embedding identity is inconsistent")
    capabilities = _object(manifest.get("capabilities"), "Corpus capabilities")
    if (
        capabilities.get("precomputed_intents") is not True
        or capabilities.get("intent_confidence") is not True
        or capabilities.get("citation_sentences") is not False
    ):
        raise ValueError(
            "The snapshot must declare precomputed intents/confidence and absent sentences"
        )


def _old_alias(service: Any, container: str, alias: str) -> bytes | None:
    try:
        return read_blob(service, container, alias)
    except BlobNotFoundError:
        return None


def _json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def activate_snapshot(
    service: Any,
    *,
    quality_receipt: Path,
    manifest_sha256: str,
    snapshot_id: str,
    out: Path,
    metadata_container: str | None = None,
    manifest_blob: str | None = None,
    producer_sizes: dict[str, int] | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    """Save a local activation review/rollback first; optionally replace one active alias."""
    expected = validate_checksum(manifest_sha256)
    snapshot_id = validate_segment(snapshot_id)
    container = validate_container(
        metadata_container or os.environ.get("GRAPHIV_METADATA_CONTAINER", "metadata")
    )
    alias = validate_blob_name(
        manifest_blob or os.environ.get("GRAPHIV_MANIFEST_BLOB", "manifest.json")
    )
    if alias.split("/")[0] == "snapshots":
        raise ValueError("The active alias cannot overwrite the immutable snapshots namespace")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("Choose an empty activation review/backup directory")
    receipt_body = Path(quality_receipt).read_bytes()
    receipt = _object(json.loads(receipt_body), "Quality receipt")
    if validate_checksum(receipt.get("manifest_sha256")) != expected:
        raise ValueError("Expected manifest checksum disagrees with the quality receipt")
    if producer_sizes is not None:
        producer_sizes = _object(producer_sizes, "Producer sizes")
        if set(producer_sizes) != set(ARTIFACT_FILENAMES):
            raise ValueError("Producer sizes must identify vectors, metadata and graph")
        for role, size in producer_sizes.items():
            _size(size, f"Producer {role} bytes")
    candidate_blob = f"snapshots/{snapshot_id}/manifest.json"
    body = read_blob(service, container, candidate_blob)
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError(
            "Published immutable manifest checksum disagrees with the reviewed receipt"
        )
    parsed = parse_manifest(body)
    if parsed.snapshot_id != snapshot_id:
        raise ValueError("The immutable manifest identifies a different snapshot")
    _published_source(parsed.raw)
    _quality(receipt, parsed.raw)
    properties = {}
    for role, reference in parsed.artifacts.items():
        if reference.blob != f"snapshots/{snapshot_id}/{ARTIFACT_FILENAMES[role]}":
            raise ValueError(
                "Artifact reference is outside its expected immutable snapshot filename"
            )
        info = blob_info(service, reference.container, reference.blob)
        if info is None or validate_checksum(info.sha256) != reference.sha256:
            raise ValueError(f"Published {role} producer checksum does not match the manifest")
        _size(info.size, f"Published {role} bytes")
        if producer_sizes is not None and info.size != producer_sizes[role]:
            raise ValueError(f"Published {role} bytes disagree with producer sizes")
        expected_size = receipt.get(
            {"metadata": "sqlite_bytes", "vectors": "index_bytes"}.get(role, "")
        )
        if role != "graph" and _size(expected_size, f"Benchmark {role} bytes") != info.size:
            raise ValueError(f"Published {role} bytes disagree with the actual benchmark")
        properties[role] = {
            "container": reference.container,
            "blob": reference.blob,
            "bytes": info.size,
            "sha256": reference.sha256,
        }
    previous = _old_alias(service, container, alias)
    previous_sha = hashlib.sha256(previous).hexdigest() if previous is not None else None
    review = {
        "status": "reviewed",
        "execute_requested": execute,
        "activated": False,
        "write_attempted": False,
        "write_completed": False,
        "metadata_container": container,
        "active_alias": alias,
        "snapshot_id": snapshot_id,
        "manifest_blob": candidate_blob,
        "manifest_sha256": expected,
        "quality_receipt_sha256": hashlib.sha256(receipt_body).hexdigest(),
        "previous_exists": previous is not None,
        "previous_sha256": previous_sha,
        "artifacts": properties,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidate-manifest.json").write_bytes(body)
    (out / "quality-receipt.json").write_bytes(receipt_body)
    if previous is not None:
        (out / "previous-manifest.json").write_bytes(previous)
    _json(
        out / "rollback.json",
        {
            "container": container,
            "alias": alias,
            "previous_exists": previous is not None,
            "previous_sha256": previous_sha,
        },
    )
    _json(out / "review.json", review)
    if not execute:
        return review
    if _old_alias(service, container, alias) != previous:
        raise ValueError("The active alias changed after its rollback backup was recorded")
    review.update(status="write_attempted", write_attempted=True, activated=None)
    _json(out / "review.json", review)
    try:
        upload_blob(service, container, alias, body, overwrite=True, metadata={"sha256": expected})
    except Exception as error:  # noqa: BLE001 -- retain exact local activation state on provider failure
        review.update(status="upload_failed", error_type=type(error).__name__)
        _json(out / "review.json", review)
        raise
    review.update(status="write_completed", write_completed=True)
    _json(out / "review.json", review)
    try:
        if read_blob(service, container, alias) != body:
            raise ValueError("Active alias readback disagrees with the reviewed immutable manifest")
    except Exception as error:  # noqa: BLE001 -- never hide that the one alias write already happened
        review.update(status="readback_failed", error_type=type(error).__name__)
        _json(out / "review.json", review)
        raise
    review.update(status="activated", activated=True, readback_sha256=expected)
    _json(out / "review.json", review)
    return review


def main() -> None:
    """Review by default; --execute explicitly allows the single active alias overwrite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-receipt", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--metadata-container")
    parser.add_argument("--manifest-blob")
    parser.add_argument("--producer-sizes", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = vars(parser.parse_args())
    sizes = args.pop("producer_sizes")
    args["producer_sizes"] = json.loads(sizes.read_bytes()) if sizes else None
    result = activate_snapshot(blob_service_from_environment(), **args)
    print(json.dumps({"status": result["status"], "activated": result["activated"]}))


if __name__ == "__main__":
    main()
