"""
The Benchmarks tab reads every split's runs, the legacy layout included, and every exported version
"""

import json
from pathlib import Path

import bench_results


def _scores(path: Path, recalls: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"recall": {"100": r / 2, "1000": r}} for r in recalls]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def test_runs_are_read_per_split_and_from_the_legacy_layout(tmp_path: Path):
    _scores(tmp_path / "test" / "SurveyMatch" / "survey" / "scores.jsonl", [0.8, 0.6])
    _scores(tmp_path / "SurveyMatch" / "survey" / "scores.jsonl", [0.5])
    _scores(tmp_path / "test" / "ConsensusMatch" / "consensus" / "scores.jsonl", [0.8])
    found = bench_results.runs(tmp_path)
    assert found["test"]["SurveyMatch"]["survey"]["cases"] == 2
    assert abs(found["test"]["SurveyMatch"]["survey"]["headline"] - 0.7) < 1e-9
    assert found["test"]["ConsensusMatch"]["consensus"]["headline"] == 0.4
    assert found["legacy"]["SurveyMatch"]["survey"]["headline"] == 0.5


def test_versions_skip_a_partial_export_and_mark_the_configured_one(tmp_path: Path):
    for name in ("graphiv-benchmarks-2026-10-22", "graphiv-benchmarks-2026-11-05.part"):
        (tmp_path / name).mkdir()
    counts = {"SurveyMatch": {"train": 3, "val": 1, "test": 1}}
    manifest = tmp_path / "graphiv-benchmarks-2026-10-22" / "manifest.json"
    manifest.write_text(json.dumps({"counts": counts}))
    found = bench_results.versions(tmp_path, "2026-10-22")
    assert [v["cutoff"] for v in found] == ["2026-10-22"]
    assert found[0]["current"] and found[0]["counts"] == counts
