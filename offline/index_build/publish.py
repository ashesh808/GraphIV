"""Publish a verified immutable runtime snapshot, activating its manifest only on request."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from src.storage.artifacts import ARTIFACT_FILENAMES, parse_manifest
from src.storage.blobs import (
    BlobIntegrityError,
    BlobStorageError,
    blob_info,
    blob_service_from_environment,
    file_sha256,
    upload_blob,
    validate_blob_name,
    validate_container,
)


def _publish_once(
    service: Any, container: str, name: str, data: Path | bytes, checksum: str
) -> bool:
    size = data.stat().st_size if isinstance(data, Path) else len(data)

    def matches() -> bool | None:
        existing = blob_info(service, container, name)
        if existing is None:
            return None
        return existing.sha256 == checksum and existing.size == size

    matched = matches()
    if matched:
        return False
    if matched is False:
        raise BlobIntegrityError("An immutable snapshot object already exists with different bytes")
    try:
        if isinstance(data, Path):
            with data.open("rb") as handle:
                upload_blob(service, container, name, handle, metadata={"sha256": checksum})
        else:
            upload_blob(service, container, name, data, metadata={"sha256": checksum})
    except BlobStorageError:
        # An identical concurrent publisher may have created the immutable object.
        if matches():
            return False
        raise
    return True


def publish_snapshot(
    service: Any,
    directory: Path,
    *,
    metadata_container: str | None = None,
    manifest_blob: str = "manifest.json",
    activate: bool = False,
) -> dict[str, Any]:
    """Validate all local files, publish immutable objects, then optionally switch the alias."""
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("The snapshot needs a regular manifest.json file")
    body = manifest_path.read_bytes()
    manifest = parse_manifest(body)
    container = validate_container(metadata_container or manifest.artifacts["metadata"].container)
    active_name = validate_blob_name(manifest_blob)
    if activate and active_name.startswith("snapshots/"):
        raise ValueError("An activation alias cannot overwrite the immutable snapshots namespace")
    files: dict[str, Path] = {}
    # Validate the entire local snapshot before the first remote write.
    for role, filename in ARTIFACT_FILENAMES.items():
        path = directory / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"The snapshot needs a regular {filename} file")
        if file_sha256(path) != manifest.artifacts[role].sha256:
            raise BlobIntegrityError("A local snapshot artifact failed SHA-256 verification")
        files[role] = path
    uploaded, reused = 0, 0
    for role, path in files.items():
        reference = manifest.artifacts[role]
        created = _publish_once(
            service, reference.container, reference.blob, path, reference.sha256
        )
        uploaded += int(created)
        reused += int(not created)
    immutable_manifest = f"snapshots/{manifest.snapshot_id}/manifest.json"
    created = _publish_once(
        service, container, immutable_manifest, body, hashlib.sha256(body).hexdigest()
    )
    uploaded += int(created)
    reused += int(not created)
    if activate:
        upload_blob(
            service, container, active_name, body, overwrite=True,
            metadata={"sha256": hashlib.sha256(body).hexdigest()},
        )
    return {
        "snapshot_id": manifest.snapshot_id,
        "metadata_container": container,
        "immutable_manifest": immutable_manifest,
        "activated": activate,
        "active_manifest": active_name if activate else None,
        "uploaded": uploaded,
        "reused": reused,
    }


def main() -> None:
    """Publish a locally built snapshot using configured managed identity credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot_path", type=Path, required=True)
    parser.add_argument(
        "--metadata_container", default=os.environ.get("GRAPHIV_METADATA_CONTAINER")
    )
    parser.add_argument(
        "--manifest_blob", default=os.environ.get("GRAPHIV_MANIFEST_BLOB", "manifest.json")
    )
    parser.add_argument(
        "--activate", action="store_true",
        help="switch the runtime manifest alias after every immutable object is published",
    )
    args = parser.parse_args()
    result = publish_snapshot(
        blob_service_from_environment(), args.snapshot_path,
        metadata_container=args.metadata_container,
        manifest_blob=args.manifest_blob, activate=args.activate,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
