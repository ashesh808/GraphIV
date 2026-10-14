"""
The scheduler's gate: a job waits only on the disks its own stages read or fill
"""

from pathlib import Path

import pytest

import stages
from jobs import Step
from schedule import Manager

LOW = {"ok": False, "free": 1, "total": 2}
FINE = {"ok": True, "free": 2, "total": 2}
DENIED = {"ok": False, "note": "[Errno 13] Permission denied"}


@pytest.fixture
def manager(tmp_path: Path) -> Manager:
    config = tmp_path / "config.toml"
    config.write_text(
        '[database]\nPG_DEST = ""\n[source]\nSOURCE_PATH = "' + str(tmp_path / "a.json") + '"\n'
    )
    made = Manager(tmp_path / "scripts", config, tmp_path / "state", "python")
    made.health = {"store": {"ok": True}, "disk": {"State": FINE, "Snapshot": FINE}}
    return made


def test_a_fetch_ignores_the_corpus(manager: Manager) -> None:
    manager.health["disk"] |= {"PDF store": DENIED, "HTML store": LOW}
    job = manager.add("fetch", [stages.step(stages.BY_KEY["papers.fetch"])])
    assert manager.blocker(job) == ""


def test_a_download_waits_on_its_store(manager: Manager) -> None:
    manager.health["disk"] |= {"PDF store": LOW}
    job = manager.add("pdfs", [stages.step(stages.BY_KEY["papers.1"])])
    assert manager.blocker(job) == "waiting for disk space on PDF store"


def test_an_unreachable_store_is_not_low_space(manager: Manager) -> None:
    manager.health["disk"] |= {"HTML store": DENIED}
    job = manager.add("html", [stages.step(stages.BY_KEY["papers.2"])])
    assert manager.blocker(job).startswith("cannot reach the HTML store: [Errno 13]")


def test_an_unknown_script_waits_on_every_disk(manager: Manager) -> None:
    manager.health["disk"] |= {"PDF store": LOW}
    job = manager.add("other", [Step(label="other", script="task/other.py")])
    assert manager.blocker(job) == "waiting for disk space on PDF store"


def test_a_dump_waits_on_its_own_disk(manager: Manager) -> None:
    manager.health["disk"] |= {"Export": LOW, "PDF store": LOW}
    job = manager.add("dump", [stages.step(stages.BY_KEY["export.0"])])
    assert manager.blocker(job) == "waiting for disk space on Export"
