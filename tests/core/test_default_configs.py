"""Splitting config files preserves the locations of shared runtime data."""

from pathlib import Path

from src.core.config import load_config
from src.core.paths import OFFLINE_CONFIG, PROJECT_ROOT, RUNTIME_CONFIG


def test_shared_runtime_settings_match_the_offline_tools() -> None:
    runtime = load_config(RUNTIME_CONFIG)
    offline = load_config(OFFLINE_CONFIG)
    for key in ("database", "source", "dataset", "serve", "endpoints"):
        assert runtime[key] == offline[key]
    assert "manager" not in runtime
    assert "recipe_tuning" not in runtime


def test_default_data_paths_stay_at_the_repository_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    runtime = load_config(RUNTIME_CONFIG)
    offline = load_config(OFFLINE_CONFIG)

    assert Path(runtime["dataset"]["GRAPH_PATH"]).resolve() == (
        PROJECT_ROOT / "data/citation_graph_export.npy"
    )
    assert Path(runtime["serve"]["RECIPE_PATH"]).resolve() == PROJECT_ROOT / "retrieval_recipes"
    assert Path(offline["recipe_tuning"]["OUTPUT_PATH"]).resolve() == (
        PROJECT_ROOT / "research/experiments/retrieve"
    )
