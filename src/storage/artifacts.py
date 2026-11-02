"""Download immutable FAISS, SQLite, and graph snapshots from an Azure manifest."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.storage.blobs import (
    BlobIntegrityError,
    download_blob,
    file_sha256,
    read_blob,
    validate_blob_name,
    validate_checksum,
    validate_container,
    validate_segment,
)

ARTIFACT_FILENAMES = {
    "vectors": "index.faiss",
    "metadata": "metadata.sqlite",
    "graph": "graph.npz",
}


@dataclass(frozen=True)
class Artifact:
    """The immutable location and digest of one runtime corpus file."""

    container: str
    blob: str
    sha256: str


@dataclass(frozen=True)
class ArtifactManifest:
    """Version one manifest, with FAISS labels mapped by SQLite vector_ids."""

    snapshot_id: str
    embedding_dimension: int
    embedding_model: str
    artifacts: dict[str, Artifact]
    raw: dict[str, Any]


@dataclass(frozen=True)
class Snapshot:
    """A fully verified immutable local runtime snapshot."""

    root: Path
    database: Path
    index: Path
    graph: Path
    embedding_dimension: int
    embedding_model: str
    manifest: ArtifactManifest


def parse_manifest(body: bytes) -> ArtifactManifest:
    """Validate the versioned artifact manifest before following any object references."""
    raw = json.loads(body)
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("version"), int)
        or isinstance(raw.get("version"), bool)
        or raw.get("version") != 1
    ):
        raise ValueError("Unsupported artifact manifest version")
    snapshot_id = validate_segment(raw.get("snapshot_id"))
    embedding = raw.get("embedding")
    if not isinstance(embedding, dict):
        raise ValueError("The artifact manifest needs embedding metadata")
    dimension = embedding.get("dimension")
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
        raise ValueError("The artifact embedding dimension must be a positive integer")
    model = embedding.get("model", "")
    if not isinstance(model, str):
        raise ValueError("The artifact embedding model must be a string")
    references = raw.get("artifacts")
    if not isinstance(references, dict):
        raise ValueError("The artifact manifest needs an artifacts object")
    artifacts: dict[str, Artifact] = {}
    for role in ARTIFACT_FILENAMES:
        reference = references.get(role)
        if not isinstance(reference, dict):
            raise ValueError(f"The artifact manifest is missing {role}")
        artifacts[role] = Artifact(
            container=validate_container(reference.get("container")),
            blob=validate_blob_name(reference.get("blob")),
            sha256=validate_checksum(reference.get("sha256")),
        )
    return ArtifactManifest(snapshot_id, dimension, model, artifacts, raw)


def _snapshot(root: Path, manifest: ArtifactManifest) -> Snapshot:
    return Snapshot(
        root=root,
        database=root / ARTIFACT_FILENAMES["metadata"],
        index=root / ARTIFACT_FILENAMES["vectors"],
        graph=root / ARTIFACT_FILENAMES["graph"],
        embedding_dimension=manifest.embedding_dimension,
        embedding_model=manifest.embedding_model,
        manifest=manifest,
    )


def _verify_cache(root: Path, body: bytes, manifest: ArtifactManifest) -> None:
    marker = root / "manifest.json"
    if (
        root.is_symlink()
        or marker.is_symlink()
        or not marker.is_file()
        or marker.read_bytes() != body
    ):
        raise BlobIntegrityError("The cached snapshot manifest does not match")
    for role, reference in manifest.artifacts.items():
        path = root / ARTIFACT_FILENAMES[role]
        if path.is_symlink() or not path.is_file() or file_sha256(path) != reference.sha256:
            raise BlobIntegrityError("A cached runtime artifact failed SHA-256 verification")


def load_snapshot(
    service: Any,
    metadata_container: str,
    manifest_blob: str,
    cache_root: Path,
) -> Snapshot:
    """Publish a local snapshot directory only after all three downloads verify."""
    body = read_blob(service, metadata_container, manifest_blob)
    manifest = parse_manifest(body)
    cache_root = Path(cache_root).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(body).hexdigest()[:20]
    target = cache_root / f"{manifest.snapshot_id}-{digest}"
    if target.exists() or target.is_symlink():
        _verify_cache(target, body, manifest)
        return _snapshot(target, manifest)
    with tempfile.TemporaryDirectory(prefix=".snapshot-", dir=cache_root) as directory:
        staging = Path(directory) / "complete"
        staging.mkdir()
        for role, reference in manifest.artifacts.items():
            _ = download_blob(
                service, reference.container, reference.blob,
                staging / ARTIFACT_FILENAMES[role], reference.sha256,
            )
        _ = (staging / "manifest.json").write_bytes(body)
        try:
            os.rename(staging, target)
        except OSError as error:
            if error.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                raise
            # A concurrent loader can publish the same immutable snapshot first.
            _verify_cache(target, body, manifest)
    return _snapshot(target, manifest)
