"""
LeyLine on a hand-built graph, which needs no store, no endpoint and no GPU
"""

from __future__ import annotations

from src.core.schema import Edge, Lineage
from src.miner.leyline import LeyLine, Settings

SETTINGS = Settings(
    weights={"extends": 1.0, "critiques": 1.0, "compares": 0.8, "background": 0.0},
    argues=("extends", "critiques", "compares"),
    seeds=3,
    walks=5,
)


def build(pairs: list[tuple[str, str, str]]) -> list[Edge]:
    return [Edge(source=s, target=t, intent=i, sentence="x" * 60) for s, t, i in pairs]


def line(edges: list[Edge], nodes: list[str], settings: Settings = SETTINGS) -> LeyLine:
    scores = {n: 1.0 for n in nodes}
    order = {n: float(i) for i, n in enumerate(nodes)}
    return LeyLine(edges, settings, scores, order, focus=scores)


def test_background_attracts_nothing():
    edges = build([("c", "a", "background"), ("d", "a", "background")])
    assert line(edges, ["a", "c", "d"]).magnets() == []


def test_the_argued_with_paper_wins():
    edges = build([("c", "a", "extends"), ("d", "a", "critiques"), ("c", "b", "background")])
    found = line(edges, ["a", "b", "c", "d"]).magnets()
    assert [m.node for m in found] == ["a"]
    assert found[0].weight == 1.0
    assert found[0].argued == {"extends": 1, "critiques": 1}


def test_share_separates_a_hub_from_a_magnet():
    argued = [("c", "a", "extends"), ("d", "a", "extends")]
    waved = [(f"w{i}", "b", "background") for i in range(8)] + [("c", "b", "extends")]
    found = line(build(argued + waved), ["a", "b", "c", "d"] + [f"w{i}" for i in range(8)])
    weight = {m.node: m.weight for m in found.magnets()}
    assert weight["a"] > weight["b"]


def test_a_lineage_runs_oldest_first():
    edges = build([("b", "a", "extends"), ("c", "b", "extends"), ("d", "c", "critiques")])
    found = line(edges, ["a", "b", "c", "d"]).lineages()
    assert found
    assert found[0].nodes == ["a", "b", "c"]
    assert found[0].runs >= 1


def test_a_path_ends_at_the_last_argued_with_node():
    edges = build([("b", "a", "extends"), ("c", "b", "extends")])
    found = line(edges, ["a", "b", "c"]).lineages()
    assert [f.nodes for f in found] == [["a", "b"]]


def test_a_contained_path_is_dropped():
    long = Lineage(nodes=["a", "b", "c"], magnets=["a"], runs=1)
    short = Lineage(nodes=["a", "b"], magnets=["a"], runs=1)
    kept = line([], []).prune([short, long], {"a": 1.0})
    assert [k.nodes for k in kept] == [["a", "b", "c"]]


def test_connectors_bridge_two_anchors():
    edges = build([("x", "a", "extends"), ("b", "x", "extends"), ("q", "z", "extends")])
    found = line(edges, ["a", "b", "x", "z", "q"]).connectors({"a", "b"}, 10)
    assert found == ["x"]


def test_two_intermediates_also_bridge():
    edges = build([("x", "a", "extends"), ("y", "x", "extends"), ("b", "y", "extends")])
    found = line(edges, ["a", "b", "x", "y"]).connectors({"a", "b"}, 10)
    assert sorted(found) == ["x", "y"]


def test_an_empty_graph_returns_nothing():
    empty = line([], [])
    assert empty.magnets() == []
    assert empty.lineages() == []
    assert empty.connectors(set(), 10) == []
