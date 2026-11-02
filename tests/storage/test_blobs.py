"""Atomic corpus artifact downloads and credential-free transport validation."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.storage.artifacts import load_snapshot, parse_manifest
from src.storage.blobs import (
    BlobIntegrityError,
    BlobStorageError,
    blob_service_from_environment,
    download_blob,
    read_blob,
    validate_blob_name,
    validate_container,
    validate_segment,
)


def install_snapshot(fake_blobs, snapshot_id="snapshot-1"):
    contents = {"vectors": b"FAISS bytes", "metadata": b"SQLite bytes", "graph": b"Graph NPZ bytes"}
    containers = {"vectors": "vector-indexes", "metadata": "metadata", "graph": "citation-graphs"}
    references = {}
    for role, body in contents.items():
        blob = f"snapshots/{snapshot_id}/{role}"
        fake_blobs.objects[(containers[role], blob)] = body
        references[role] = {
            "container": containers[role], "blob": blob,
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    manifest = {
        "version": 1, "snapshot_id": snapshot_id,
        "embedding": {"dimension": 4, "model": "test-embedding"}, "artifacts": references,
    }
    fake_blobs.objects[("metadata", "manifest.json")] = json.dumps(manifest).encode()
    return manifest, contents


@pytest.mark.parametrize(
    "name", ["../index", "/index", "a/../index", "a\\index", "a//index", "a/./index", "a\x00b"]
)
def test_blob_paths_reject_traversal(name):
    with pytest.raises(ValueError):
        validate_blob_name(name)


@pytest.mark.parametrize("name", [".", "..", "../report", "a/b", ".working"])
def test_local_segments_reject_hidden_or_traversing_names(name):
    with pytest.raises(ValueError):
        validate_segment(name)


@pytest.mark.parametrize("name", ["a", "../metadata", "BadName", "bad--name", "-bad"])
def test_container_names_are_validated(name):
    with pytest.raises(ValueError):
        validate_container(name)


def test_checksum_failure_preserves_existing_file(fake_blobs, tmp_path: Path):
    fake_blobs.objects[("vectors", "index.faiss")] = b"corrupted new payload"
    target = tmp_path / "index.faiss"
    target.write_bytes(b"known good")
    with pytest.raises(BlobIntegrityError):
        download_blob(fake_blobs, "vectors", "index.faiss", target, "0" * 64)
    assert target.read_bytes() == b"known good"
    assert list(tmp_path.iterdir()) == [target]


def test_interrupted_download_preserves_existing_file(fake_blobs, tmp_path: Path):
    body = b"complete new payload"
    fake_blobs.objects[("vectors", "index.faiss")] = body
    fake_blobs.fail_download = lambda key: True
    target = tmp_path / "index.faiss"
    target.write_bytes(b"known good")
    with pytest.raises(BlobStorageError):
        download_blob(
            fake_blobs, "vectors", "index.faiss", target, hashlib.sha256(body).hexdigest()
        )
    assert target.read_bytes() == b"known good"
    assert list(tmp_path.iterdir()) == [target]


def test_bounded_metadata_refuses_large_payload(fake_blobs):
    fake_blobs.objects[("metadata", "manifest.json")] = b"large metadata"
    with pytest.raises(BlobStorageError, match="permitted metadata size"):
        read_blob(fake_blobs, "metadata", "manifest.json", max_bytes=4)


def test_snapshot_is_published_only_when_all_downloads_verify(fake_blobs, tmp_path: Path):
    _, contents = install_snapshot(fake_blobs)
    snapshot = load_snapshot(fake_blobs, "metadata", "manifest.json", tmp_path)
    assert snapshot.index.read_bytes() == contents["vectors"]
    assert snapshot.database.read_bytes() == contents["metadata"]
    assert snapshot.graph.read_bytes() == contents["graph"]
    assert snapshot.embedding_dimension == 4
    assert snapshot.embedding_model == "test-embedding"
    assert sorted(path.name for path in tmp_path.iterdir()) == [snapshot.root.name]
    before = list(fake_blobs.downloads)
    assert load_snapshot(fake_blobs, "metadata", "manifest.json", tmp_path).root == snapshot.root
    assert fake_blobs.downloads[len(before):] == [("metadata", "manifest.json")]


def test_new_bad_snapshot_never_overwrites_previous_complete_snapshot(fake_blobs, tmp_path: Path):
    install_snapshot(fake_blobs)
    original = load_snapshot(fake_blobs, "metadata", "manifest.json", tmp_path)
    manifest, _ = install_snapshot(fake_blobs, "snapshot-2")
    reference = manifest["artifacts"]["graph"]
    fake_blobs.objects[(reference["container"], reference["blob"])] = b"wrong graph"
    with pytest.raises(BlobIntegrityError):
        load_snapshot(fake_blobs, "metadata", "manifest.json", tmp_path)
    assert original.index.read_bytes() == b"FAISS bytes"
    assert list(tmp_path.iterdir()) == [original.root]


def test_cached_artifact_corruption_is_detected(fake_blobs, tmp_path: Path):
    install_snapshot(fake_blobs)
    snapshot = load_snapshot(fake_blobs, "metadata", "manifest.json", tmp_path)
    snapshot.database.write_bytes(b"bad cache")
    with pytest.raises(BlobIntegrityError):
        load_snapshot(fake_blobs, "metadata", "manifest.json", tmp_path)
    assert snapshot.database.read_bytes() == b"bad cache"


def test_manifest_cannot_escape_blob_or_snapshot_paths(fake_blobs):
    manifest, _ = install_snapshot(fake_blobs)
    manifest["snapshot_id"] = "../other"
    with pytest.raises(ValueError):
        parse_manifest(json.dumps(manifest).encode())
    manifest["snapshot_id"] = "valid"
    manifest["artifacts"]["metadata"]["blob"] = "../metadata.sqlite"
    with pytest.raises(ValueError):
        parse_manifest(json.dumps(manifest).encode())


def test_manifest_requires_explicit_version_dimension_and_checksums(fake_blobs):
    manifest, _ = install_snapshot(fake_blobs)
    for key, value in [
        ("version", 2), ("version", True), ("version", 1.0),
        ("embedding", {"dimension": True}),
    ]:
        with pytest.raises(ValueError):
            parse_manifest(json.dumps(manifest | {key: value}).encode())
    manifest["artifacts"]["vectors"]["sha256"] = "missing"
    with pytest.raises(ValueError):
        parse_manifest(json.dumps(manifest).encode())


def test_production_connection_strings_are_rejected_before_loading_sdk(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "BlobEndpoint=https://account.blob.core.windows.net;AccountName=account;AccountKey=private")
    with pytest.raises(ValueError, match="only for local Azurite"):
        blob_service_from_environment()


def test_account_url_refuses_embedded_credentials_or_sas(monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("GRAPHIV_STORAGE_ACCOUNT_URL", "https://account.blob.core.windows.net?sig=private")
    with pytest.raises(ValueError, match="HTTPS account URL"):
        blob_service_from_environment()


def test_managed_identity_uses_the_configured_client_id(monkeypatch):
    import azure.identity
    import azure.storage.blob

    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("GRAPHIV_STORAGE_ACCOUNT_URL", "https://graphiv.blob.core.windows.net")
    monkeypatch.setenv("AZURE_CLIENT_ID", "identity-client-id")
    observed = {}

    def credential(**kwargs):
        observed["credential"] = kwargs
        return SimpleNamespace()

    def service(**kwargs):
        observed["service"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", credential)
    monkeypatch.setattr(azure.storage.blob, "BlobServiceClient", service)
    _ = blob_service_from_environment()
    assert observed["credential"]["managed_identity_client_id"] == "identity-client-id"
    assert observed["service"]["account_url"] == "https://graphiv.blob.core.windows.net"
