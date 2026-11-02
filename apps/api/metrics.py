"""Measure real research-job wall time and process/container memory."""

from __future__ import annotations

import resource
import sys
import threading
import time
from pathlib import Path


def _number(path: str) -> int | None:
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return None


def resident_bytes() -> int:
    """Read current Linux RSS, falling back to the platform's lifetime peak."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


class ExecutionMetrics:
    """Sample memory during a job; keep queue and processing measurements explicit."""

    def __init__(self) -> None:
        self.started = time.perf_counter()
        self.peak_rss = resident_bytes()
        self.peak_container: int | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def start(self) -> None:
        """Begin sampling the actual worker process."""
        self._thread.start()

    def _sample(self) -> None:
        while not self._stop.is_set():
            self.peak_rss = max(self.peak_rss, resident_bytes())
            container = _number("/sys/fs/cgroup/memory.current")
            if container is None:
                container = _number("/sys/fs/cgroup/memory/memory.usage_in_bytes")
            if container is not None:
                self.peak_container = max(self.peak_container or 0, container)
            _ = self._stop.wait(0.1)

    def snapshot(self) -> dict[str, int | float | None]:
        """Return sampled peaks and elapsed seconds without mutating the report."""
        return {
            "elapsed_seconds": round(time.perf_counter() - self.started, 3),
            "peak_rss_bytes": max(self.peak_rss, resident_bytes()),
            "peak_container_bytes": self.peak_container,
            "sample_interval_seconds": 0.1,
        }

    def close(self) -> None:
        """Stop sampling when the job finishes."""
        self._stop.set()
        self._thread.join(timeout=1)
