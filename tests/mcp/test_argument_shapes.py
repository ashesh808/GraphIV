"""
The argument shapes a calling model actually sends, read the way each tool means them

Every shape here came from a local model's tool call that the strict signature had rejected
"""

from __future__ import annotations

from src.mcp.read_paper import as_fields, keywords
from src.mcp.write_report import as_sections


def test_one_keyword_stays_one():
    assert keywords("limitations") == ["limitations"]


def test_a_comma_list_is_several_keywords():
    assert keywords("threat model, defenses and results") == ["threat model", "defenses", "results"]


def test_a_list_of_keywords_is_kept():
    assert keywords(["Nix", " immutable "]) == ["nix", "immutable"]


def test_a_mapping_schema_becomes_fields():
    got = as_fields(
        {"attack": "What attack is studied", "kind": {"description": "x", "options": ["a"]}}
    )
    assert got == [
        {"name": "attack", "description": "What attack is studied"},
        {"name": "kind", "description": "x", "options": ["a"]},
    ]


def test_a_list_schema_is_kept():
    fields = [{"name": "attack", "description": "What attack is studied"}]
    assert as_fields(fields) == fields


def test_markdown_sections_are_cut_at_headings():
    got = as_sections("## Flaws\nInjection.\n## Defenses\nSandboxing.")
    assert got == [
        {"title": "Flaws", "body": "Injection."},
        {"title": "Defenses", "body": "Sandboxing."},
    ]


def test_a_list_of_markdown_and_dicts_is_read_both_ways():
    got = as_sections(["## A\nbody a", {"title": "B", "body": "body b"}])
    assert got == [{"title": "A", "body": "body a"}, {"title": "B", "body": "body b"}]


def test_prose_with_no_heading_is_one_untitled_section():
    assert as_sections("Just prose.") == [{"title": "", "body": "Just prose."}]


def test_no_sections_is_an_empty_list():
    assert as_sections(None) == []
