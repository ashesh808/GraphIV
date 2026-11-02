"""Committed Blob generations preserve prior reports through publication failures."""

import hashlib
import json
import os
import uuid
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from starlette.testclient import TestClient

from apps.api.dashboard import mount
from src.storage.artifacts import load_snapshot
from src.storage.blobs import (
    BlobIntegrityError,
    BlobStorageError,
    blob_service_from_environment,
    upload_blob,
)
from src.storage.runs import FILES, BlobReportStore, LocalReportStore, known, read_one, read_runs


def make_report(root: Path, slug="2026-11-01-research", question="A saved research question"):
    directory = root / slug
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "run.json": {
            "question": question, "asked": "2026-11-01", "mode": "survey", "effort": "quick",
            "papers": ["paper-a"],
        },
        "papers.json": [{"arxiv_id": "paper-a", "title": "Paper A"}],
        "graph.json": {"nodes": [{"arxiv_id": "paper-a"}], "edges": []},
        "report.json": {"answer": "The saved answer"},
    }
    for name, data in payload.items():
        (directory / name).write_text(json.dumps(data))
    (directory / "report.md").write_text("# A saved report\n\nThe saved answer.")
    return directory


def test_local_helpers_preserve_the_existing_api(tmp_path: Path):
    directory = make_report(tmp_path)
    assert read_runs(tmp_path)[0]["slug"] == directory.name
    report = read_one(tmp_path, directory.name)
    assert report["papers"][0]["title"] == "Paper A"
    assert report["sections"]["answer"] == "The saved answer"
    assert report["report"].startswith("# A saved report")
    store = LocalReportStore(tmp_path)
    assert store.read_run(directory.name) == report
    assert store.file_path(directory.name, "report.md") == directory / "report.md"


def test_local_helpers_reject_directory_symlinks_and_traversal(tmp_path: Path):
    source = make_report(tmp_path / "elsewhere")
    root = tmp_path / "reports"
    root.mkdir()
    (root / "escaped").symlink_to(source, target_is_directory=True)
    assert not known(root, "escaped")
    assert read_one(root, "escaped") is None
    assert read_one(root, "../elsewhere") is None
    assert read_runs(root) == []


def test_local_store_can_atomically_copy_a_complete_report(tmp_path: Path):
    source = make_report(tmp_path / "source")
    store = LocalReportStore(tmp_path / "destination")
    store.save_directory(source)
    assert store.read_run(source.name)["question"] == "A saved research question"
    (source / "papers.json").write_text("not json")
    with pytest.raises(ValueError):
        store.save_directory(source)
    assert store.read_run(source.name)["papers"][0]["title"] == "Paper A"


def test_blob_report_commit_marker_is_uploaded_last(fake_blobs, tmp_path: Path):
    source = make_report(tmp_path / "source")
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache")
    store.save_directory(source)
    assert len(fake_blobs.uploads) == 5
    assert fake_blobs.uploads[-1] == ("reports", f"{source.name}/run.json")
    assert all("/_versions/" in name for _, name in fake_blobs.uploads[:-1])
    assert store.list_runs()[0]["papers"] == 1
    report = store.read_run(source.name)
    assert report["question"] == "A saved research question"
    assert report["papers"][0]["title"] == "Paper A"
    assert report["sections"]["answer"] == "The saved answer"
    directory = store.file_path(source.name, "run.json").parent
    assert sorted(path.name for path in directory.iterdir()) == sorted(FILES)


@pytest.mark.parametrize("failed_file", ["graph.json", "run.json"])
def test_partial_first_upload_never_becomes_a_visible_report(
    fake_blobs, tmp_path: Path, failed_file
):
    source = make_report(tmp_path / "source")
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache")
    fake_blobs.fail_upload = lambda key: key[1].endswith(failed_file)
    with pytest.raises(BlobStorageError):
        store.save_directory(source)
    assert store.list_runs() == []
    assert store.read_run(source.name) is None


@pytest.mark.parametrize("failed_file", ["graph.json", "run.json"])
def test_failed_replacement_keeps_previous_committed_report(
    fake_blobs, tmp_path: Path, failed_file
):
    source = make_report(tmp_path / "source")
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache")
    store.save_directory(source)
    previous = fake_blobs.objects[("reports", f"{source.name}/run.json")]
    make_report(tmp_path / "source", question="A replacement question")
    fake_blobs.fail_upload = lambda key: key[1].endswith(failed_file)
    with pytest.raises(BlobStorageError):
        store.save_directory(source)
    assert fake_blobs.objects[("reports", f"{source.name}/run.json")] == previous
    assert store.read_run(source.name)["question"] == "A saved research question"


def test_successful_replacement_is_seen_by_new_readers(fake_blobs, tmp_path: Path):
    source = make_report(tmp_path / "source")
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache")
    store.save_directory(source)
    old_path = store.file_path(source.name, "report.md")
    make_report(tmp_path / "source", question="A replacement question")
    store.save_directory(source)
    assert store.read_run(source.name)["question"] == "A replacement question"
    assert store.file_path(source.name, "report.md") != old_path
    assert old_path.is_file()


def test_blob_cache_verifies_committed_checksums(fake_blobs, tmp_path: Path):
    source = make_report(tmp_path / "source")
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache")
    store.save_directory(source)
    marker = json.loads(fake_blobs.objects[("reports", f"{source.name}/run.json")])
    generation = marker["_graphiv_storage"]["generation"]
    fake_blobs.objects[("reports", f"{source.name}/_versions/{generation}/papers.json")] = b"[]"
    with pytest.raises(BlobIntegrityError):
        store.read_run(source.name)
    assert list((tmp_path / "cache").rglob("run.json")) == []


def test_report_downloads_cannot_escape_the_five_standard_files(fake_blobs, tmp_path: Path):
    source = make_report(tmp_path / "source")
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache")
    store.save_directory(source)
    assert store.file_path(source.name, "../secrets") is None
    assert store.read_run("../secrets") is None
    assert store.file_path("../secrets", "run.json") is None
    assert store.read_run("missing") is None


def test_prefixed_blob_store_lists_only_committed_root_markers(fake_blobs, tmp_path: Path):
    source = make_report(tmp_path / "source")
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache", prefix="research/team")
    store.save_directory(source)
    fake_blobs.objects[("reports", "unrelated/run.json")] = b"{}"
    assert [run["slug"] for run in store.list_runs()] == [source.name]


def test_legacy_direct_blob_reports_still_hydrate(fake_blobs, tmp_path: Path):
    source = make_report(tmp_path / "source")
    for name in FILES:
        fake_blobs.objects[("reports", f"{source.name}/{name}")] = (source / name).read_bytes()
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache")
    assert store.read_run(source.name)["papers"][0]["arxiv_id"] == "paper-a"


def test_http_report_routes_use_the_blob_store_without_a_local_run(fake_blobs, tmp_path: Path):
    source = make_report(tmp_path / "source")
    store = BlobReportStore(fake_blobs, "reports", tmp_path / "cache")
    store.save_directory(source)
    server = FastMCP("blob-report-test")
    mount(server, tmp_path / "empty-runs", tmp_path / "pdfs", report_store=store)
    client = TestClient(server.streamable_http_app())
    assert client.get("/api/runs").json()[0]["slug"] == source.name
    report = client.get(f"/api/runs/{source.name}")
    assert report.status_code == 200
    assert report.json()["sections"]["answer"] == "The saved answer"
    assert client.get(f"/files/{source.name}/report.md").content == (
        source / "report.md"
    ).read_bytes()
    assert client.get(f"/files/{source.name}/unrecognized.txt").status_code == 404
    fake_blobs.fail_download = lambda key: key[1].endswith("run.json")
    assert client.get("/api/runs").status_code == 503


@pytest.mark.slow
def test_azurite_snapshot_and_report_roundtrip(tmp_path: Path, monkeypatch):
    connection = os.environ.get("GRAPHIV_TEST_AZURITE_CONNECTION_STRING")
    if not connection:
        pytest.skip("Set GRAPHIV_TEST_AZURITE_CONNECTION_STRING for local Azurite integration")
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", connection)
    service = blob_service_from_environment()
    suffix = uuid.uuid4().hex[:12]
    containers = {
        role: f"graphiv-{role}-{suffix}" for role in ("vectors", "metadata", "graph", "reports")
    }
    created = []
    try:
        for container in containers.values():
            service.create_container(container)
            created.append(container)
        artifacts = {}
        for role in ("vectors", "metadata", "graph"):
            body = f"Immutable {role} fixture".encode()
            blob = f"snapshots/integration/{role}"
            upload_blob(service, containers[role], blob, body)
            artifacts[role] = {
                "container": containers[role], "blob": blob,
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        manifest = {
            "version": 1, "snapshot_id": "integration",
            "embedding": {"dimension": 4}, "artifacts": artifacts,
        }
        upload_blob(service, containers["metadata"], "manifest.json", json.dumps(manifest).encode())
        snapshot = load_snapshot(
            service, containers["metadata"], "manifest.json", tmp_path / "artifacts"
        )
        assert snapshot.index.read_bytes() == b"Immutable vectors fixture"
        assert snapshot.database.read_bytes() == b"Immutable metadata fixture"
        source = make_report(tmp_path / "source")
        reports = BlobReportStore(service, containers["reports"], tmp_path / "cache")
        reports.save_directory(source)
        assert reports.list_runs()[0]["slug"] == source.name
        assert reports.read_run(source.name)["sections"]["answer"] == "The saved answer"
        report_file = reports.file_path(source.name, "report.md")
        assert report_file.read_text().startswith("# A saved report")
    finally:
        for container in created:
            service.delete_container(container)
