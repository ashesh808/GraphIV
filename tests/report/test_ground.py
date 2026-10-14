"""
The grounding guard, on the two shapes a document cites in and the three things it does to them
"""

from __future__ import annotations

from src.report.ground import distance, linkify, mark, nearest, read_ids, strip

GIVEN = {"2006.10637": "2006.10637", "hep-th/0409210": "hep-th/0409210"}


def test_both_citation_shapes_are_found():
    text = "see [`2006.10637`](https://arxiv.org/abs/2006.10637) and arXiv:2004.04926"
    assert read_ids(text) == {"2006.10637", "2004.04926"}


def test_a_legacy_id_is_found():
    assert read_ids("arXiv:hep-th/0409210") == {"hep-th/0409210"}


def test_an_id_nowhere_near_one_given_is_not_corrected():
    assert nearest("1111.11111", GIVEN) is None


def test_one_edit_away_is_a_typo():
    assert nearest("2006.10638", GIVEN) == "2006.10637"


def test_two_candidates_one_edit_away_are_ambiguous():
    assert nearest("2006.10630", {"2006.10631": "2006.10631", "2006.10632": "2006.10632"}) is None


def test_distance_stops_at_the_cap():
    assert distance("aaaa", "bbbb", 2) == 3


def test_a_stripped_link_takes_its_brackets_with_it():
    text = "a real [`2006.10637`](https://arxiv.org/abs/2006.10637) and a fake [`0000.00000`](https://arxiv.org/abs/0000.00000)."
    out = strip(text, {"0000.00000"})
    assert "0000.00000" not in out
    assert "2006.10637" in out
    assert out.rstrip().endswith(".")


def test_a_stripped_mention_leaves_the_sentence_readable():
    assert strip("built on arXiv:0000.00000 and nothing else", {"0000.00000"}) == (
        "built on and nothing else"
    )


def test_linkify_leaves_an_existing_link_alone():
    text = "[arXiv:2006.10637](https://arxiv.org/abs/2006.10637)"
    assert linkify(text) == text


def test_linkify_turns_a_mention_into_a_link():
    assert linkify("see arXiv:2006.10637 now") == (
        "see [arXiv:2006.10637](https://arxiv.org/abs/2006.10637) now"
    )


def test_a_bare_id_is_given_its_prefix():
    text = "BA-Cite [2510.19246] and (2408.03934, physics/0612122)."
    assert read_ids(mark(text)) == {"2510.19246", "2408.03934", "physics/0612122"}


def test_a_prefixed_or_linked_id_is_left_alone():
    text = "arXiv:2510.19246 and [`2006.10637`](https://arxiv.org/abs/2006.10637) at 0.9734"
    assert mark(text) == text
