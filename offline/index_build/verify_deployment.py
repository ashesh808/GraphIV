"""Run real HTTP research jobs and retain independently checkable deployment evidence.

This command intentionally has no demo, fixture, dry-run-success, or offline-pass mode.
By default it submits two real jobs after readiness is established. Supplying two
existing job IDs verifies their actual results without submitting replacement work.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

from src.report.ground import read_ids
from src.storage.artifacts import parse_manifest
from src.storage.blobs import (
    blob_service_from_environment,
    list_blob_names,
    read_blob,
    validate_blob_name,
    validate_checksum,
    validate_segment,
)
from src.storage.runs import FILES

QUESTIONS = (
    "How do linear attention mechanisms and selective state-space models compare for efficient "
    "long-context language modeling, and which research lineages connect them?",
    "What methods improve evidence grounding and citation faithfulness in retrieval-augmented "
    "generation, and which follow-up papers extend those methods?",
)
REPOSITORY = "kkuroma/GraphIV"
REVISION = "GraphIV-2026-10-01"
COMMIT = "cc781313c13b9cbd08110c97eb84b7e1a62180e1"
SOURCE_COUNTS = {"papers": 3_165_827, "citations": 74_764_672, "topics": 3_165_827}
SOURCE_BYTES = 6_486_435_579
MAX_BODY = 128 * 1024 * 1024


class VerificationError(RuntimeError):
    """A real deployment did not supply the required acceptance evidence."""


def origin(value: str) -> str:
    """Accept a credential-free HTTPS origin, allowing HTTP only for localhost."""
    parsed = urlsplit(value)
    local = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not (parsed.scheme == "https" or local)
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Pass an HTTPS origin without credentials, paths, or query parameters")
    return value.rstrip("/")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VerificationError(f"{label} must be a JSON object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise VerificationError(f"{label} must be a JSON array")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise VerificationError(f"{label} must be an explicit nonnegative integer")
    return value


def _positive(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise VerificationError(f"{label} must be a measured number")
    if not math.isfinite(value) or value <= 0:
        raise VerificationError(f"{label} must be positive and finite")
    return value


def _redact(value: str) -> str:
    for name in (
        "GRAPHIV_API_TOKEN",
        "GRAPHIV_LLM_API_KEY",
        "GRAPHIV_EMBED_API_KEY",
        "HF_TOKEN",
        "VERCEL_AUTOMATION_BYPASS_SECRET",
    ):
        secret = os.environ.get(name)
        if secret:
            value = value.replace(secret, "[redacted]")
    return value


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        # Never forward the API bearer token to a redirect target.
        return None


class Http:
    """Bound every request by both its socket timeout and the run's wall deadline."""

    def __init__(self, api: str, vercel: str, *, deadline: float, request_timeout: float) -> None:
        self.api = origin(api)
        self.vercel = origin(vercel)
        self.deadline = deadline
        self.request_timeout = request_timeout
        self.opener = urllib.request.build_opener(_NoRedirect())
        self.token = os.environ.get("GRAPHIV_API_TOKEN", "").strip()
        if not self.token:
            raise VerificationError("Set GRAPHIV_API_TOKEN in the environment before verification")

    def request(
        self, path: str, *, frontend: bool = False, payload: dict[str, Any] | None = None
    ) -> tuple[int, bytes]:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise VerificationError("Deployment verification exceeded its wall timeout")
        base = self.vercel if frontend else self.api
        headers = {"Accept": "application/json"}
        if frontend:
            bypass = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET", "")
            if bypass:
                headers["x-vercel-protection-bypass"] = bypass
        else:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps(payload).encode() if payload is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(base + path, data=body, headers=headers)
        try:
            with self.opener.open(
                request, timeout=min(self.request_timeout, remaining)
            ) as response:
                result = response.read(MAX_BODY + 1)
                if len(result) > MAX_BODY:
                    raise VerificationError("An HTTP response exceeded the verification size limit")
                return response.status, result
        except urllib.error.HTTPError as error:
            return error.code, error.read(min(MAX_BODY, 65536))
        except (OSError, urllib.error.URLError) as error:
            raise VerificationError(f"HTTP request failed ({type(error).__name__})") from None

    def json(self, path: str, *, payload: dict[str, Any] | None = None, expected: int = 200) -> Any:
        status, body = self.request(path, payload=payload)
        if status != expected:
            raise VerificationError(f"{path} returned HTTP {status}; expected {expected}")
        try:
            return json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise VerificationError(f"{path} did not return valid JSON") from None


def require_ready(status_code: int, body: Any) -> dict[str, Any]:
    """Reject missing corpus/read-only health scopes before any research submission."""
    status = _object(body, "Readiness response")
    if status_code != 200 or status.get("ready") is not True or status.get("reasons"):
        reasons = status.get("reasons")
        detail = "; ".join(str(reason) for reason in reasons) if isinstance(reasons, list) else ""
        raise VerificationError(
            "Research runtime is not ready" + (f": {_redact(detail)}" if detail else "")
        )
    if status.get("scope") == "saved-reports":
        raise VerificationError("Readiness describes saved reports only, not research")
    return status


def validate_provenance(value: Any) -> dict[str, Any]:
    """Require the complete pinned published source, not an example or partial corpus."""
    manifest = parse_manifest(json.dumps(_object(value, "Run corpus provenance")).encode())
    source = _object(manifest.raw.get("source"), "Published source provenance")
    if (source.get("repository"), source.get("revision"), source.get("commit")) != (
        REPOSITORY,
        REVISION,
        COMMIT,
    ):
        raise VerificationError("Run does not use the pinned published GraphIV release")
    if manifest.embedding_dimension != 768 or manifest.embedding_model != "nomic-embed-text-v2-moe":
        raise VerificationError("Published corpus/query embedding identity is inconsistent")
    counts = _object(manifest.raw.get("counts"), "Corpus counts")
    if any(counts.get(key) != count for key, count in SOURCE_COUNTS.items()):
        raise VerificationError(
            "Corpus does not contain the full published paper/citation/topic counts"
        )
    if counts.get("embedded") != SOURCE_COUNTS["papers"]:
        raise VerificationError("The full published paper vectors have not all been indexed")
    if source.get("rows") != SOURCE_COUNTS:
        raise VerificationError("Imported corpus counts disagree with published source counts")
    files = source.get("files")
    if not isinstance(files, list) or len(files) != 12:
        raise VerificationError(
            "Source provenance does not identify all 12 published Parquet files"
        )
    grouped = {"papers": 0, "citations": 0, "topics": 0}
    rows = dict.fromkeys(grouped, 0)
    size = 0
    names = set()
    for raw in files:
        item = _object(raw, "Source file")
        name = validate_blob_name(item.get("path"))
        if name in names or name.split("/")[0] not in grouped or not name.endswith(".parquet"):
            raise VerificationError("Source provenance contains invalid or repeated Parquet paths")
        names.add(name)
        grouped[name.split("/")[0]] += 1
        _positive(item.get("size"), "Source file bytes")
        size += _integer(item.get("size"), "Source file bytes")
        rows[name.split("/")[0]] += _integer(item.get("rows"), "Source file rows")
        validate_checksum(item.get("sha256"))
    if grouped != {"papers": 7, "citations": 4, "topics": 1}:
        raise VerificationError("Source provenance has an incomplete shard layout")
    if rows != SOURCE_COUNTS or size != SOURCE_BYTES:
        raise VerificationError("Source shard counts/sizes disagree with the published release")
    features = _object(manifest.raw.get("capabilities"), "Corpus capabilities")
    if features != {
        "precomputed_intents": True,
        "intent_confidence": True,
        "citation_sentences": False,
    }:
        raise VerificationError(
            "Published precomputed-intent/no-citation-sentence capabilities are missing"
        )
    return manifest.raw


def job_counts(result: dict[str, Any]) -> dict[str, int]:
    """Read measured fields explicitly; absence never turns into a synthetic zero."""
    retrieval = _object(result.get("retrieval_counts"), "Retrieval counts")
    mining = _object(result.get("mining_counts"), "Mining counts")
    return {
        "pool": _integer(retrieval.get("pool"), "Retrieval pool"),
        "kept": _integer(retrieval.get("kept"), "Retrieval kept"),
        **{
            key: _integer(mining.get(key), f"Mining {key}")
            for key in ("edges", "lineages", "successors")
        },
    }


def validate_job_ids(value: list[str] | None) -> list[str] | None:
    """Require exactly two distinct server-generated IDs before any HTTP request."""
    if value is None:
        return None
    if (
        len(value) != 2
        or any(
            not isinstance(item, str) or not re.fullmatch(r"[a-f0-9]{32}", item) for item in value
        )
        or value[0] == value[1]
    ):
        raise ValueError("Pass exactly two distinct 32-character research job IDs")
    return value


def require_job_identity(
    job: dict[str, Any], *, job_id: str, question: str, mode: str, effort: str
) -> None:
    """Bind every observed job state to its expected ID and exact research inputs."""
    for key, expected in (
        ("id", job_id),
        ("question", question),
        ("mode", mode),
        ("effort", effort),
    ):
        if job.get(key) != expected:
            raise VerificationError(
                f"Research job {key} does not match the requested acceptance case"
            )


def _sentences(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value for text in _sentences(item)]
    if isinstance(value, dict):
        found = [str(value["sentence"])] if value.get("sentence") else []
        return found + [
            text for key, item in value.items() if key != "sentence" for text in _sentences(item)
        ]
    return []


def _database_records(database: Path, ids: set[str]) -> dict[str, dict[str, Any]]:
    if not database.is_file():
        raise VerificationError("The supplied corpus database does not exist")
    uri = database.resolve().as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        records = connection.execute(
            "SELECT arxiv_id,title,authors FROM papers WHERE arxiv_id IN "
            "(SELECT value FROM json_each(?))",
            (json.dumps(sorted(ids)),),
        ).fetchall()
    return {row[0].lower(): {"title": row[1], "authors": row[2]} for row in records}


def report_identifiers(artifacts: dict[str, bytes]) -> set[str]:
    """Collect actual returned IDs before independently checking corpus membership."""
    identifiers = read_ids(artifacts["report.md"].decode("utf-8"))

    def collect(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            if "arxiv_id" in value:
                identifiers.add(str(value["arxiv_id"]).lower())
            for item in value.values():
                collect(item)

    for name in ("papers.json", "graph.json", "report.json"):
        collect(json.loads(artifacts[name]))
    metadata = _object(json.loads(artifacts["run.json"]), "Run identifiers")
    for key in ("papers", "cited"):
        identifiers.update(str(value).lower() for value in _list(metadata.get(key), key))
    graph = _object(json.loads(artifacts["graph.json"]), "Graph identifiers")
    for edge in _list(graph.get("edges"), "Graph edges"):
        for key in ("source", "target"):
            identifiers.add(str(_object(edge, "Graph edge").get(key, "")).lower())
    if not identifiers or any(not identifier or len(identifier) > 80 for identifier in identifiers):
        raise VerificationError("The returned report has invalid paper identifiers")
    return identifiers


def corpus_records(client: Http, identifiers: set[str]) -> dict[str, dict[str, Any]]:
    """Check every actual returned ID against the deployed corpus, in bounded requests."""
    records: dict[str, dict[str, Any]] = {}
    ordered = sorted(identifiers)
    for offset in range(0, len(ordered), 1000):
        batch = ordered[offset : offset + 1000]
        response = _object(
            client.json("/api/corpus/validate", payload={"ids": batch}), "Corpus validation"
        )
        if _list(response.get("missing"), "Missing corpus identifiers"):
            raise VerificationError(
                "A returned citation/paper ID is absent from the deployed corpus"
            )
        found = {}
        for raw in _list(response.get("papers"), "Corpus paper records"):
            row = _object(raw, "Corpus paper metadata")
            identifier = row.get("arxiv_id")
            if not isinstance(identifier, str) or identifier.lower() in found:
                raise VerificationError("Corpus validation returned missing or duplicate IDs")
            found[identifier.lower()] = row
        if set(found) != set(batch):
            raise VerificationError("Corpus validation did not return every requested paper")
        records.update(found)
    return records


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def validate_report(
    run: dict[str, Any],
    result: dict[str, Any],
    artifacts: dict[str, bytes],
    *,
    question: str,
    deployed_records: dict[str, dict[str, Any]],
    database: Path | None = None,
) -> dict[str, Any]:
    """Cross-check downloaded artifacts, identifiers, authors and evidence limitations."""
    metadata = _object(json.loads(artifacts["run.json"]), "Downloaded run metadata")
    papers = json.loads(artifacts["papers.json"])
    graph = _object(json.loads(artifacts["graph.json"]), "Downloaded graph")
    sections = _object(json.loads(artifacts["report.json"]), "Downloaded sections")
    report = artifacts["report.md"].decode("utf-8")
    if metadata.get("question") != question or run.get("question") != question:
        raise VerificationError("Saved report does not match the submitted question")
    for key, value in metadata.items():
        if key != "papers" and run.get(key) != value:
            raise VerificationError(f"Run API and downloaded metadata disagree on {key}")
    for key, value in (
        ("papers", papers),
        ("graph", graph),
        ("sections", sections),
        ("report", report),
    ):
        if run.get(key) != value:
            raise VerificationError(f"Run API and downloaded {key} disagree")
    corpus = validate_provenance(metadata.get("corpus"))
    if (
        not isinstance(papers, list)
        or not papers
        or not report.strip()
        or not sections.get("answer")
    ):
        raise VerificationError("Persisted report lacks its paper library, body, or answer")
    paper_rows = [_object(paper, "Paper metadata") for paper in papers]
    ids = {str(paper.get("arxiv_id", "")).lower() for paper in paper_rows}
    if "" in ids or len(ids) != len(paper_rows):
        raise VerificationError("Paper library contains missing or duplicate identifiers")
    author_ids = [
        paper["arxiv_id"] for paper in paper_rows if str(paper.get("authors") or "").strip()
    ]
    if not author_ids:
        raise VerificationError("No real paper author metadata was returned")
    nodes = _list(graph.get("nodes"), "Graph nodes")
    edges = _list(graph.get("edges"), "Graph edges")
    lineages = _list(sections.get("lineages"), "Report lineages")
    successors = _list(sections.get("successors"), "Report successors")
    node_ids = {str(node.get("arxiv_id", "")).lower() for node in nodes}
    if "" in node_ids or not node_ids.issubset(ids):
        raise VerificationError("Graph nodes do not resolve to the persisted paper library")
    for edge in edges:
        if (
            str(edge.get("source", "")).lower() not in node_ids
            or str(edge.get("target", "")).lower() not in node_ids
        ):
            raise VerificationError("A graph edge references a missing graph node")
    known_ids = ids | {str(item.get("arxiv_id", "")).lower() for item in successors}
    for lineage in lineages:
        known_ids.update(
            str(paper.get("arxiv_id", "")).lower() for paper in lineage.get("papers", [])
        )
    cited = read_ids(report)
    if not cited:
        raise VerificationError("The saved report contains no arXiv citations")
    reported_cited = metadata.get("cited")
    if not isinstance(reported_cited, list) or not set(reported_cited).issubset(cited):
        raise VerificationError("Reported cited identifiers disagree with the downloaded document")
    if not (cited | known_ids).issubset(deployed_records):
        raise VerificationError("Report IDs were not all verified against the deployed corpus")
    for paper in paper_rows:
        record = deployed_records[paper["arxiv_id"].lower()]
        if any(
            _text(record.get(key)) != _text(paper.get(key))
            for key in ("authors", "title", "abstract")
        ):
            raise VerificationError(
                "Returned paper metadata disagrees with deployed corpus records"
            )
    membership = (
        "matched IDs, paper titles, abstracts and authors to the deployed corpus read endpoint"
    )
    if database is not None:
        records = _database_records(database, cited | known_ids)
        if not (cited | known_ids).issubset(records):
            raise VerificationError(
                "A returned identifier is absent from the supplied corpus database"
            )
        for paper in paper_rows:
            record = records[paper["arxiv_id"].lower()]
            if any(_text(record[key]) != _text(paper.get(key)) for key in ("authors", "title")):
                raise VerificationError(
                    "Returned paper title/authors disagree with corpus metadata"
                )
        membership = (
            "independently matched identifiers, paper titles and authors to read-only SQLite"
        )
    expected_degraded = {"citation_quotations", "sentence_based_disputes"}
    for item in (metadata, sections):
        availability = _object(item.get("evidence_availability"), "Evidence availability")
        if (
            availability.get("citation_sentences") is not False
            or availability.get("jit_intent_mapping") is not False
        ):
            raise VerificationError(
                "Report does not declare the published source's evidence limitations"
            )
        if not expected_degraded.issubset(set(item.get("degraded_features", []))):
            raise VerificationError("Report omits its degraded evidence feature labels")
    if _sentences(graph) or _sentences(sections):
        raise VerificationError(
            "Unpublished citation sentence text appeared in structured report evidence"
        )
    if "Citation sentences are unavailable in this published snapshot" not in report:
        raise VerificationError("Downloaded report omits its citation-sentence evidence note")
    counts = job_counts(result)
    if counts["pool"] <= 0 or counts["kept"] <= 0:
        raise VerificationError("Research returned an empty retrieval pool or kept set")
    if metadata.get("counts") != result.get("mining_counts"):
        raise VerificationError("Job mining counts disagree with persisted run metadata")
    metrics = _object(result.get("metrics"), "Job execution metrics")
    _positive(metrics.get("peak_rss_bytes"), "Measured peak RSS bytes")
    _positive(metrics.get("peak_container_bytes"), "Measured container peak bytes")
    _positive(metrics.get("elapsed_seconds"), "Measured execution seconds")
    return {
        "counts": counts,
        "paper_records": len(papers),
        "author_records": len(author_ids),
        "cited_ids": sorted(cited),
        "identifier_validation": membership,
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "rendered_lineages": len(lineages),
        "rendered_successors": len(successors),
        "retrieval_counts": result["retrieval_counts"],
        "mining_counts": result["mining_counts"],
        "timings": _object(result.get("timings"), "Job stage timings"),
        "metrics": metrics,
        "degraded_features": metadata["degraded_features"],
        "corpus": corpus,
    }


def verify_blob(
    service: Any,
    slug: str,
    artifacts: dict[str, bytes],
    corpus: dict[str, Any],
) -> dict[str, Any]:
    """Independently read the Blob commit marker and verify every immutable payload."""
    container = os.environ.get("GRAPHIV_REPORTS_CONTAINER", "reports")
    prefix = os.environ.get("GRAPHIV_REPORTS_PREFIX", "").strip("/")
    base = f"{validate_blob_name(prefix)}/" if prefix else ""
    marker_name = f"{base}{validate_segment(slug)}/run.json"
    if marker_name not in list_blob_names(service, container, f"{base}{slug}/"):
        raise VerificationError("The report commit marker is absent from Blob listing")
    marker = read_blob(service, container, marker_name, MAX_BODY)
    if marker != artifacts["run.json"]:
        raise VerificationError("Independent Blob commit marker disagrees with HTTP download")
    publication = _object(json.loads(marker).get("_graphiv_storage"), "Blob generation commit")
    generation = validate_segment(publication.get("generation"))
    references = _object(publication.get("files"), "Blob payload checksums")
    if publication.get("version") != 1 or set(references) != set(FILES) - {"run.json"}:
        raise VerificationError(
            "Blob commit marker does not identify a complete immutable generation"
        )
    for filename, reference in references.items():
        digest = validate_checksum(_object(reference, "Blob payload reference").get("sha256"))
        payload = read_blob(
            service, container, f"{base}{slug}/_versions/{generation}/{filename}", MAX_BODY
        )
        if hashlib.sha256(payload).hexdigest() != digest or payload != artifacts[filename]:
            raise VerificationError("Independent Blob payload/hash disagrees with HTTP download")
    active = read_blob(
        service,
        os.environ.get("GRAPHIV_METADATA_CONTAINER", "metadata"),
        os.environ.get("GRAPHIV_MANIFEST_BLOB", "manifest.json"),
    )
    if parse_manifest(active).raw != corpus:
        raise VerificationError("Report corpus provenance disagrees with the active Blob manifest")
    return {
        "verified": True,
        "container": container,
        "marker": marker_name,
        "generation": generation,
        "payloads_sha256_verified": len(references),
        "active_manifest_matches": True,
    }


def _page(client: Http, path: str, *, question: str | None = None) -> dict[str, Any]:
    status, body = client.request(path, frontend=True)
    if status != 200:
        raise VerificationError(f"Vercel {path} returned HTTP {status}")
    if question is not None:
        text = html.unescape(re.sub(r"<[^>]*>", " ", body.decode("utf-8")))
        if " ".join(question.split()) not in " ".join(text.split()):
            raise VerificationError(
                "Vercel report page does not render the submitted real question"
            )
        if "example report" in text.lower():
            raise VerificationError("Vercel returned a labeled example report")
    return {"status": status, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _markdown(evidence: dict[str, Any]) -> str:
    lines = [
        "# GraphIV deployment verification",
        "",
        f"Status: **{evidence['status'].upper()}**",
        "",
        f"Recorded: {evidence['started_at']}",
        "",
        f"API: {evidence['api_origin']}",
        f"Frontend: {evidence['vercel_origin']}",
        "",
        f"Research jobs: {evidence['job_mode']}",
        "",
        "This record contains real HTTP job observations. Browser interaction and scientific "
        "report-quality review remain separate checks.",
        "",
    ]
    if evidence.get("error"):
        lines.extend([f"Failure: {evidence['error']}", ""])
    for number, case in enumerate(evidence["cases"], 1):
        lines.extend(
            [
                f"## Question {number}",
                "",
                case["question"],
                "",
                f"Job: `{case.get('job_id', 'not submitted')}`",
                "",
                f"Report: {case.get('report_url', 'not completed')}",
                "",
            ]
        )
        if "counts" in case:
            lines.extend(
                [
                    "| Pool | Kept | Mined edges | Lineages | Successors |",
                    "| ---: | ---: | ---: | ---: | ---: |",
                    "| "
                    + " | ".join(
                        str(case["counts"][key])
                        for key in ("pool", "kept", "edges", "lineages", "successors")
                    )
                    + " |",
                    "",
                    f"Identifier evidence: {case['identifier_validation']}.",
                    "",
                    f"Peak RSS: {case['metrics']['peak_rss_bytes']} bytes; container peak: "
                    f"{case['metrics']['peak_container_bytes']} bytes; job elapsed: "
                    f"{case['metrics']['elapsed_seconds']} seconds.",
                    "",
                    "Citation sentences are absent from the published source. Quotations and "
                    "sentence-based dispute analysis remain disabled; "
                    "no JIT extraction was performed.",
                    "",
                    "Blob persistence: "
                    + (
                        "independently verified"
                        if case.get("blob", {}).get("verified")
                        else "HTTP list/read/five-file downloads verified; "
                        "independent Blob check not requested"
                    )
                    + ".",
                    "",
                ]
            )
    if evidence.get("corpus"):
        corpus = evidence["corpus"]
        lines.extend(
            [
                "## Corpus provenance",
                "",
                f"Snapshot: `{corpus['snapshot_id']}`",
                "",
                f"HF release: `{REVISION}`; commit: `{COMMIT}`",
                "",
                "Counts: " + ", ".join(f"{key}={value:,}" for key, value in SOURCE_COUNTS.items()),
                "",
                "Full metrics, artifact checksums, provenance, timings and job stage observations "
                "are retained in the adjacent JSON record.",
                "",
            ]
        )
    return "\n".join(lines)


def verify_deployment(
    api_origin: str,
    vercel_origin: str,
    output: Path,
    *,
    questions: list[str] | None = None,
    job_ids: list[str] | None = None,
    mode: str = "survey",
    effort: str = "standard",
    timeout: float = 3600,
    request_timeout: float = 30,
    poll_interval: float = 5,
    verify_blob_storage: bool = False,
    corpus_database: Path | None = None,
) -> dict[str, Any]:
    """Verify actual research after readiness, submitting only when existing IDs are absent."""
    chosen = list(questions or QUESTIONS)
    if (
        len(chosen) != 2
        or chosen[0].strip() == chosen[1].strip()
        or any(not value.strip() or len(value) > 4000 for value in chosen)
    ):
        raise ValueError("Pass exactly two nonblank questions of at most 4000 characters each")
    if min(timeout, request_timeout, poll_interval) <= 0 or poll_interval > 60:
        raise ValueError("Timeouts must be positive and polling must not exceed 60 seconds")
    existing = validate_job_ids(job_ids)
    api_origin, vercel_origin = origin(api_origin), origin(vercel_origin)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in ("verification.json", "verification.md")):
        raise FileExistsError("Choose a new verification output directory")
    started = time.monotonic()
    evidence: dict[str, Any] = {
        "status": "failed",
        "started_at": datetime.now(UTC).isoformat(),
        "api_origin": api_origin,
        "vercel_origin": vercel_origin,
        "cases": [],
        "independent_blob_requested": verify_blob_storage,
        "browser_interaction_verified": False,
        "job_mode": "existing IDs" if existing is not None else "submitted by this verifier",
    }
    try:
        client = Http(
            api_origin, vercel_origin, deadline=started + timeout, request_timeout=request_timeout
        )
        code, body = client.request("/health/ready")
        evidence["readiness"] = require_ready(code, json.loads(body))
        preflight = evidence["readiness"].get("corpus")
        if preflight:
            evidence["corpus"] = validate_provenance(preflight)
        evidence["frontend_home"] = _page(client, "/")
        service = blob_service_from_environment() if verify_blob_storage else None
        for index, question in enumerate(chosen):
            case: dict[str, Any] = {
                "question": question,
                "mode": mode,
                "effort": effort,
                "stages": [],
                "submitted_by_verifier": existing is None,
            }
            evidence["cases"].append(case)
            if existing is not None:
                job_id = existing[index]
            else:
                submitted = _object(
                    client.json(
                        "/api/research",
                        payload={"question": question, "mode": mode, "effort": effort},
                        expected=202,
                    ),
                    "Submitted job",
                )
                job_id = validate_segment(submitted.get("id"))
                require_job_identity(
                    submitted, job_id=job_id, question=question, mode=mode, effort=effort
                )
            case["job_id"] = job_id
            previous = None
            while True:
                job = _object(client.json(f"/api/jobs/{quote(job_id, safe='')}"), "Research job")
                require_job_identity(
                    job, job_id=job_id, question=question, mode=mode, effort=effort
                )
                state = (job.get("status"), job.get("stage"))
                if state != previous:
                    observation = {
                        "status": state[0],
                        "stage": state[1],
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    }
                    case["stages"].append(observation)
                    print(json.dumps({"job_id": job_id, **observation}), flush=True)
                    previous = state
                if job.get("status") == "failed":
                    raise VerificationError(
                        "Real research job failed: "
                        + _redact(str(job.get("error") or "unspecified error"))
                    )
                if job.get("status") == "complete":
                    break
                if job.get("status") not in {"queued", "running"}:
                    raise VerificationError("Research job returned an unknown status")
                remaining = client.deadline - time.monotonic()
                if remaining <= 0:
                    raise VerificationError("Research job exceeded the verification wall timeout")
                time.sleep(min(poll_interval, remaining))
            result = _object(job.get("result"), "Completed research result")
            case["job_result"] = result
            case["job_timestamps"] = {
                key: job.get(key) for key in ("created_at", "started_at", "finished_at")
            }
            slug = validate_segment(result.get("slug"))
            encoded_slug = quote(slug, safe="")
            case.update(slug=slug, report_url=vercel_origin + "/runs/" + encoded_slug)
            run = _object(client.json(f"/api/runs/{encoded_slug}"), "Saved run")
            listing = client.json("/api/runs")
            if not isinstance(listing, list) or not any(row.get("slug") == slug for row in listing):
                raise VerificationError("Completed report is absent from the saved-run library")
            artifacts = {}
            directory = output / "runs" / slug
            directory.mkdir(parents=True)
            for filename in FILES:
                status, artifact = client.request(f"/files/{encoded_slug}/{filename}")
                if status != 200:
                    raise VerificationError(f"Persisted {filename} download returned HTTP {status}")
                artifacts[filename] = artifact
                (directory / filename).write_bytes(artifact)
            deployed_records = corpus_records(client, report_identifiers(artifacts))
            record_bytes = (json.dumps(deployed_records, indent=2) + "\n").encode()
            (directory / "corpus-records.json").write_bytes(record_bytes)
            case["corpus_validation"] = {
                "endpoint": "/api/corpus/validate",
                "verified_records": len(deployed_records),
                "sha256": hashlib.sha256(record_bytes).hexdigest(),
            }
            case.update(
                validate_report(
                    run,
                    result,
                    artifacts,
                    question=question,
                    deployed_records=deployed_records,
                    database=corpus_database,
                )
            )
            if evidence.get("corpus") is not None and evidence["corpus"] != case["corpus"]:
                raise VerificationError("Acceptance cases used different corpus snapshots")
            evidence["corpus"] = case.pop("corpus")
            case["artifact_sha256"] = {
                name: hashlib.sha256(body).hexdigest() for name, body in artifacts.items()
            }
            case["frontend_report"] = _page(client, "/runs/" + encoded_slug, question=question)
            if verify_blob_storage:
                case["blob"] = verify_blob(service, slug, artifacts, evidence["corpus"])
            case["persisted_http_verified"] = True
            case["status"] = "passed"
        for key in ("edges", "lineages", "successors"):
            if sum(case["counts"][key] for case in evidence["cases"]) <= 0:
                raise VerificationError(f"Both cases produced no mined {key}")
        for key in ("graph_edges", "rendered_lineages", "rendered_successors"):
            if sum(case[key] for case in evidence["cases"]) <= 0:
                raise VerificationError(f"Persisted reports contain no {key}")
        evidence["status"] = "passed"
    except Exception as error:  # noqa: BLE001 -- preserve a failed real verification record
        evidence["error"] = (
            _redact(str(error)) if isinstance(error, VerificationError) else type(error).__name__
        )
    finally:
        evidence["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (output / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
        (output / "verification.md").write_text(_markdown(evidence))
    return evidence


def main() -> None:
    """Verify an actual deployed API/frontend pair; credentials are environment-only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-origin", required=True)
    parser.add_argument("--vercel-origin", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--question", action="append", dest="questions")
    parser.add_argument(
        "--job-id",
        action="append",
        dest="job_ids",
        help="existing real job ID; pass twice in the same order as the two questions",
    )
    parser.add_argument(
        "--mode",
        choices=["survey", "frontier", "consensus", "ancestry", "evolution"],
        default="survey",
    )
    parser.add_argument("--effort", choices=["quick", "standard", "deep"], default="standard")
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--request-timeout", type=float, default=30)
    parser.add_argument("--poll-interval", type=float, default=5)
    parser.add_argument("--verify-blob", action="store_true", dest="verify_blob_storage")
    parser.add_argument("--corpus-database", type=Path)
    args = vars(parser.parse_args())
    args["output"] = args.pop("out")
    result = verify_deployment(**args)
    print(json.dumps({"status": result["status"], "output": str(args["output"])}), flush=True)
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
