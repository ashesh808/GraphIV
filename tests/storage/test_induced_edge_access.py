"""Source-index reads retain the exact sequence of the original target-index traversal."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

from src.storage.sqlite import SQLiteCorpus

IDS = ["hep-th/9901001", "d", "c", "b", "a"]
# Deliberately neither insertion nor source/target order. citation_id is SQLite's rowid.
OCCURRENCES = [
    (90, "b", "a", 1, "Later duplicate", "extends", 0.25),
    (7, "b", "a", 1, "First duplicate", "extends", 0.95),
    (60, "b", "a", 1, None, "extends", None),
    (4, "c", "a", 1, "Critique occurrence", "critiques", 0.42),
    (39, "a", "c", 1, "Later use", "uses", 0.84),
    (12, "a", "c", 1, "Earlier use", "uses", 0.37),
    (55, "d", "b", 1, None, None, None),
    (2, "b", "a", 1, "Background occurrence", "background", 0.8),
    (77, "a", "b", 0, "Not labeled", "extends", 1.0),
    (13, "a", None, 1, "Unresolved target", "extends", 0.8),
    (15, "excluded-source", "a", 1, "Source outside set", "extends", 0.8),
    (17, "a", "excluded-target", 1, "Target outside set", "extends", 0.8),
    (3, "d", "d", 1, "Self occurrence remains a data row", "uses", 0.5),
    (101, "hep-th/9901001", "a", 1, "Legacy identifier", "motivates", 0.99),
    (33, "c", "b", 1, "Empty label and zero score", "", 0.0),
    (5, "a", "b", 1, "Null label with confidence", None, 0.2),
    (21, "d", "a", 2, "Wrong completed stage", "critiques", 0.98),
]


@pytest.fixture
def induced_corpus(tmp_path: Path):
    """Create a real tiny SQLite file without a vector index or model dependencies."""
    database = tmp_path / "metadata.sqlite"
    schema = Path(__file__).resolve().parents[2] / "src/storage/schema.sql"
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(schema.read_text())
        connection.executemany(
            "INSERT INTO citations(citation_id,source_id,target_id,stage,sentence,intent,"
            "intent_score) VALUES (?,?,?,?,?,?,?)",
            OCCURRENCES,
        )
        connection.commit()
    return database, SQLiteCorpus(database)


def original_rows(
    database: Path, identifiers: list[str], *, scored: bool, index: str = "citations_target"
):
    """Use the original unordered query, forcing its original target-index access path."""
    columns = "source_id,target_id,intent,sentence" + (",intent_score" if scored else "")
    # The index is test-owned, never externally supplied.
    assert index in {"citations_source", "citations_target"}
    sql = (
        f"SELECT {columns} FROM citations INDEXED BY {index} WHERE stage=1 "
        "AND source_id IN (SELECT value FROM json_each(?)) "
        "AND target_id IN (SELECT value FROM json_each(?)) AND target_id IS NOT NULL"
    )
    encoded = json.dumps(identifiers)
    with closing(sqlite3.connect(database)) as connection:
        return connection.execute(sql, (encoded, encoded)).fetchall()


@pytest.mark.parametrize("method,scored", [("edges", False), ("edge_records", True)])
@pytest.mark.parametrize("identifiers", [IDS, ["c", "a", "b", "a"], ["b"], ["not-present"], []])
def test_induced_reads_match_original_target_index_sequence_and_values(
    induced_corpus, method, scored, identifiers
):
    database, corpus = induced_corpus
    expected = original_rows(database, identifiers, scored=scored)
    assert getattr(corpus, method)(identifiers) == expected


def test_reference_fixture_exposes_order_changes_and_preserves_each_scored_occurrence(
    induced_corpus,
):
    database, corpus = induced_corpus
    expected = original_rows(database, IDS, scored=True)
    unordered_source = original_rows(database, IDS, scored=True, index="citations_source")
    assert expected != unordered_source  # An access-path-only change without ORDER BY would fail.
    assert len(expected) == len(unordered_source) == 12
    assert [row for row in expected if row[:3] == ("b", "a", "extends")] == [
        ("b", "a", "extends", "First duplicate", 0.95),
        ("b", "a", "extends", None, None),
        ("b", "a", "extends", "Later duplicate", 0.25),
    ]
    assert ("d", "b", None, None, None) in expected
    assert ("c", "b", "", "Empty label and zero score", 0.0) in expected
    assert corpus.edge_records(IDS) == expected


def test_adapter_really_uses_source_index_while_successor_query_is_unchanged(
    induced_corpus, monkeypatch
):
    database, corpus = induced_corpus
    captured = []
    original = corpus._rows

    def observe(sql, parameters=()):
        captured.append((sql, parameters))
        return original(sql, parameters)

    monkeypatch.setattr(corpus, "_rows", observe)
    corpus.edges(IDS)
    corpus.edge_records(IDS)
    with closing(sqlite3.connect(database)) as connection:
        for sql, parameters in captured:
            plan = connection.execute("EXPLAIN QUERY PLAN " + sql, parameters).fetchall()
            assert any("USING INDEX citations_source" in row[3] for row in plan)
    # No paper rows exist, so this evaluates the real successor query and returns no vectors.
    assert (
        corpus.successors([1.0, 0.0], IDS, date(2020, 1, 1), date(2021, 1, 1), ("extends",), 0.5)
        == []
    )
    successor_sql, _ = captured[-1]
    assert "INDEXED BY citations_source" not in successor_sql
    assert "c.target_id IN" in successor_sql
    assert "c.intent_score >= ?" in successor_sql
