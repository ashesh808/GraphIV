"""A bounded, serialized research workflow over the existing retrieval/report tools."""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.metrics import ExecutionMetrics

RUNTIME_LOCK = threading.RLock()


class ResearchRequest(BaseModel):
    """The supported public inputs; scoring constants remain in the recipes."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    mode: Literal["survey", "frontier", "consensus", "ancestry", "evolution"] = "survey"
    effort: Literal["quick", "standard", "deep"] = "standard"

    @field_validator("question")
    @classmethod
    def meaningful_question(cls, value: str) -> str:
        """Reject blank questions before any model or corpus work starts."""
        if not value.strip():
            raise ValueError("question cannot be blank")
        return value.strip()


def safe_error(error: BaseException) -> str:
    """Preserve a useful failure reason while removing configured credential values."""
    message = str(error) or type(error).__name__
    for name in ("GRAPHIV_API_TOKEN", "GRAPHIV_LLM_API_KEY", "GRAPHIV_EMBED_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            message = message.replace(secret, "[redacted]")
    return message[:1000]


def _result(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("The research tool returned an invalid response")
    if value.get("error"):
        raise RuntimeError(str(value["error"]))
    return value


def run_research(
    request: ResearchRequest, *, progress: Callable[[str], None] | None = None
) -> dict[str, Any]:
    """Retrieve one question, then mine and write it through the existing report tool."""
    from src.mcp import retrieve, state, write_report

    measurement = ExecutionMetrics()
    measurement.start()
    with RUNTIME_LOCK:
        # Preserve rankings held by existing MCP callers while this job owns the process.
        previous_rankings, previous_areas = state.STORE.copy(), state.AREAS.copy()
        state.reset()
        handles = None
        previous_progress = None
        previous_metrics = None
        hooks_installed = False
        try:
            handles = state.load()
            previous_progress = getattr(handles, "progress", None)
            previous_metrics = getattr(handles, "execution_metrics", None)
            if hasattr(handles, "progress") and hasattr(handles, "execution_metrics"):
                handles.progress = progress
                handles.execution_metrics = measurement.snapshot
                hooks_installed = True
            if progress:
                progress("retrieving")
            retrieved = _result(
                retrieve.retrieve(
                    handles,
                    question=request.question,
                    mode=request.mode,
                    effort=request.effort,
                )
            )
            query_id = retrieved.get("query_id")
            if not isinstance(query_id, str) or not query_id:
                raise RuntimeError("Retrieval produced no ranking for this question")
            written = _result(
                write_report.write_report(
                    handles,
                    query_ids=[query_id],
                    question=request.question,
                    effort=request.effort,
                    end=True,
                )
            )
            slug = str(written.get("slug") or Path(str(written.get("path", ""))).parent.name)
            return {
                "slug": slug,
                "papers": written.get("papers", 0),
                "answer": written.get("answer", ""),
                "url": f"/api/runs/{slug}",
                "retrieval_counts": retrieved.get("counts", {}),
                "mining_counts": written.get("counts", {}),
                "timings": written.get("seconds", {}),
                "degraded_features": written.get("degraded_features", []),
                "metrics": measurement.snapshot(),
            }
        finally:
            measurement.close()
            if handles is not None and hooks_installed:
                handles.progress = previous_progress
                handles.execution_metrics = previous_metrics
            state.reset()
            state.STORE.update(previous_rankings)
            state.AREAS.update(previous_areas)


@dataclass
class Job:
    """A small status record; full report artifacts live in the configured report store."""

    id: str
    question: str
    mode: str
    effort: str
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    result: dict[str, Any] | None = None
    error: str | None = None
    stage: str = "queued"
    started_at: str | None = None
    finished_at: str | None = None


class Coordinator:
    """Run one job at a time, with bounded queue and retained status records."""

    def __init__(
        self,
        runner: Callable[[ResearchRequest], dict[str, Any]] = run_research,
        *,
        max_jobs: int = 128,
        max_pending: int = 4,
    ) -> None:
        if max_jobs < 1 or max_pending < 1 or max_pending > max_jobs:
            raise ValueError("Job limits must be positive and pending must fit retained jobs")
        self.runner = runner
        self.max_jobs = max_jobs
        self.max_pending = max_pending
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="graphiv-research")

    def submit(self, request: ResearchRequest) -> dict[str, Any]:
        """Queue validated work, refusing excess requests before allocating another job."""
        with self._lock:
            pending = sum(job.status in ("queued", "running") for job in self.jobs.values())
            if pending >= self.max_pending:
                raise OverflowError("The research queue is full; retry when a job finishes")
            while len(self.jobs) >= self.max_jobs:
                finished = next(
                    (key for key, job in self.jobs.items() if job.status in ("complete", "failed")),
                    None,
                )
                if finished is None:
                    raise OverflowError("The research queue is full")
                del self.jobs[finished]
            job = Job(
                id=uuid.uuid4().hex,
                question=request.question,
                mode=request.mode,
                effort=request.effort,
            )
            self.jobs[job.id] = job
            queued = asdict(job)
            self._executor.submit(self._run, job.id, request)
            return queued

    def _run(self, job_id: str, request: ResearchRequest) -> None:
        with self._lock:
            self.jobs[job_id].status = "running"
            self.jobs[job_id].stage = "starting"
            self.jobs[job_id].started_at = datetime.now(UTC).isoformat()
        try:
            with RUNTIME_LOCK:
                result = (
                    run_research(request, progress=lambda stage: self._progress(job_id, stage))
                    if self.runner is run_research
                    else self.runner(request)
                )
        except Exception as error:  # noqa: BLE001 - record worker failures instead of losing jobs
            with self._lock:
                self.jobs[job_id].status = "failed"
                self.jobs[job_id].error = safe_error(error)
                self.jobs[job_id].stage = "failed"
                self.jobs[job_id].finished_at = datetime.now(UTC).isoformat()
        else:
            with self._lock:
                self.jobs[job_id].status = "complete"
                self.jobs[job_id].result = result
                self.jobs[job_id].stage = "complete"
                self.jobs[job_id].finished_at = datetime.now(UTC).isoformat()

    def _progress(self, job_id: str, stage: str) -> None:
        with self._lock:
            self.jobs[job_id].stage = stage

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Return a detached status snapshot."""
        with self._lock:
            job = self.jobs.get(job_id)
            return asdict(job) if job else None

    def close(self) -> None:
        """Stop accepting work and cancel queued jobs during process shutdown."""
        self._executor.shutdown(wait=False, cancel_futures=True)
