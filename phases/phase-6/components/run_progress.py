"""Per-run stage timing: run.json gains `timings`, and an incremental progress.json lets the
dashboard show what a live run is doing (stage name + elapsed) before run.json exists.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


class StageTimer:
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
        except Exception:  # noqa: BLE001 — progress is best-effort, never sinks a run
            pass

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
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
        """Aggregate for run.json (same-named stages from loop rounds are summed)."""
        agg: dict[str, float] = {}
        for s in self._stages:
            sec = s["seconds"]
            if isinstance(sec, (int, float)):
                agg[str(s["name"])] = round(
                    agg.get(str(s["name"]), 0.0) + float(sec), 1
                )
        self._write(done=True)
        return {
            "started_at": self.started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "total_seconds": round(time.monotonic() - self._t0, 1),
            "stages": agg,
        }
