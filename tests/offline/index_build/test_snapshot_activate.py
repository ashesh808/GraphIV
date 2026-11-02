"""Synthetic guard tests only; these are not actual corpus quality or activation proof."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from offline.index_build import activate
from src.storage.artifacts import ARTIFACT_FILENAMES
from src.storage.blobs import BlobInfo, BlobNotFoundError


@pytest.fixture
def unit_activation(tmp_path: Path, monkeypatch):
    """Use tiny mocked objects with the receipt schema; never access Azure or real data."""
    objects, information, reads, writes = {}, {}, [], []
    snapshot_id = "unit-activation-guards"
    references = {}
    containers = {"vectors": "vector-indexes", "metadata": "metadata", "graph": "citation-graphs"}
    for role, filename in ARTIFACT_FILENAMES.items():
        data = ("unit-test-only-" + role).encode()
        digest = hashlib.sha256(data).hexdigest()
        key = (containers[role], f"snapshots/{snapshot_id}/{filename}")
        objects[key] = data
        information[key] = BlobInfo(len(data), digest)
        references[role] = {"container": key[0], "blob": key[1], "sha256": digest}
    manifest = {
        "version": 1,
        "snapshot_id": snapshot_id,
        "embedding": {"dimension": 768, "model": "nomic-embed-text-v2-moe"},
        "artifacts": references,
        "counts": {**activate.COUNTS, "embedded": activate.COUNTS["papers"]},
        "source": {
            "repository": activate.SOURCE[0],
            "revision": activate.SOURCE[1],
            "commit": activate.SOURCE[2],
            "rows": activate.COUNTS,
        },
        "capabilities": {
            "precomputed_intents": True,
            "intent_confidence": True,
            "citation_sentences": False,
        },
        "index": {"kind": "ivfsq8", "nprobe": 128, "dimension": 768, "vector_dtype": "float16"},
    }
    body = json.dumps(manifest).encode()
    expected = hashlib.sha256(body).hexdigest()
    candidate = ("metadata", f"snapshots/{snapshot_id}/manifest.json")
    objects[candidate] = body
    objects[("metadata", "manifest.json")] = b"previous immutable manifest bytes"
    source_queries = [
        json.loads(line) for line in activate.VALIDATION_QUERIES.read_bytes().splitlines()
    ]
    queries = [
        {
            "query_id": query["id"],
            "query_kind": "nomic-search-query",
            "date_max": query.get("date_max"),
            "blocked_count": len(query.get("blocked", [])),
            "returned": 200,
            "eligible_gold": 200,
            "recall_at_k": 1.0,
            "max_abs_score_error": 0.0,
        }
        for query in source_queries
    ]
    receipt = {
        "manifest_sha256": expected,
        "deployment_gate_passed": True,
        "active_configuration_passed": True,
        "minimum_required_recall": 0.98,
        "active_nprobe": 128,
        "index_kind": "ivfsq8",
        "dimension": 768,
        "vector_dtype": "float16",
        "query_count": 13,
        "top_k": 200,
        "queries_sha256": activate.VALIDATION_QUERIES_SHA256,
        "sqlite_bytes": information[("metadata", references["metadata"]["blob"])].size,
        "index_bytes": information[("vector-indexes", references["vectors"]["blob"])].size,
        "configurations": [
            {
                "nprobe": 128,
                "passed": True,
                "minimum_recall_at_k": 1.0,
                "max_abs_score_error": 0.0,
                "queries": queries,
            }
        ],
        "document_space": {
            "passed": True,
            "sample_count": 16,
            "required_cosine": 0.999,
            "minimum_cosine": 1.0,
            "papers": [{"arxiv_id": f"unit-{i}", "cosine": 1.0} for i in range(16)],
        },
    }
    receipt_path = tmp_path / "unit-receipt.json"
    receipt_path.write_text(json.dumps(receipt))

    def read(_service, container, blob):
        reads.append((container, blob))
        if (container, blob) not in objects:
            raise BlobNotFoundError(blob)
        return objects[(container, blob)]

    def upload(_service, container, blob, data, *, overwrite=False, metadata=None):
        writes.append((container, blob, overwrite, metadata))
        objects[(container, blob)] = data

    monkeypatch.setattr(activate, "read_blob", read)
    monkeypatch.setattr(
        activate, "blob_info", lambda _service, container, blob: information.get((container, blob))
    )
    monkeypatch.setattr(activate, "upload_blob", upload)
    options = {
        "quality_receipt": receipt_path,
        "manifest_sha256": expected,
        "snapshot_id": snapshot_id,
        "out": tmp_path / "review",
        "metadata_container": "metadata",
        "manifest_blob": "manifest.json",
    }
    return SimpleNamespace(
        objects=objects,
        information=information,
        reads=reads,
        writes=writes,
        receipt=receipt,
        receipt_path=receipt_path,
        manifest=manifest,
        candidate=candidate,
        options=options,
        read=read,
    )


def test_default_dry_run_saves_exact_candidate_and_rollback_without_cloud_writes(unit_activation):
    unit = unit_activation
    previous = unit.objects[("metadata", "manifest.json")]
    review = activate.activate_snapshot(None, **unit.options)
    assert review["activated"] is False
    assert review["execute_requested"] is False
    assert (unit.options["out"] / "previous-manifest.json").read_bytes() == previous
    assert review["previous_sha256"] == hashlib.sha256(previous).hexdigest()
    assert (unit.options["out"] / "candidate-manifest.json").read_bytes() == unit.objects[
        unit.candidate
    ]
    assert unit.writes == []


def test_execute_overwrites_only_active_alias_after_local_backup(unit_activation):
    unit = unit_activation
    review = activate.activate_snapshot(None, execute=True, **unit.options)
    assert review["activated"] is True
    assert unit.writes == [
        ("metadata", "manifest.json", True, {"sha256": unit.options["manifest_sha256"]})
    ]
    assert unit.objects[("metadata", "manifest.json")] == unit.objects[unit.candidate]
    assert (
        json.loads((unit.options["out"] / "review.json").read_text())["readback_sha256"]
        == unit.options["manifest_sha256"]
    )


def test_missing_old_alias_is_recorded_without_inventing_rollback_bytes(unit_activation):
    unit = unit_activation
    del unit.objects[("metadata", "manifest.json")]
    review = activate.activate_snapshot(None, **unit.options)
    assert review["previous_exists"] is False and review["previous_sha256"] is None
    assert not (unit.options["out"] / "previous-manifest.json").exists()
    assert unit.writes == []


@pytest.mark.parametrize(
    "path,value",
    [
        (("deployment_gate_passed",), 1),
        (("active_configuration_passed",), False),
        (("minimum_required_recall",), 0.97),
        (("top_k",), 1),
        (("top_k",), True),
        (("query_count",), 1),
        (("queries_sha256",), "0" * 64),
        (("active_nprobe",), 256),
        (("index_kind",), "flat"),
        (("dimension",), 1536),
        (("vector_dtype",), "float32"),
        (("document_space", "passed"), False),
        (("document_space", "sample_count"), 15),
        (("document_space", "minimum_cosine"), 0.998),
        (("configurations", 0, "queries", 0, "recall_at_k"), 0.97),
        (("configurations", 0, "queries", 0, "max_abs_score_error"), 1e-7),
        (("configurations", 0, "queries", 0, "query_id"), "different-query"),
        (("configurations", 0, "queries", 0, "query_kind"), "provided-query-embedding"),
        (("configurations", 0, "queries", 0, "query_kind"), None),
        (("configurations", 0, "queries", 0, "date_max"), "2000-01-01"),
        (("configurations", 0, "queries", 0, "blocked_count"), True),
        (("configurations", 0, "queries", 0, "returned"), 199),
        (("configurations", 0, "queries", 0, "eligible_gold"), 1),
        (("configurations", 0, "queries"), []),
    ],
)
def test_quality_guards_never_write_when_evidence_is_missing_or_inconsistent(
    unit_activation, path, value
):
    unit = unit_activation
    target = unit.receipt
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    unit.receipt_path.write_text(json.dumps(unit.receipt))
    with pytest.raises(ValueError):
        activate.activate_snapshot(None, execute=True, **unit.options)
    assert unit.writes == []


def test_committed_evaluation_file_matches_its_pinned_checksum():
    assert hashlib.sha256(activate.VALIDATION_QUERIES.read_bytes()).hexdigest() == (
        activate.VALIDATION_QUERIES_SHA256
    )


def test_consistent_single_query_top_one_receipt_cannot_weaken_evaluation(unit_activation):
    unit = unit_activation
    unit.receipt.update(query_count=1, top_k=1)
    query = unit.receipt["configurations"][0]["queries"][0]
    unit.receipt["configurations"][0]["queries"] = [query]
    query.update(returned=1, eligible_gold=1)
    unit.receipt_path.write_text(json.dumps(unit.receipt))
    with pytest.raises(ValueError, match="13 queries evaluated at top-200"):
        activate.activate_snapshot(None, execute=True, **unit.options)
    assert unit.writes == []


def test_duplicate_query_ids_cannot_replace_missing_committed_coverage(unit_activation):
    unit = unit_activation
    queries = unit.receipt["configurations"][0]["queries"]
    queries[-1] = deepcopy(queries[0])
    unit.receipt_path.write_text(json.dumps(unit.receipt))
    with pytest.raises(ValueError, match="distinct committed set"):
        activate.activate_snapshot(None, execute=True, **unit.options)
    assert unit.writes == []


@pytest.mark.parametrize("field", ["date_max", "blocked_count"])
def test_committed_date_and_exclusion_filters_cannot_be_omitted(unit_activation, field):
    unit = unit_activation
    queries = unit.receipt["configurations"][0]["queries"]
    query = next(row for row in queries if row[field])
    del query[field]
    unit.receipt_path.write_text(json.dumps(unit.receipt))
    with pytest.raises(ValueError, match="committed queries"):
        activate.activate_snapshot(None, execute=True, **unit.options)
    assert unit.writes == []


def test_alternative_probe_rows_must_cover_the_same_evaluation(unit_activation):
    unit = unit_activation
    alternative = deepcopy(unit.receipt["configurations"][0])
    alternative["nprobe"] = 256
    alternative["queries"].pop()
    unit.receipt["configurations"].append(alternative)
    unit.receipt_path.write_text(json.dumps(unit.receipt))
    with pytest.raises(ValueError, match="all 13 committed query rows"):
        activate.activate_snapshot(None, execute=True, **unit.options)
    assert unit.writes == []


def test_failed_alternative_probe_does_not_invalidate_passing_active_probe(unit_activation):
    unit = unit_activation
    alternative = deepcopy(unit.receipt["configurations"][0])
    alternative.update(nprobe=256, passed=False, minimum_recall_at_k=0.5)
    alternative["queries"][0]["recall_at_k"] = 0.5
    unit.receipt["configurations"].append(alternative)
    unit.receipt_path.write_text(json.dumps(unit.receipt))
    assert activate.activate_snapshot(None, **unit.options)["status"] == "reviewed"
    assert unit.writes == []


def test_altered_packaged_query_file_cannot_redefine_the_pinned_evaluation(
    unit_activation, monkeypatch, tmp_path
):
    unit = unit_activation
    altered = tmp_path / "altered-queries.jsonl"
    altered.write_bytes(activate.VALIDATION_QUERIES.read_bytes() + b"\n")
    monkeypatch.setattr(activate, "VALIDATION_QUERIES", altered)
    with pytest.raises(ValueError, match="Packaged validation queries"):
        activate.activate_snapshot(None, execute=True, **unit.options)
    assert unit.writes == []


def test_receipt_manifest_digest_mismatch_fails_before_remote_reads(unit_activation):
    unit = unit_activation
    with pytest.raises(ValueError, match="quality receipt"):
        activate.activate_snapshot(None, **{**unit.options, "manifest_sha256": "0" * 64})
    assert unit.reads == [] and unit.writes == []


@pytest.mark.parametrize(
    "role,kind", [("vectors", "hash"), ("metadata", "size"), ("graph", "producer-size")]
)
def test_published_artifact_properties_and_producer_sizes_must_match(unit_activation, role, kind):
    unit = unit_activation
    reference = unit.manifest["artifacts"][role]
    key = (reference["container"], reference["blob"])
    info = unit.information[key]
    options = unit.options
    if kind == "hash":
        unit.information[key] = BlobInfo(info.size, "0" * 64)
    elif kind == "size":
        unit.information[key] = BlobInfo(info.size + 1, info.sha256)
    else:
        sizes = {
            r: unit.information[(ref["container"], ref["blob"])].size
            for r, ref in unit.manifest["artifacts"].items()
        }
        sizes["graph"] += 1
        options = {**options, "producer_sizes": sizes}
    with pytest.raises(ValueError):
        activate.activate_snapshot(None, execute=True, **options)
    assert unit.writes == []


def test_active_alias_cannot_target_any_immutable_snapshot_path(unit_activation):
    unit = unit_activation
    with pytest.raises(ValueError, match="immutable snapshots"):
        activate.activate_snapshot(
            None, **{**unit.options, "manifest_blob": "snapshots/other/manifest.json"}
        )
    assert unit.reads == [] and unit.writes == []


def test_source_pin_rejects_an_otherwise_hash_matched_wrong_release(unit_activation):
    unit = unit_activation
    unit.manifest["source"]["commit"] = "0" * 40
    body = json.dumps(unit.manifest).encode()
    expected = hashlib.sha256(body).hexdigest()
    unit.objects[unit.candidate] = body
    unit.receipt["manifest_sha256"] = expected
    unit.receipt_path.write_text(json.dumps(unit.receipt))
    with pytest.raises(ValueError, match="pinned published"):
        activate.activate_snapshot(
            None, **{**unit.options, "manifest_sha256": expected}, execute=True
        )
    assert unit.writes == []


def test_failed_readback_records_the_single_write_and_retains_rollback(
    unit_activation, monkeypatch
):
    unit = unit_activation
    previous = unit.objects[("metadata", "manifest.json")]

    def read(service, container, blob):
        if unit.writes and blob == "manifest.json":
            return b"unexpected replacement"
        return unit.read(service, container, blob)

    monkeypatch.setattr(activate, "read_blob", read)
    with pytest.raises(ValueError, match="readback"):
        activate.activate_snapshot(None, execute=True, **unit.options)
    review = json.loads((unit.options["out"] / "review.json").read_text())
    assert review["status"] == "readback_failed" and review["activated"] is None
    assert review["write_attempted"] is True and review["write_completed"] is True
    assert len(unit.writes) == 1
    assert (unit.options["out"] / "previous-manifest.json").read_bytes() == previous


def test_upload_error_retains_unknown_remote_outcome_and_never_retries(
    unit_activation, monkeypatch
):
    unit = unit_activation
    previous = unit.objects[("metadata", "manifest.json")]

    def ambiguous_upload(_service, container, blob, data, **kwargs):
        unit.writes.append((container, blob))
        unit.objects[(container, blob)] = data
        raise OSError("The response failed after the server accepted bytes")

    monkeypatch.setattr(activate, "upload_blob", ambiguous_upload)
    with pytest.raises(OSError):
        activate.activate_snapshot(None, execute=True, **unit.options)
    review = json.loads((unit.options["out"] / "review.json").read_text())
    assert review["status"] == "upload_failed" and review["activated"] is None
    assert review["write_attempted"] is True and review["write_completed"] is False
    assert len(unit.writes) == 1
    assert (unit.options["out"] / "previous-manifest.json").read_bytes() == previous


@pytest.mark.parametrize(
    "key,value",
    [
        ("precomputed_intents", 1),
        ("intent_confidence", False),
        ("citation_sentences", 0),
    ],
)
def test_published_capabilities_require_all_literal_boolean_values(unit_activation, key, value):
    unit = unit_activation
    unit.manifest["capabilities"][key] = value
    with pytest.raises(ValueError, match="precomputed intents"):
        activate._published_source(unit.manifest)
    assert unit.writes == []
