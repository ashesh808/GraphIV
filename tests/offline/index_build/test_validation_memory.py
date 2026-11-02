"""The worker must measure actual v1/v2 limits without treating missing files as capacity."""

from pathlib import Path

import pytest

from offline.index_build.validation_memory import (
    EIGHT_GIB,
    memory_event_deltas,
    read_cgroup,
    require_memory_budget,
)


def write(root: Path, relative: str, value: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def test_v1_maps_hierarchical_stats_and_keeps_oom_and_limit_failures_distinct(tmp_path):
    files = {
        "memory.usage_in_bytes": "777",
        "memory.max_usage_in_bytes": "999",
        "memory.limit_in_bytes": str(EIGHT_GIB),
        "memory.failcnt": "4",
        "memory.oom_control": "oom_kill_disable 0\nunder_oom 0\noom_kill 2\n",
        "memory.kmem.usage_in_bytes": "12",
        "memory.stat": "rss 30\ncache 40\ntotal_rss 300\ntotal_cache 400\n"
        "total_mapped_file 23\ntotal_inactive_file 123\ntotal_shmem 7\n",
    }
    for name, value in files.items():
        write(tmp_path, "memory/" + name, value)
    result = read_cgroup(tmp_path)
    require_memory_budget(result)
    assert result["layout"] == "v1"
    assert result["memory.current"] == 777
    assert result["memory.peak"] == 999
    assert result["memory.max"] == EIGHT_GIB
    assert result["memory.stat"] == {
        "anon": 300,
        "file": 400,
        "file_mapped": 23,
        "inactive_file": 123,
        "shmem": 7,
        "kernel": 12,
    }
    assert result["memory.events"]["oom_kill"] == 2
    assert result["memory.events"]["failcnt"] == 4
    assert result["paths"]["limit"] == str(tmp_path / "memory/memory.limit_in_bytes")
    assert result["raw"]["memory/memory.oom_control"] == files["memory.oom_control"].strip()


def test_v2_maps_native_files_and_retains_exact_values(tmp_path):
    files = {
        "memory.current": "123",
        "memory.peak": "456",
        "memory.max": str(EIGHT_GIB),
        "memory.events": "max 3\nhigh 0\noom 2\noom_kill 1\n",
        "memory.stat": "anon 50\nfile 60\nkernel 7\nshmem 8\nfile_mapped 9\ninactive_file 10",
    }
    for name, value in files.items():
        write(tmp_path, name, value)
    result = read_cgroup(tmp_path)
    require_memory_budget(result)
    assert result["layout"] == "v2"
    assert result["memory.current"] == 123
    assert result["memory.peak"] == 456
    assert result["memory.stat"]["anon"] == 50
    assert result["memory.stat"]["file"] == 60
    assert result["memory.events"]["oom_kill"] == 1
    assert "failcnt" not in result["memory.events"]
    assert result["raw"]["memory.max"] == str(EIGHT_GIB)


@pytest.mark.parametrize("value", [None, "max", "not-a-number", "4294967296"])
def test_absent_unlimited_malformed_or_too_small_limit_never_passes(tmp_path, value):
    write(tmp_path, "memory.current", "100")
    if value is not None:
        write(tmp_path, "memory.max", value)
    with pytest.raises(RuntimeError, match="measured numeric"):
        require_memory_budget(read_cgroup(tmp_path))


def test_v2_missing_limit_does_not_silently_fall_back_to_other_hierarchy(tmp_path):
    write(tmp_path, "memory.current", "123")
    write(tmp_path, "memory/memory.usage_in_bytes", "234")
    write(tmp_path, "memory/memory.limit_in_bytes", str(EIGHT_GIB))
    measured = read_cgroup(tmp_path)
    assert measured["layout"] == "v2"
    with pytest.raises(RuntimeError):
        require_memory_budget(measured)


def test_missing_current_and_unavailable_layout_fail_closed(tmp_path):
    with pytest.raises(RuntimeError):
        require_memory_budget(read_cgroup(tmp_path))
    write(tmp_path, "memory.max", str(EIGHT_GIB))
    with pytest.raises(RuntimeError, match="current memory"):
        require_memory_budget(read_cgroup(tmp_path))


def test_event_deltas_do_not_report_missing_or_reset_counters_as_zero():
    before = {"memory.events": {"oom_kill": 2, "failcnt": 7, "max": 8}}
    after = {"memory.events": {"oom_kill": 2, "failcnt": 9, "max": 1}}
    result = memory_event_deltas(before, after)
    assert result["oom_kill"] == 0
    assert result["failcnt"] == 2
    assert result["max"] is None
    assert result["oom"] is None
