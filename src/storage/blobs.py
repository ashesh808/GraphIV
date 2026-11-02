"""Azure Blob transport with managed identity and verified, atomic local downloads."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from urllib.parse import urlsplit

_CONTAINER = re.compile(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?\Z")
_SEGMENT = re.compile(r"[\w][\w. -]{0,199}\Z", re.UNICODE)
_SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")


class BlobStorageError(RuntimeError):
    """A storage operation failed without exposing provider credentials."""


class BlobNotFoundError(FileNotFoundError):
    """A requested object does not exist."""


class BlobIntegrityError(BlobStorageError):
    """Downloaded bytes do not match their immutable artifact checksum."""


@dataclass(frozen=True)
class BlobInfo:
    """Metadata needed to avoid overwriting an already-published immutable object."""

    size: int
    sha256: str | None


def validate_segment(value: object) -> str:
    """Accept one filename segment, excluding traversal and hidden working files."""
    if not isinstance(value, str) or not _SEGMENT.fullmatch(value) or value in {".", ".."}:
        raise ValueError("Invalid storage path segment")
    return value


def validate_blob_name(value: object) -> str:
    """Reject absolute paths, traversal, backslashes, and control characters."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 1024
        or "\\" in value
        or any(ord(char) < 32 for char in value)
        or value.startswith("/")
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or PurePosixPath(value).is_absolute()
    ):
        raise ValueError("Invalid blob object name")
    return value


def validate_container(value: object) -> str:
    """Validate the Azure container name before making a storage request."""
    if not isinstance(value, str) or not 3 <= len(value) <= 63:
        raise ValueError("Invalid blob container name")
    if not _CONTAINER.fullmatch(value) or "--" in value:
        raise ValueError("Invalid blob container name")
    return value


def validate_checksum(value: object) -> str:
    """Validate and normalize a SHA-256 digest supplied by an artifact manifest."""
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("Artifact checksum must be a SHA-256 hex digest")
    return value.lower()


def file_sha256(path: Path) -> str:
    """Hash a local artifact without loading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _request_errors() -> tuple[type[Exception], ...]:
    try:
        from azure.core.exceptions import AzureError
    except ImportError:
        return (OSError,)
    return (AzureError, OSError)


def _missing(error: Exception) -> bool:
    return isinstance(error, FileNotFoundError) or getattr(error, "status_code", None) == 404


def blob_service_from_environment() -> Any:
    """Create the Azure SDK service client using managed identity or local Azurite."""
    connection = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    account_url = os.environ.get("GRAPHIV_STORAGE_ACCOUNT_URL", "").strip()
    if connection:
        fields = dict(
            part.split("=", 1) for part in connection.split(";") if part and "=" in part
        )
        endpoint = urlsplit(fields.get("BlobEndpoint", ""))
        if endpoint.scheme != "http" or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Connection strings are supported only for local Azurite")
    else:
        endpoint = urlsplit(account_url)
        if (
            endpoint.scheme != "https"
            or not endpoint.hostname
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError("GRAPHIV_STORAGE_ACCOUNT_URL must be an HTTPS account URL")

    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    if connection:
        return BlobServiceClient.from_connection_string(
            connection, connection_timeout=10, read_timeout=60
        )
    credential = DefaultAzureCredential(
        managed_identity_client_id=os.environ.get("AZURE_CLIENT_ID") or None,
        exclude_interactive_browser_credential=True,
    )
    return BlobServiceClient(
        account_url=account_url,
        credential=credential,
        connection_timeout=10,
        read_timeout=60,
    )


def _download_chunks(client: Any, container: str, name: str) -> Iterable[bytes]:
    validate_container(container)
    validate_blob_name(name)
    try:
        source = client.get_blob_client(container=container, blob=name).download_blob()
        yield from source.chunks()
    except _request_errors() as error:
        if _missing(error):
            raise BlobNotFoundError("The requested blob does not exist") from None
        raise BlobStorageError("Could not download an object from blob storage") from None


def read_blob(client: Any, container: str, name: str, max_bytes: int = 8 * 1024 * 1024) -> bytes:
    """Read a bounded metadata object, refusing unexpectedly large payloads."""
    body = bytearray()
    for chunk in _download_chunks(client, container, name):
        if len(body) + len(chunk) > max_bytes:
            raise BlobStorageError("The blob exceeds the permitted metadata size")
        body.extend(chunk)
    return bytes(body)


def download_blob(
    client: Any,
    container: str,
    name: str,
    destination: Path,
    sha256: str,
    max_bytes: int | None = None,
) -> Path:
    """Verify a streamed download before atomically replacing its local destination."""
    expected = validate_checksum(sha256)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            digest = hashlib.sha256()
            size = 0
            for chunk in _download_chunks(client, container, name):
                size += len(chunk)
                if max_bytes is not None and size > max_bytes:
                    raise BlobStorageError("The blob exceeds the permitted artifact size")
                digest.update(chunk)
                _ = handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if digest.hexdigest() != expected:
            raise BlobIntegrityError("The downloaded blob failed SHA-256 verification")
        os.replace(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def upload_blob(
    client: Any,
    container: str,
    name: str,
    data: BinaryIO | bytes,
    *,
    overwrite: bool = False,
    metadata: dict[str, str] | None = None,
) -> None:
    """Upload a named object without placing authentication material in its metadata."""
    validate_container(container)
    validate_blob_name(name)
    try:
        _ = client.get_blob_client(container=container, blob=name).upload_blob(
            data, overwrite=overwrite, metadata=metadata
        )
    except _request_errors():
        raise BlobStorageError("Could not publish an object to blob storage") from None


def list_blob_names(client: Any, container: str, prefix: str = "") -> list[str]:
    """List object names below an optional validated blob prefix."""
    validate_container(container)
    if prefix:
        validate_blob_name(prefix.rstrip("/"))
    try:
        found = client.get_container_client(container).list_blobs(name_starts_with=prefix)
        return [str(blob.name) for blob in found]
    except _request_errors():
        raise BlobStorageError("Could not list objects in blob storage") from None


def blob_info(client: Any, container: str, name: str) -> BlobInfo | None:
    """Inspect a published object's size and producer checksum without downloading it."""
    validate_container(container)
    validate_blob_name(name)
    try:
        properties = client.get_blob_client(container=container, blob=name).get_blob_properties()
    except _request_errors() as error:
        if _missing(error):
            return None
        raise BlobStorageError("Could not inspect an object in blob storage") from None
    metadata = properties.metadata or {}
    return BlobInfo(int(properties.size), metadata.get("sha256"))
