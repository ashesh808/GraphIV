"""Research readers resolve relocated files independently of the working directory."""

from pathlib import Path

from research.assets.code import benchmark_scores, leyline_scores


def test_benchmark_output_is_relative_to_its_config(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    output = tmp_path / "results" / "SurveyMatch" / "survey"
    output.mkdir(parents=True)
    (output / "scores.jsonl").write_text('{"ceiling": 0.25}\n{"ceiling": 0.75}\n')
    config = config_dir / "offline.toml"
    config.write_text('[recipe_tuning]\nOUTPUT_PATH = "../results"\n')
    monkeypatch.chdir(config_dir)

    assert benchmark_scores.ceiling(config, "SurveyMatch", "survey") == 0.5


def test_recipe_lookup_is_relative_to_its_config(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "survey.toml").write_text(
        '[[component]]\nKIND = "GraphScorer"\nCORE = 12\n'
        '[component.weights]\nANC = 2.0\nFRO = 0.0\n'
    )
    config = config_dir / "offline.toml"
    config.write_text('[serve]\nRECIPE_PATH = "../recipes"\n')
    monkeypatch.chdir(config_dir)

    assert benchmark_scores.exponents(config, "survey") == {
        "core": 12,
        "weights": {"anc": 2.0},
        "miner": {},
    }


def test_archived_findings_are_read_from_the_research_directory() -> None:
    root = Path(__file__).resolve().parents[2]
    assert benchmark_scores.agreement(root)[0] > 0
    assert leyline_scores.load(root)["topics"]
