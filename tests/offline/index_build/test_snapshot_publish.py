"""Artifact publication is immutable, resumable, and activates the manifest last."""

import hashlib
import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from offline.index_build.publish import publish_snapshot
from src.storage.artifacts import ARTIFACT_FILENAMES, load_snapshot
from src.storage.blobs import BlobIntegrityError, BlobStorageError, blob_service_from_environment


class Service:
    def __init__(self):
        self.objects = {}
        self.metadata = {}
        self.uploads = []
        self.fail = None

    def get_blob_client(self, container, blob):
        service = self
        key = (container, blob)

        class Blob:
            def get_blob_properties(self):
                if key not in service.objects:
                    raise FileNotFoundError(blob)
                return SimpleNamespace(
                    size=len(service.objects[key]), metadata=service.metadata[key]
                )

            def upload_blob(self, data, overwrite=False, metadata=None):
                if service.fail and service.fail(key):
                    raise OSError("interrupted upload")
                if not overwrite and key in service.objects:
                    raise OSError("object exists")
                service.uploads.append(key)
                service.objects[key] = data if isinstance(data, bytes) else data.read()
                service.metadata[key] = metadata or {}

        return Blob()


def snapshot(root: Path, snapshot_id="snapshot-1"):
    root.mkdir()
    containers = {"vectors": "vector-indexes", "metadata": "metadata", "graph": "citation-graphs"}
    artifacts = {}
    for role, filename in ARTIFACT_FILENAMES.items():
        data = f"{snapshot_id} {role}".encode()
        (root / filename).write_bytes(data)
        artifacts[role] = {
            "container": containers[role], "blob": f"snapshots/{snapshot_id}/{filename}",
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    body = json.dumps({
        "version": 1, "snapshot_id": snapshot_id,
        "embedding": {"dimension": 4}, "artifacts": artifacts,
    }).encode()
    (root / "manifest.json").write_bytes(body)
    return root


def test_activation_happens_after_all_immutable_payloads_and_manifest(tmp_path: Path):
    service = Service()
    local = snapshot(tmp_path / "snapshot")
    result = publish_snapshot(service, local, activate=True)
    assert service.uploads[-2:] == [
        ("metadata", "snapshots/snapshot-1/manifest.json"), ("metadata", "manifest.json")
    ]
    assert result["activated"] is True
    assert result["uploaded"] == 4
    assert service.objects[("metadata", "manifest.json")] == (local / "manifest.json").read_bytes()


def test_default_publication_does_not_switch_the_active_manifest(tmp_path: Path):
    service = Service()
    publish_snapshot(service, snapshot(tmp_path / "snapshot"))
    assert ("metadata", "manifest.json") not in service.objects


def test_all_local_checksums_are_verified_before_any_remote_write(tmp_path: Path):
    service = Service()
    local = snapshot(tmp_path / "snapshot")
    (local / "graph.npz").write_bytes(b"corrupted")
    with pytest.raises(BlobIntegrityError):
        publish_snapshot(service, local, activate=True)
    assert service.uploads == []


def test_repeated_publication_reuses_identical_immutable_objects(tmp_path: Path):
    service = Service()
    local = snapshot(tmp_path / "snapshot")
    publish_snapshot(service, local, activate=True)
    service.uploads.clear()
    result = publish_snapshot(service, local, activate=True)
    assert result["reused"] == 4
    assert result["uploaded"] == 0
    assert service.uploads == [("metadata", "manifest.json")]


def test_a_conflicting_immutable_object_is_not_overwritten(tmp_path: Path):
    service = Service()
    local = snapshot(tmp_path / "snapshot")
    key = ("vector-indexes", "snapshots/snapshot-1/index.faiss")
    service.objects[key] = b"previous data"
    service.metadata[key] = {"sha256": "0" * 64}
    with pytest.raises(BlobIntegrityError):
        publish_snapshot(service, local, activate=True)
    assert service.objects[key] == b"previous data"
    assert service.uploads == []


def test_failed_replacement_preserves_the_previous_active_manifest(tmp_path: Path):
    service = Service()
    publish_snapshot(service, snapshot(tmp_path / "old"), activate=True)
    previous = service.objects[("metadata", "manifest.json")]
    service.fail = lambda key: key[1].endswith("graph.npz")
    with pytest.raises(BlobStorageError):
        publish_snapshot(service, snapshot(tmp_path / "new", "snapshot-2"), activate=True)
    assert service.objects[("metadata", "manifest.json")] == previous


def test_partial_publication_can_resume_without_deleting_existing_objects(tmp_path: Path):
    service = Service()
    local = snapshot(tmp_path / "snapshot")
    service.fail = lambda key: key[1].endswith("graph.npz")
    with pytest.raises(BlobStorageError):
        publish_snapshot(service, local, activate=True)
    service.fail = None
    result = publish_snapshot(service, local, activate=True)
    assert result["reused"] == 2
    assert result["uploaded"] == 2
    assert result["activated"] is True


def test_activation_cannot_overwrite_the_immutable_snapshot_namespace(tmp_path: Path):
    service = Service()
    with pytest.raises(ValueError, match="immutable snapshots namespace"):
        publish_snapshot(
            service, snapshot(tmp_path / "snapshot"), activate=True,
            manifest_blob="snapshots/another/manifest.json",
        )
    assert service.uploads == []


@pytest.mark.slow
def test_azurite_publish_activate_reuse_and_runtime_download(tmp_path: Path, monkeypatch):
    connection = os.environ.get("GRAPHIV_TEST_AZURITE_CONNECTION_STRING")
    if not connection:
        pytest.skip("Set GRAPHIV_TEST_AZURITE_CONNECTION_STRING for local Azurite integration")
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", connection)
    service = blob_service_from_environment()
    local = snapshot(tmp_path / "snapshot")
    manifest = json.loads((local / "manifest.json").read_bytes())
    suffix = uuid.uuid4().hex[:12]
    created = []
    try:
        for role, reference in manifest["artifacts"].items():
            container = f"publisher-{role}-{suffix}"
            service.create_container(container)
            created.append(container)
            reference["container"] = container
        (local / "manifest.json").write_text(json.dumps(manifest))
        result = publish_snapshot(service, local, activate=True)
        assert result["uploaded"] == 4
        assert publish_snapshot(service, local, activate=True)["reused"] == 4
        runtime = load_snapshot(
            service, manifest["artifacts"]["metadata"]["container"],
            "manifest.json", tmp_path / "cache",
        )
        assert runtime.index.read_bytes() == (local / "index.faiss").read_bytes()
        assert runtime.database.read_bytes() == (local / "metadata.sqlite").read_bytes()
    finally:
        for container in created:
            service.delete_container(container)
