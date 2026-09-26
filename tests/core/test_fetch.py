"""
Where a paper is looked for, over a corpus and a cache built in a temp directory

Nothing here reaches the network, since every case leaves fetch off
"""

from __future__ import annotations

from pathlib import Path

from src.core.fetch import html_file, html_path, newest_pdf, pdf_file, stem, yymm


def test_a_modern_id_names_its_directory():
    assert yymm("2006.10637") == "2006"


def test_a_legacy_id_names_its_directory():
    assert yymm("hep-th/0409210") == "0409"


def test_an_id_that_does_not_parse_has_no_directory():
    assert yymm("not-an-id") is None


def test_a_legacy_id_folds_its_archive_into_the_stem():
    assert stem("hep-th/0409210") == "hep-th0409210"


def test_the_html_name_carries_no_version(tmp_path: Path):
    assert html_path(tmp_path, "2006.10637") == tmp_path / "2006" / "2006.10637.html"


def test_the_corpus_is_read_before_the_cache(tmp_path: Path):
    corpus, cache = tmp_path / "corpus", tmp_path / "cache"
    for root in (corpus, cache):
        (root / "2006").mkdir(parents=True)
        _ = (root / "2006" / "2006.10637.html").write_text("x", encoding="utf-8")
    assert html_file(corpus, cache, "2006.10637") == corpus / "2006" / "2006.10637.html"


def test_a_paper_only_in_the_cache_is_still_found(tmp_path: Path):
    corpus, cache = tmp_path / "corpus", tmp_path / "cache"
    corpus.mkdir()
    (cache / "2006").mkdir(parents=True)
    _ = (cache / "2006" / "2006.10637.html").write_text("x", encoding="utf-8")
    assert html_file(corpus, cache, "2006.10637") == cache / "2006" / "2006.10637.html"


def test_a_miss_with_fetch_off_returns_nothing(tmp_path: Path):
    assert html_file(tmp_path, tmp_path, "2006.10637") is None
    assert pdf_file(tmp_path, tmp_path, "2006.10637") is None


def test_the_highest_pdf_version_wins(tmp_path: Path):
    (tmp_path / "2006").mkdir()
    for name in ("2006.10637v1.pdf", "2006.10637v3.pdf", "2006.10637v2.pdf"):
        _ = (tmp_path / "2006" / name).write_bytes(b"%PDF-")
    assert newest_pdf(tmp_path, "2006.10637") == tmp_path / "2006" / "2006.10637v3.pdf"


def test_a_versionless_pdf_is_found_when_no_version_is(tmp_path: Path):
    (tmp_path / "2006").mkdir()
    _ = (tmp_path / "2006" / "2006.10637.pdf").write_bytes(b"%PDF-")
    assert newest_pdf(tmp_path, "2006.10637") == tmp_path / "2006" / "2006.10637.pdf"


def test_a_version_that_is_not_a_number_is_ignored(tmp_path: Path):
    (tmp_path / "2006").mkdir()
    _ = (tmp_path / "2006" / "2006.10637vX.pdf").write_bytes(b"%PDF-")
    assert newest_pdf(tmp_path, "2006.10637") is None
