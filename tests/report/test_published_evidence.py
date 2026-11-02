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
