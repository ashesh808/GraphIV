"""Local and Azure Blob persistence for committed research report directories."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Protocol

from src.storage.blobs import (
    BlobIntegrityError,
    BlobNotFoundError,
    BlobStorageError,
    download_blob,
    file_sha256,
    list_blob_names,
    read_blob,
    upload_blob,
    validate_blob_name,
    validate_checksum,
    validate_container,
    validate_segment,
)

FILES = ("report.md", "run.json", "papers.json", "graph.json", "report.json")
_PAYLOADS = tuple(name for name in FILES if name != "run.json")
_MAX_REPORT_BYTES = 128 * 1024 * 1024
_STORAGE_KEY = "_graphiv_storage"


class ReportStore(Protocol):
    """Persistence independent of the runtime's local scratch directory."""

    def list_runs(self) -> list[dict[str, Any]]:
        """List only committed report metadata."""
        ...

    def read_run(self, slug: str) -> dict[str, Any] | None:
        """Read one committed report and its standard artifacts."""
        ...

    def file_path(self, slug: str, name: str) -> Path | None:
        """Return a safe local path to one report artifact, hydrating if necessary."""
        ...

    def save_directory(self, directory: Path) -> None:
        """Publish all five completed files from a local report directory."""
        ...


def _valid_slug(slug: str) -> bool:
    try:
        _ = validate_segment(slug)
    except ValueError:
        return False
    return True


def _metadata(body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise BlobStorageError("The report metadata is not valid JSON") from None
    if not isinstance(parsed, dict):
        raise BlobStorageError("The report metadata must be a JSON object")
    return parsed


def _summary(parsed: dict[str, Any], slug: str) -> dict[str, Any]:
    papers = parsed.get("papers")
    return {
        "slug": slug,
        "question": str(parsed.get("question", slug)),
        "asked": str(parsed.get("asked", "")),
        "mode": str(parsed.get("mode", "")),
        "effort": str(parsed.get("effort", "")),
        "papers": len(papers) if isinstance(papers, list) else 0,
    }


def _read_directory(where: Path, slug: str) -> dict[str, Any] | None:
    try:
        parsed = _metadata((where / "run.json").read_bytes())
        parsed["slug"] = slug
        for name in _PAYLOADS:
            found = where / name
            if not found.is_file():
                continue
            if found.is_symlink():
                return None
            raw = found.read_text(encoding="utf-8")
            key = "sections" if name == "report.json" else name.split(".")[0]
            parsed[key] = json.loads(raw) if name.endswith(".json") else raw
    except (OSError, ValueError, BlobStorageError):
        return None
    return parsed


def read_runs(root: Path) -> list[dict[str, Any]]:
    """Read local report metadata, newest directory name first."""
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for found in sorted(root.iterdir(), reverse=True):
        if not known(root, found.name):
            continue
        meta = found / "run.json"
        if meta.is_symlink() or not meta.is_file():
            continue
        try:
            parsed = _metadata(meta.read_bytes())
        except (OSError, BlobStorageError):
            continue
        out.append(_summary(parsed, found.name))
    return out


def known(root: Path, slug: str) -> bool:
    """Accept only a real child report directory, never a traversal or symlink."""
    if not _valid_slug(slug) or not root.is_dir():
        return False
    where = root / slug
    return where.is_dir() and not where.is_symlink() and where.resolve().parent == root.resolve()


def read_one(root: Path, slug: str) -> dict[str, Any] | None:
    """Read the standard local files while retaining the existing public signature."""
    if not known(root, slug) or (root / slug / "run.json").is_symlink():
        return None
    return _read_directory(root / slug, slug)


def _validate_directory(directory: Path) -> dict[str, Any]:
    validate_segment(directory.name)
    for name in FILES:
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("A complete report needs all five regular artifact files")
        if path.stat().st_size > _MAX_REPORT_BYTES:
            raise ValueError("A report artifact exceeds the permitted size")
        if name.endswith(".json"):
            try:
                value = json.loads(path.read_bytes())
            except (ValueError, UnicodeDecodeError):
                raise ValueError("A report artifact is not valid JSON") from None
            expected = list if name == "papers.json" else dict
            if not isinstance(value, expected):
                raise ValueError("A report artifact has an unexpected JSON shape")
    return _metadata((directory / "run.json").read_bytes())


class LocalReportStore:
    """Keep the established filesystem layout for development and offline use."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def list_runs(self) -> list[dict[str, Any]]:
        """List committed local run metadata."""
        return read_runs(self.root)

    def read_run(self, slug: str) -> dict[str, Any] | None:
        """Read one local report."""
        return read_one(self.root, slug)

    def file_path(self, slug: str, name: str) -> Path | None:
        """Resolve only the five allowed files in a local report."""
        if name not in FILES or not known(self.root, slug):
            return None
        found = self.root / slug / name
        return found if found.is_file() and not found.is_symlink() else None

    def save_directory(self, directory: Path) -> None:
        """Validate or atomically copy a completed run into this local store."""
        directory = Path(directory)
        _ = _validate_directory(directory)
        target = self.root / directory.name
        if directory.resolve() == target.resolve():
            return
        self.root.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError("A report destination cannot be a symbolic link")
        with tempfile.TemporaryDirectory(prefix=".report-", dir=self.root) as temporary:
            staging = Path(temporary) / "complete"
            staging.mkdir()
            for name in FILES:
                _ = shutil.copyfile(directory / name, staging / name)
            _ = _validate_directory(staging)
            previous = Path(temporary) / "previous"
            if target.exists():
                os.rename(target, previous)
            try:
                os.rename(staging, target)
            except OSError:
                if previous.exists():
                    os.rename(previous, target)
                raise


class BlobReportStore:
    """Publish immutable payload generations with run.json as the last commit marker."""

    def __init__(
        self, client: Any, container: str, cache_root: Path, prefix: str = ""
    ) -> None:
        self.client = client
        self.container = validate_container(container)
        self.cache_root = Path(cache_root)
        self.prefix = validate_blob_name(prefix.rstrip("/")) + "/" if prefix else ""
        self._lock = threading.RLock()

    def _name(self, slug: str, name: str) -> str:
        validate_segment(slug)
        return validate_blob_name(f"{self.prefix}{slug}/{name}")

    def list_runs(self) -> list[dict[str, Any]]:
        """List root commit markers without downloading report bodies."""
        out: list[dict[str, Any]] = []
        for name in sorted(list_blob_names(self.client, self.container, self.prefix), reverse=True):
            if not name.startswith(self.prefix):
                continue
            relative = name[len(self.prefix):].split("/")
            if len(relative) != 2 or relative[1] != "run.json" or not _valid_slug(relative[0]):
                continue
            try:
                parsed = _metadata(read_blob(self.client, self.container, name))
            except BlobNotFoundError:
                continue
            out.append(_summary(parsed, relative[0]))
        return out

    def _references(self, slug: str, metadata: dict[str, Any]) -> dict[str, tuple[str, str | None]]:
        publication = metadata.get(_STORAGE_KEY)
        if publication is None:
            # Read compatibility for pre-generation Blob uploads. New writes always
            # carry immutable generation paths and SHA-256 digests.
            return {name: (self._name(slug, name), None) for name in _PAYLOADS}
        if (
            not isinstance(publication, dict)
            or not isinstance(publication.get("version"), int)
            or isinstance(publication.get("version"), bool)
            or publication.get("version") != 1
        ):
            raise BlobStorageError("Unsupported report storage version")
        generation = validate_segment(publication.get("generation"))
        files = publication.get("files")
        if not isinstance(files, dict) or set(files) != set(_PAYLOADS):
            raise BlobStorageError("The report commit marker is incomplete")
        references: dict[str, tuple[str, str | None]] = {}
        for name in _PAYLOADS:
            reference = files[name]
            if not isinstance(reference, dict):
                raise BlobStorageError("The report artifact metadata is invalid")
            checksum = validate_checksum(reference.get("sha256"))
            references[name] = (self._name(slug, f"_versions/{generation}/{name}"), checksum)
        return references

    def _check_cache(
        self, directory: Path, marker: bytes, references: dict[str, tuple[str, str | None]]
    ) -> None:
        if directory.is_symlink() or (directory / "run.json").is_symlink():
            raise BlobIntegrityError("The report cache cannot contain symbolic links")
        if (directory / "run.json").read_bytes() != marker:
            raise BlobIntegrityError("The cached report commit marker does not match")
        for name, (_, checksum) in references.items():
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise BlobIntegrityError("The cached report is incomplete")
            if checksum is not None and file_sha256(path) != checksum:
                raise BlobIntegrityError("A cached report artifact failed SHA-256 verification")

    def _hydrate(self, slug: str) -> Path | None:
        if not _valid_slug(slug):
            return None
        try:
            marker = read_blob(self.client, self.container, self._name(slug, "run.json"))
        except BlobNotFoundError:
            return None
        metadata = _metadata(marker)
        references = self._references(slug, metadata)
        digest = hashlib.sha256(marker).hexdigest()
        parent = self.cache_root.resolve() / "_blob_runs" / slug
        if not parent.resolve().is_relative_to(self.cache_root.resolve()):
            raise ValueError("The report cache path escapes its root")
        parent.mkdir(parents=True, exist_ok=True)
        target = parent / digest
        with self._lock:
            if target.exists() or target.is_symlink():
                self._check_cache(target, marker, references)
                return target
            with tempfile.TemporaryDirectory(prefix=".report-", dir=parent) as temporary:
                staging = Path(temporary) / "complete"
                staging.mkdir()
                for name, (blob, checksum) in references.items():
                    if checksum is None:
                        _ = (staging / name).write_bytes(
                            read_blob(self.client, self.container, blob, _MAX_REPORT_BYTES)
                        )
                    else:
                        _ = download_blob(
                            self.client, self.container, blob, staging / name,
                            checksum, max_bytes=_MAX_REPORT_BYTES,
                        )
                _ = (staging / "run.json").write_bytes(marker)
                _ = _validate_directory(staging)
                try:
                    os.rename(staging, target)
                except OSError as error:
                    if error.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                        raise
                    self._check_cache(target, marker, references)
            return target

    def read_run(self, slug: str) -> dict[str, Any] | None:
        """Hydrate one complete committed generation and read its five local files."""
        directory = self._hydrate(slug)
        return _read_directory(directory, slug) if directory is not None else None

    def file_path(self, slug: str, name: str) -> Path | None:
        """Hydrate a report and return only an allowed artifact path."""
        if name not in FILES:
            return None
        directory = self._hydrate(slug)
        return directory / name if directory is not None else None

    def save_directory(self, directory: Path) -> None:
        """Upload payloads first and commit their immutable generation last."""
        directory = Path(directory)
        metadata = _validate_directory(directory)
        slug = directory.name
        generation = uuid.uuid4().hex
        files: dict[str, dict[str, str]] = {}
        for name in _PAYLOADS:
            path = directory / name
            checksum = file_sha256(path)
            with path.open("rb") as handle:
                upload_blob(
                    self.client, self.container,
                    self._name(slug, f"_versions/{generation}/{name}"), handle,
                    metadata={"sha256": checksum},
                )
            files[name] = {"sha256": checksum}
        metadata[_STORAGE_KEY] = {"version": 1, "generation": generation, "files": files}
        marker = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
        upload_blob(
            self.client, self.container, self._name(slug, "run.json"), marker, overwrite=True
        )
