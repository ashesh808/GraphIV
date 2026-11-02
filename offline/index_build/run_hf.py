"""Download one pinned published GraphIV release, build it, and optionally publish it."""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

from offline.index_build.build import build_snapshot
from offline.index_build.parquet import ParquetSource
from offline.index_build.publish import publish_snapshot
from src.storage.artifacts import ARTIFACT_FILENAMES, parse_manifest
from src.storage.blobs import (
    blob_service_from_environment,
    file_sha256,
    validate_blob_name,
    validate_segment,
)


def peak_rss_bytes() -> int:
    """Report the platform's process high-water RSS using one unambiguous unit."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(temporary, path)


def run_release(
    workdir: Path,
    *,
    repository: str = "kkuroma/GraphIV",
    revision: str = "GraphIV-2026-10-01",
    snapshot_id: str = "graphiv-2026-10-01-nomic-sq8",
    embedding_model: str = "nomic-embed-text-v2-moe",
    index_kind: str = "ivfsq8",
    nlist: int = 1024,
    nprobe: int = 128,
    train_size: int = 65536,
    seed: int = 0,
    publish: bool = False,
    activate: bool = False,
) -> dict[str, Any]:
    """Run the explicit offline release workflow without generating substitute data."""
    from huggingface_hub import HfApi, get_token, snapshot_download
    from huggingface_hub.utils.tqdm import disable_progress_bars

    validate_segment(snapshot_id)
    if activate and not publish:
        raise ValueError("--activate requires --publish")
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    temporary = workdir / "tmp"
    temporary.mkdir(exist_ok=True)
    os.environ.setdefault("SQLITE_TMPDIR", str(temporary))
    disable_progress_bars()
    started = time.perf_counter()
    phase = {"name": "metadata"}
    report: dict[str, Any] = {
        "repository": repository,
        "revision": revision,
        "snapshot_id": snapshot_id,
        "status": "running",
        "events": [],
    }
    source: ParquetSource | None = None
    stop = threading.Event()

    def event(name: str, **details: Any) -> None:
        phase["name"] = name
        row = {
            "event": name,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "peak_rss_bytes": peak_rss_bytes(),
            "disk_free_bytes": shutil.disk_usage(workdir).free,
            **details,
        }
        report["events"].append(row)
        print(json.dumps(row), flush=True)

    def heartbeat() -> None:
        while not stop.wait(30):
            print(
                json.dumps(
                    {
                        "event": "heartbeat",
                        "phase": phase["name"],
                        "elapsed_seconds": round(time.perf_counter() - started, 3),
                        "peak_rss_bytes": peak_rss_bytes(),
                        "decoded_rows": source.decoded_rows.copy() if source else {},
                    }
                ),
                flush=True,
            )

    thread = threading.Thread(target=heartbeat, name="snapshot-progress", daemon=True)
    thread.start()
    try:
        token = get_token()
        info = HfApi(token=token or False).dataset_info(
            repository, revision=revision, files_metadata=True
        )
        if not isinstance(info.sha, str) or not re.fullmatch(r"[a-f0-9]{40}", info.sha):
            raise ValueError("The HF revision must resolve to one immutable commit")
        files = []
        for item in info.siblings or ():
            if item.rfilename.split("/")[0] not in {"papers", "citations", "topics"}:
                continue
            if not item.rfilename.endswith(".parquet"):
                continue
            if item.size is None:
                raise ValueError("Published Parquet metadata must include exact file sizes")
            file = {"path": validate_blob_name(item.rfilename), "size": int(item.size)}
            if item.lfs and item.lfs.sha256:
                file["sha256"] = item.lfs.sha256
            files.append(file)
        if not files or not info.sha:
            raise ValueError(
                "The requested repository revision has no complete published Parquet release"
            )
        source_manifest = {
            "repository": repository,
            "revision": revision,
            "commit": info.sha,
            "files": sorted(files, key=lambda item: item["path"]),
        }
        source_manifest_path = workdir / "source-manifest.json"
        _write_json(source_manifest_path, source_manifest)
        report["commit"] = info.sha
        event(
            "metadata",
            commit=info.sha,
            parquet_files=len(files),
            source_bytes=sum(item["size"] for item in files),
        )
        destination = workdir / "snapshots" / snapshot_id
        existing = destination / "manifest.json"
        build_options = {
            "index_kind": index_kind,
            "nlist": nlist,
            "nprobe": nprobe,
            "train_size": train_size,
            "seed": seed,
            "vector_dtype": "float16",
        }
        if existing.is_file():
            manifest = parse_manifest(existing.read_bytes())
            if manifest.raw.get("source", {}).get("commit") != info.sha:
                raise ValueError("An existing snapshot ID belongs to a different source commit")
            if (
                manifest.embedding_model != embedding_model
                or manifest.raw.get("build") != build_options
            ):
                raise ValueError("Existing snapshot build options differ; choose a new snapshot ID")
            for role, filename in ARTIFACT_FILENAMES.items():
                if file_sha256(destination / filename) != manifest.artifacts[role].sha256:
                    raise ValueError(
                        "A previously built local artifact failed checksum verification"
                    )
            event("reuse-built-snapshot")
        else:
            source_root = workdir / "source" / info.sha
            missing = [
                item
                for item in files
                if not (source_root / item["path"]).is_file()
                or (source_root / item["path"]).stat().st_size != item["size"]
            ]
            required = sum(item["size"] for item in missing)
            if shutil.disk_usage(workdir).free < required + 1024**3:
                raise OSError(
                    "Insufficient disk space for the missing source files and staging margin"
                )
            if missing:
                if not token:
                    raise RuntimeError(
                        "HF_TOKEN or a local HF login is required for gated data downloads"
                    )
                event("download", missing_files=len(missing), missing_bytes=required)
                snapshot_download(
                    repository,
                    repo_type="dataset",
                    revision=info.sha,
                    local_dir=source_root,
                    allow_patterns=[item["path"] for item in files],
                    token=token,
                    max_workers=2,
                )
            source = ParquetSource(
                source_root,
                repository=repository,
                revision=revision,
                commit=info.sha,
                source_manifest=source_manifest_path,
            )
            event("validated-source", rows=source.expected_rows)
            event("build", index_kind=index_kind, vector_dtype="float16")
            manifest_path = build_snapshot(
                source.paper_rows(),
                source.citation_rows(),
                destination,
                snapshot_id=snapshot_id,
                embedding_model=embedding_model,
                embedding_dimension=source.embedding_dimension,
                vector_dtype="float16",
                topics=source.topic_rows(),
                topic_names=source.topic_name_rows(),
                index_kind=index_kind,
                nlist=nlist,
                nprobe=nprobe,
                train_size=train_size,
                seed=seed,
                provenance=source.provenance(),
                expected_counts=source.expected_rows,
                capabilities={
                    "precomputed_intents": True,
                    "intent_confidence": True,
                    "citation_sentences": False,
                },
                vector_container=os.environ.get("GRAPHIV_VECTOR_CONTAINER", "vector-indexes"),
                metadata_container=os.environ.get("GRAPHIV_METADATA_CONTAINER", "metadata"),
                graph_container=os.environ.get("GRAPHIV_GRAPH_CONTAINER", "citation-graphs"),
            )
            source.verify_counts()
            manifest = parse_manifest(manifest_path.read_bytes())
            event("built", counts=manifest.raw["counts"], index=manifest.raw["index"])
        report.update(
            counts=manifest.raw["counts"],
            quality=manifest.raw.get("quality", {}),
            index=manifest.raw.get("index", {}),
            source=manifest.raw.get("source", {}),
        )
        if publish:
            event("publish", activate=activate)
            report["publication"] = publish_snapshot(
                blob_service_from_environment(),
                destination,
                metadata_container=os.environ.get("GRAPHIV_METADATA_CONTAINER"),
                manifest_blob=os.environ.get("GRAPHIV_MANIFEST_BLOB", "manifest.json"),
                activate=activate,
            )
        report.update(
            status="complete",
            elapsed_seconds=round(time.perf_counter() - started, 3),
            peak_rss_bytes=peak_rss_bytes(),
            manifest=str(existing),
        )
        event("complete", counts=report["counts"])
        _write_json(workdir / "build-report.json", report)
        return report
    except Exception as error:
        report.update(
            status="failed",
            phase=phase["name"],
            error_type=type(error).__name__,
            http_status=getattr(getattr(error, "response", None), "status_code", None),
            elapsed_seconds=round(time.perf_counter() - started, 3),
            peak_rss_bytes=peak_rss_bytes(),
        )
        _write_json(workdir / "build-report.json", report)
        raise
    finally:
        stop.set()
        thread.join(timeout=1)


def main() -> None:
    """Invoke the one-off builder with secrets supplied only through environment/identity."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--repository", default="kkuroma/GraphIV")
    parser.add_argument("--revision", default="GraphIV-2026-10-01")
    parser.add_argument("--snapshot-id", default="graphiv-2026-10-01-nomic-sq8")
    parser.add_argument("--embedding-model", default="nomic-embed-text-v2-moe")
    parser.add_argument("--index-kind", choices=["flat", "ivfsq8"], default="ivfsq8")
    parser.add_argument("--nlist", type=int, default=1024)
    parser.add_argument("--nprobe", type=int, default=128)
    parser.add_argument("--train-size", type=int, default=65536)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    try:
        run_release(**vars(args))
    except Exception as error:  # noqa: BLE001 -- emit only a redacted failure type from the CLI
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
