"""Published intent labels remain usable without manufacturing citation text."""

from datetime import date

from src.core.schema import Edge, Paper
from src.mcp.write_report import between
from src.miner.miner import Mined
from src.miner.store import read_edges
from src.report.compose import digest


def test_published_digest_qualifies_predicted_relations_without_text():
    paper = Paper(
        arxiv_id="2401.00001", title="A real title", abstract="Evidence", date=date(2024, 1, 1)
    )
    found = Mined(
        edges=[Edge(source=paper.arxiv_id, target="2301.00001", intent="uses", intent_score=0.93)]
    )
    evidence = digest("A question", [paper], {}, found, None, [])
    assert "Citation sentences are unavailable" in evidence
    assert "not quotations" in evidence
    assert "Do not invent or reconstruct wording" in evidence


def test_occurrence_confidences_survive_storage_and_lineage_serialization(monkeypatch):
    class Corpus:
        def edge_records(self, ids):
            assert ids == ["2401.00001", "2301.00001"]
            return [
                ("2401.00001", "2301.00001", "uses", None, 0.93),
                ("2401.00001", "2301.00001", "extends", None, 0.88),
            ]

    monkeypatch.setattr("src.miner.store.open_corpus", lambda _: Corpus())
    ids = ["2401.00001", "2301.00001"]
    edges = read_edges("unused", ids)
    assert len(edges) == 2
    assert [edge.intent for edge in edges] == ["uses", "extends"]
    assert [edge.intent_score for edge in edges] == [0.93, 0.88]
    assert all(edge.sentence == "" for edge in edges)
    rendered = between(ids, edges)
    assert len(rendered) == 2
    assert [edge["intent_score"] for edge in rendered] == [0.93, 0.88]


def test_successor_metadata_can_be_explored_without_being_mislabeled_retrieved(monkeypatch):
    from types import SimpleNamespace

    from src.mcp.write_report import as_papers
    from src.miner.miner import Successor

    kept = Paper(
        arxiv_id="2301.00001", title="Earlier work", abstract="Original", date=date(2023, 1, 1)
    )
    successor = Paper(
        arxiv_id="2401.00001",
        title="Follow-up work",
        abstract="Extension",
        date=date(2024, 1, 1),
        cosine=0.87,
    )
    records = {
        paper.arxiv_id: {
            "title": paper.title,
            "authors": "Published author",
            "abstract": paper.abstract,
            "date": paper.date.isoformat(),
            "category": "cs.CL",
            "topic": [],
            "topic_id": [],
        }
        for paper in [kept, successor]
    }

    def read_records(_source, ids):
        assert ids == [kept.arxiv_id, successor.arxiv_id]
        return records

    monkeypatch.setattr("src.mcp.write_report.read_records", read_records)
    found = Mined(successors=[Successor(paper=successor, targets={kept.arxiv_id: "extends"})])
    rows = as_papers(SimpleNamespace(dsn="unused"), [kept], {}, found, set())
    assert len(rows) == 2
    assert rows[0]["retrieved"] is True
    assert rows[1] == records[successor.arxiv_id] | {
        "arxiv_id": successor.arxiv_id,
        "year": "2024",
        "role": "successor",
        "relevance": None,
        "cosine": 0.87,
        "magnet": None,
        "retrieved": False,
        "cited": False,
    }
