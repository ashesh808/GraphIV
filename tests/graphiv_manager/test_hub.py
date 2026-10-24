"""
Publishing runs only from its own button, and the page can tell whether the token may push
"""

import probes
import stages

FINE_GRAINED = {
    "auth": {
        "accessToken": {
            "role": "fineGrained",
            "fineGrained": {
                "scoped": [
                    {
                        "entity": {"type": "dataset", "name": "kkuroma/GraphIV"},
                        "permissions": ["repo.content.read", "repo.write"],
                    },
                    {
                        "entity": {"type": "model", "name": "kkuroma/GraphIV-survey"},
                        "permissions": ["repo.content.read"],
                    },
                ]
            },
        }
    }
}


def test_publish_stays_out_of_every_batch() -> None:
    assert "export.3" not in stages.of_table("export")
    assert "export.3" not in stages.everything()
    assert stages.of_table("export") == ["export.0", "export.1", "export.2"]


def test_a_scoped_token_writes_only_its_repos() -> None:
    assert probes.writable(FINE_GRAINED, "kkuroma/GraphIV")
    assert not probes.writable(FINE_GRAINED, "kkuroma/GraphIV-survey")
    assert not probes.writable(FINE_GRAINED, "kkuroma/GraphIV-citation-intent")


def test_a_namespace_scope_writes_every_repo_in_it() -> None:
    who = {
        "auth": {
            "accessToken": {
                "role": "fineGrained",
                "fineGrained": {
                    "scoped": [
                        {
                            "entity": {"type": "user", "name": "kkuroma"},
                            "permissions": ["repo.write"],
                        }
                    ]
                },
            }
        }
    }
    assert probes.writable(who, "kkuroma/GraphIV-survey")
    assert not probes.writable(who, "someone/GraphIV")


def test_a_write_token_writes_and_a_read_token_does_not() -> None:
    assert probes.writable({"auth": {"accessToken": {"role": "write"}}}, "kkuroma/GraphIV")
    assert not probes.writable({"auth": {"accessToken": {"role": "read"}}}, "kkuroma/GraphIV")


def test_no_token_is_said_plainly() -> None:
    found = probes.hub("", ["kkuroma/GraphIV"])
    assert not found["token"]
    assert found["repos"] == [{"id": "kkuroma/GraphIV", "write": False}]
    assert "HF_TOKEN_PATH" in found["note"]
