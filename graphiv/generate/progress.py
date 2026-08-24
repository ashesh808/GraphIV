"""
Per-stage run timing, written incrementally so a live run is observable

The dashboard reads progress.json because run.json does not exist until the run finishes
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class StageTimer:
    """
    Times each stage and writes progress.json as the run advances
    """

    out_dir: Path
    question: str
    started_at: str
    _t0: float
    _stages: list[dict[str, object]]

    def __init__(self, out_dir: Path, question: str) -> None:
        self.out_dir = out_dir
        self.question = question
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self._t0 = time.monotonic()
        self._stages = []
        self._write(done=False)

    def _write(self, done: bool) -> None:
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            _ = (self.out_dir / "progress.json").write_text(
                json.dumps(
                    {
                        "question": self.question,
                        "started_at": self.started_at,
                        "elapsed": round(time.monotonic() - self._t0, 1),
                        "stages": self._stages,
                        "done": done,
                    },
                    indent=1,
                ),
                encoding="utf-8",
            )
        # progress is best-effort, never sinks a run
        except Exception:  # noqa: BLE001
            pass

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """
        Time the enclosed block as one named stage
        """
        entry: dict[str, object] = {"name": name, "seconds": None}
        self._stages.append(entry)
        self._write(done=False)
        t = time.monotonic()
        try:
            yield
        finally:
            entry["seconds"] = round(time.monotonic() - t, 1)
            self._write(done=False)

    def timings(self) -> dict[str, object]:
        """
        Aggregate for run.json (same-named stages from loop rounds are summed)
        """
        agg: dict[str, float] = {}
        for s in self._stages:
            sec = s["seconds"]
            if isinstance(sec, (int, float)):
                agg[str(s["name"])] = round(agg.get(str(s["name"]), 0.0) + float(sec), 1)
        self._write(done=True)
        return {
            "started_at": self.started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "total_seconds": round(time.monotonic() - self._t0, 1),
            "stages": agg,
        }
