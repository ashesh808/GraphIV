"""Offline and research stages remain discoverable after their paths diverge."""

import asyncio
import sys
from pathlib import Path

from offline.manager import stages
from offline.manager.discover import discover
from offline.manager.jobs import Runner, Step, Store


def script(path: Path, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "import argparse\n"
        "from pathlib import Path\n"
        f"{body}\n"
        'if __name__ == "__main__":\n'
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--config_path')\n"
        "    parser.add_argument('--workers', type=int, default=1)\n"
        "    parser.parse_args()\n"
    )


def test_discovery_includes_research_and_excludes_the_manager(tmp_path: Path) -> None:
    offline = tmp_path / "offline"
    script(offline / "papers_preprocess" / "stage0.py")
    script(offline / "manager" / "main.py")
    script(offline / "citation_labeler" / "train.py")
    research = tmp_path / "research"
    script(
        research / "recipe_tuning" / "stage2_evaluate.py",
        f"assert Path.cwd() == Path({str(tmp_path)!r})",
    )
    script(research / "scratch" / "experiment.py")

    found = asyncio.run(discover(offline, sys.executable, tmp_path / "help.json"))

    assert {item.path for item in found} == {
        "papers_preprocess/stage0.py",
        "../research/recipe_tuning/stage2_evaluate.py",
    }
    assert all([flag.flag for flag in item.flags] == ["--workers"] for item in found)


def test_a_research_job_runs_from_the_repository_root(tmp_path: Path) -> None:
    offline = tmp_path / "offline"
    offline.mkdir()
    research = tmp_path / "research" / "recipe_tuning" / "stage2_evaluate.py"
    script(research, f"assert Path.cwd() == Path({str(tmp_path)!r})")
    store = Store(tmp_path / "state" / "jobs")
    runner = Runner(store, offline, sys.executable, tmp_path / "offline.toml")
    job = store.new(
        "Evaluate", [Step("Evaluate", "../research/recipe_tuning/stage2_evaluate.py")]
    )

    asyncio.run(runner.run(job))

    assert job.status == "done", store.log(job).read_text()


def test_stage_commands_and_files_follow_the_component_layout() -> None:
    root = Path(__file__).resolve().parents[3]
    assert stages.BY_KEY["papers.0"].command().startswith("python offline/papers_preprocess/")
    assert stages.BY_KEY["eval.2"].command().startswith("python research/recipe_tuning/")
    for stage in stages.STAGES:
        if stage.kind == "script":
            assert (root / "offline" / stage.script).is_file(), stage.script
