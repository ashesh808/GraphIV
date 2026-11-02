"""Read cgroup memory evidence for the standalone corpus-validation worker."""

from __future__ import annotations

from pathlib import Path
from typing import Any

EIGHT_GIB = 8 * 1024**3


def _integer(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _pairs(value: str | None) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in (value or "").splitlines():
        fields = line.split()
        if len(fields) == 2 and (number := _integer(fields[1])) is not None:
            result[fields[0]] = number
    return result


def read_cgroup(root: Path = Path("/sys/fs/cgroup")) -> dict[str, Any]:
    """Normalize v1/v2 measurements while retaining their raw files and paths."""
    root = Path(root)
    if (root / "memory.current").is_file() or (root / "memory.max").is_file():
        layout = "v2"
        names = {
            "current": "memory.current",
            "peak": "memory.peak",
            "limit": "memory.max",
            "events": "memory.events",
            "stat": "memory.stat",
        }
    elif (root / "memory" / "memory.usage_in_bytes").is_file():
        layout = "v1"
        names = {
            "current": "memory/memory.usage_in_bytes",
            "peak": "memory/memory.max_usage_in_bytes",
            "limit": "memory/memory.limit_in_bytes",
            "events": "memory/memory.oom_control",
            "failcnt": "memory/memory.failcnt",
            "stat": "memory/memory.stat",
            "kernel": "memory/memory.kmem.usage_in_bytes",
        }
    else:
        layout, names = "unavailable", {}
    raw: dict[str, str | None] = {}
    for relative in names.values():
        try:
            raw[relative] = (root / relative).read_text().strip()
        except OSError:
            raw[relative] = None

    def text(name: str) -> str | None:
        return raw.get(names.get(name, ""))

    stats = _pairs(text("stat"))
    events: dict[str, int | None] = dict(_pairs(text("events")))
    if layout == "v1":
        events["failcnt"] = _integer(text("failcnt"))

        def stat(total: str, local: str) -> int | None:
            return stats.get(total, stats.get(local))

        normalized = {
            "anon": stat("total_rss", "rss"),
            "file": stat("total_cache", "cache"),
            "file_mapped": stat("total_mapped_file", "mapped_file"),
            "inactive_file": stat("total_inactive_file", "inactive_file"),
            "shmem": stat("total_shmem", "shmem"),
            "kernel": _integer(text("kernel")),
        }
    else:
        normalized = {
            key: stats.get(key)
            for key in ("anon", "file", "kernel", "shmem", "file_mapped", "inactive_file")
        }
    return {
        "layout": layout,
        "root": str(root),
        "paths": {name: str(root / relative) for name, relative in names.items()},
        "raw": raw,
        "memory.current": _integer(text("current")),
        "memory.peak": _integer(text("peak")),
        "memory.max": "max" if text("limit") == "max" else _integer(text("limit")),
        "memory.events": events,
        "memory.stat": normalized,
    }


def require_memory_budget(measured: dict[str, Any], expected_bytes: int = EIGHT_GIB) -> None:
    """Fail closed unless current usage and the exact configured limit are measured."""
    limit, current = measured.get("memory.max"), measured.get("memory.current")
    if type(limit) is not int or limit != expected_bytes:
        raise RuntimeError("Validation requires a measured numeric configured memory limit")
    if type(current) is not int or not 0 <= current <= limit:
        raise RuntimeError("Validation requires measured current memory usage within its limit")


def memory_event_deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int | None]:
    """Keep OOM kills distinct from limit failures and preserve unavailable counters."""
    result: dict[str, int | None] = {}
    for key in ("oom_kill", "oom", "failcnt", "max", "high"):
        old = before.get("memory.events", {}).get(key)
        new = after.get("memory.events", {}).get(key)
        result[key] = new - old if type(old) is int and type(new) is int and new >= old else None
    return result
