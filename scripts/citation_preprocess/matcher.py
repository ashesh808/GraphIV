"""
Resolve a citation to an arXiv id from ar5iv HTML, cheapest strategy first

The ladder runs link, regex, DOI, journal reference, exact title, then blocked fuzzy title
Each match above the cheapest tier is verified by year and author before it is accepted
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from rapidfuzz import fuzz, process  # pyright: ignore[reportMissingImports]
from selectolax.lexbor import (  # pyright: ignore[reportMissingImports]
    LexborHTMLParser,
    LexborNode,
)

# regex patterns

RE_MODERN: re.Pattern[str] = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b")
RE_LEGACY: re.Pattern[str] = re.compile(
    r"\b(astro-ph|cond-mat|gr-qc|hep-ex|hep-lat|hep-ph|hep-th|math-ph|nlin|nucl-ex|"
    r"nucl-th|physics|quant-ph|math|cs|q-bio|q-fin|stat|eess|econ)[./]\d{7}\b",
    re.IGNORECASE,
)
RE_DOI: re.Pattern[str] = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>,;]+", re.IGNORECASE)
RE_YEAR: re.Pattern[str] = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
RE_QUOTED: re.Pattern[str] = re.compile(r"[\"“‘]([^\"”’]{8,250})[\"”’]")

RE_JREF_A: re.Pattern[str] = re.compile(
    r"(?P<vol>[A-Za-z]?\d{1,4})\s*[,:]\s*(?P<page>\d{1,6}).{0,40}?(?P<year>(?:19|20)\d{2})"
)
RE_JREF_B: re.Pattern[str] = re.compile(
    r"(?P<vol>\d{1,4})\s*\((?P<year>(?:19|20)\d{2})\).{0,40}?(?P<page>\d{1,6})"
)
RE_JREF_C: re.Pattern[str] = re.compile(
    r"\b(?P<year>(?:19|20)\d{2})\s+[A-Za-z. ]{2,40}?\s+(?P<vol>[A-Za-z]?\d{1,4})\s+(?P<page>\d{1,6})\b"  # noqa: E501
)

RE_SURNAME: re.Pattern[str] = re.compile(r"\b([A-Z][a-zA-Z'\-]{2,})\b")

_PUNCT: re.Pattern[str] = re.compile(r"[^\w\s]")
_WS: re.Pattern[str] = re.compile(r"\s+")
# a private-use codepoint survives the HTML parser, unlike NUL
SENTINEL: str = "\ue001"
_BIBHREF: re.Pattern[str] = re.compile(r"^#?(bib\.bib\S+)$")

STOP: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "and",
        "or",
        "for",
        "on",
        "in",
        "to",
        "with",
        "from",
        "by",
        "at",
        "as",
        "is",
        "are",
        "be",
        "this",
        "that",
        "we",
        "our",
        "via",
        "using",
        "based",
        "new",
        "novel",
        "approach",
        "method",
        "study",
        "paper",
        "model",
        "analysis",
        "results",
        "letter",
        "letters",
    }
)

COMMON_NON_SURNAME: frozenset[str] = frozenset(
    {
        "phys",
        "rev",
        "lett",
        "vol",
        "proc",
        "natl",
        "acad",
        "sci",
        "annu",
        "math",
        "nucl",
        "comm",
        "commun",
        "mod",
        "intl",
        "internat",
        "eur",
        "amer",
        "stat",
        "appl",
        "univ",
        "press",
        "preprint",
        "rep",
        "ref",
        "ann",
        "soc",
        "inst",
        "tech",
        "theor",
        "exp",
        "the",
        "and",
        "for",
        "with",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "abstract",
        "report",
        "letter",
        "letters",
        "review",
        "reviews",
        "proceedings",
        "conference",
        "journal",
        "international",
        "advances",
        "annals",
        "transactions",
        "edited",
        "editor",
        "editors",
        "chapter",
        "section",
    }
)


# normalization helpers


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = _PUNCT.sub(" ", s.lower())
    return _WS.sub(" ", s).strip()


def _content_tokens(s: str) -> set[str]:
    return {w for w in _normalize(s).split() if len(w) >= 4 and w not in STOP}


def _blocking_key(norm_title: str) -> str | None:
    best: str | None = None
    for w in norm_title.split():
        if w in STOP or len(w) < 5:
            continue
        if best is None or len(w) > len(best):
            best = w
    return best


def _norm_surname(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z]", "", s.lower())


def _norm_page(p: str) -> str:
    s = p.lstrip("0")
    return s or "0"


def parse_jref(s: str) -> tuple[str, str, int] | None:
    for rx in (RE_JREF_A, RE_JREF_B, RE_JREF_C):
        m = rx.search(s)
        if m:
            return (
                m.group("vol").lower(),
                _norm_page(m.group("page")),
                int(m.group("year")),
            )
    return None


def year_from_arxiv_id(aid: str) -> int | None:
    """
    Publication year from a modern or legacy id, or None
    """
    m = re.match(r"(\d{2})(\d{2})\.\d{4,5}", aid)
    if m:
        yy = int(m.group(1))
        return 2000 + yy if yy < 50 else 1900 + yy
    m = re.search(r"/(\d{2})(\d{2})\d{3}", aid)
    if m:
        yy = int(m.group(1))
        return 1900 + yy if yy >= 90 else 2000 + yy
    return None


# index


@dataclass
class IndexRow:
    """
    One corpus paper as the title and blocking indexes hold it
    """

    arxiv_id: str
    year: int | None
    norm_title: str


@dataclass
class Index:
    """
    Every lookup table the resolver ladder consults
    """

    by_doi: dict[str, str]
    by_norm_title: dict[str, list[IndexRow]]
    blocks: dict[str, list[IndexRow]]
    by_jref: dict[tuple[str, str, int], list[str]]
    authors: dict[str, frozenset[str]]
    categories: dict[str, str]

    @classmethod
    def load(cls, pg_dest: str, verbose: bool = True) -> Index:
        """
        Build every lookup table from one pass over the papers table

        Args:
            pg_dest: libpq connection string.
            verbose: print timings.

        Returns:
            A populated index.
        """
        if verbose:
            print("loading index from papers ...", flush=True)
        t0 = time.time()
        with psycopg.connect(pg_dest) as conn:
            rows: list[tuple[str, ...]] = conn.execute(
                "SELECT arxiv_id, title, doi, date, journal_ref, surnames, primary_category"
                " FROM papers"
            ).fetchall()

        by_doi: dict[str, str] = {}
        by_norm_title: dict[str, list[IndexRow]] = defaultdict(list)
        blocks: dict[str, list[IndexRow]] = defaultdict(list)
        by_jref: dict[tuple[str, str, int], list[str]] = defaultdict(list)
        authors: dict[str, frozenset[str]] = {}
        cats: dict[str, str] = {}

        for aid, title, doi, when, jref, surnames, cat in rows:
            if doi:
                by_doi[doi.strip().lower()] = aid
            yr = year_from_arxiv_id(aid)
            if yr is None and when is not None:
                yr = getattr(when, "year", None)
            nt = _normalize(title or "")
            if nt:
                ix = IndexRow(arxiv_id=aid, year=yr, norm_title=nt)
                by_norm_title[nt].append(ix)
                bk = _blocking_key(nt)
                if bk:
                    blocks[bk].append(ix)
            if jref:
                k = parse_jref(jref)
                if k is not None:
                    by_jref[k].append(aid)
            if surnames:
                clean = {_norm_surname(s) for s in surnames}
                authors[aid] = frozenset(n for n in clean if len(n) >= 2)
            if cat:
                cats[aid] = cat

        if verbose:
            print(f"  loaded {len(rows):,} papers in {time.time() - t0:.1f}s", flush=True)

        return cls(
            by_doi=by_doi,
            by_norm_title=dict(by_norm_title),
            blocks=dict(blocks),
            by_jref=dict(by_jref),
            authors=authors,
            categories=cats,
        )


# lexbor helpers


_RX_BIB_TITLE = re.compile(r"ltx_bib_(title|paper|book|article)")
_RX_ITALIC_TYPE = re.compile(r"ltx_font_italic|ltx_font_typewriter")
_RX_SMALLCAPS = re.compile(r"ltx_font_smallcaps")
_RX_ITALIC_TYPE_OR_SMALLCAPS = re.compile(r"ltx_font_italic|ltx_font_typewriter|ltx_font_smallcaps")


def _node_text(node: LexborNode) -> str:
    return " ".join(node.text(separator=" ", strip=False).split())


def _arxiv_in(text: str) -> str | None:
    m = RE_MODERN.search(text)
    if m:
        return m.group(1)
    m = RE_LEGACY.search(text)
    if m:
        return m.group(0).lower().replace(".", "/")
    return None


def _extract_title(item: LexborNode) -> str | None:
    for el in item.css("[class*='ltx_bib_']"):
        cls = el.attributes.get("class") or ""
        if _RX_BIB_TITLE.search(cls):
            t = _node_text(el)
            if 8 <= len(t) <= 300:
                return t

    blocks = item.css("span.ltx_bibblock")
    if len(blocks) >= 2:
        b1 = blocks[1]
        cand = _node_text(b1)
        for it in b1.css("[class*='ltx_font_']"):
            cls = it.attributes.get("class") or ""
            if _RX_ITALIC_TYPE.search(cls):
                txt = _node_text(it)
                if txt and txt in cand:
                    cand = cand.replace(txt, "").strip()
        cand = cand.strip(" ,.;:")
        if 8 <= len(cand) <= 300:
            return cand

    bb: LexborNode = blocks[0] if blocks else item
    full = _node_text(bb)
    excised = full
    for el in bb.css("[class*='ltx_font_']"):
        cls = el.attributes.get("class") or ""
        if _RX_ITALIC_TYPE_OR_SMALLCAPS.search(cls):
            t = _node_text(el)
            if t:
                excised = excised.replace(t, " ", 1)
    excised = _WS.sub(" ", excised)
    excised = re.sub(r"\(?\b(19[5-9]\d|20[0-3]\d)\b\)?", " ", excised)
    excised = re.sub(
        r"\b(pp?\.|vol\.|no\.|eds?\.|chapter|chap\.|ed\.)\s*\S+",
        " ",
        excised,
        flags=re.IGNORECASE,
    )
    excised = re.sub(r"\b\d+\s*[-–]\s*\d+\b", " ", excised)
    excised = _WS.sub(" ", excised).strip(" ,.;:")
    chunks = [c.strip(" ,.;:") for c in re.split(r"[.;]| , ", excised)]
    chunks = [c for c in chunks if 12 <= len(c) <= 250]
    if chunks:
        return max(chunks, key=len)
    if 8 <= len(excised) <= 300:
        return excised
    return None


def _extract_surnames(item: LexborNode, raw_text: str) -> frozenset[str]:
    out: set[str] = set()
    for el in item.css("[class*='ltx_font_smallcaps']"):
        cls = el.attributes.get("class") or ""
        if not _RX_SMALLCAPS.search(cls):
            continue
        for m in RE_SURNAME.finditer(_node_text(el)):
            n = _norm_surname(m.group(1))
            if len(n) >= 3 and n not in COMMON_NON_SURNAME:
                out.add(n)
    if out:
        return frozenset(out)
    for m in RE_SURNAME.finditer(raw_text[:200]):
        n = _norm_surname(m.group(1))
        if len(n) >= 3 and n not in COMMON_NON_SURNAME:
            out.add(n)
    return frozenset(out)


# bibitem features


@dataclass
class BibFeatures:
    """
    The signals pulled out of one bibitem before resolution
    """

    raw_text: str
    link_arxiv: str | None
    text_arxiv: str | None
    doi: str | None
    title_candidate: str | None
    years: list[int]
    jref_key: tuple[str, str, int] | None
    surnames: frozenset[str]


def extract_features(item: LexborNode) -> BibFeatures:
    """
    Pull the resolvable signals out of one bibitem node
    """
    text = _node_text(item)
    link_aid: str | None = None
    for a in item.css("a"):
        href = a.attributes.get("href") or ""
        if "arxiv.org" in href:
            link_aid = _arxiv_in(href)
            if link_aid:
                break
    text_aid = _arxiv_in(text)
    doi_m = RE_DOI.search(text)
    doi = doi_m.group(0).rstrip(".,);") if doi_m else None
    title = _extract_title(item)
    years = [int(y) for y in RE_YEAR.findall(text)]
    jref_key = parse_jref(text)
    return BibFeatures(
        raw_text=text,
        link_arxiv=link_aid,
        text_arxiv=text_aid,
        doi=doi,
        title_candidate=title,
        years=years,
        jref_key=jref_key,
        surnames=_extract_surnames(item, text),
    )


# resolution


@dataclass
class ResolvedCitation:
    """
    One bibitem's resolution, with the method and score that produced it
    """

    bib_local_id: str
    raw_text: str
    arxiv_id: str | None
    method: str
    score: float
    matched_title: str | None = None
    note: str = ""
    features: BibFeatures | None = field(default=None, repr=False)


def _year_ok(bib_years: list[int], row_year: int | None) -> bool:
    if not bib_years or row_year is None:
        return True
    return any(abs(y - row_year) <= 1 for y in bib_years)


def _author_overlap(bib_surnames: frozenset[str], index: Index, aid: str) -> int:
    paper_surnames = index.authors.get(aid)
    if not paper_surnames:
        return -1
    return len(bib_surnames & paper_surnames)


def _resolve(
    feats: BibFeatures,
    index: Index,
    fuzzy_threshold: int,
    min_overlap: int,
) -> tuple[str | None, str, float, str | None, str]:
    if feats.link_arxiv:
        return feats.link_arxiv, "link", 100.0, None, ""
    if feats.text_arxiv:
        return feats.text_arxiv, "text", 100.0, None, ""
    if feats.doi:
        aid = index.by_doi.get(feats.doi.lower())
        if aid:
            return aid, "doi", 100.0, None, ""
    if feats.jref_key is not None:
        hits = index.by_jref.get(feats.jref_key)
        if hits and len(hits) == 1:
            return hits[0], "jref", 100.0, None, f"key={feats.jref_key}"

    if not feats.title_candidate:
        return None, "none", 0.0, None, "no title candidate"

    nt = _normalize(feats.title_candidate)
    if not nt or len(nt.split()) < 3:
        return None, "none", 0.0, None, "title too short"

    hits = index.by_norm_title.get(nt)
    if hits:
        best: IndexRow | None = None
        best_score = -1
        for r in hits:
            y = 1 if _year_ok(feats.years, r.year) else 0
            a = _author_overlap(feats.surnames, index, r.arxiv_id)
            s = y * 10 + max(a, 0)
            if s > best_score:
                best_score = s
                best = r
        if best is not None:
            yok = _year_ok(feats.years, best.year)
            aov = _author_overlap(feats.surnames, index, best.arxiv_id)
            method = "title-exact" if yok else "title-exact-noyr"
            note = f"row_year={best.year} bib_years={feats.years} authors={aov}"
            return best.arxiv_id, method, 100.0, nt, note

    bk = _blocking_key(nt)
    if not bk:
        return None, "none", 0.0, None, "no blocking key"
    bucket = index.blocks.get(bk)
    if not bucket:
        return None, "none", 0.0, None, f"empty block {bk}"

    sample = bucket[:8000]
    choices = [r.norm_title for r in sample]
    match = process.extractOne(
        nt, choices, scorer=fuzz.token_set_ratio, score_cutoff=fuzzy_threshold
    )
    if match is None:
        return None, "none", 0.0, None, f"no fuzzy >= {fuzzy_threshold}"
    matched_title, score, idx = match
    row = sample[idx]

    raw_tokens = _content_tokens(feats.raw_text)
    match_tokens = _content_tokens(matched_title)
    overlap = len(raw_tokens & match_tokens)
    if overlap < min_overlap:
        return (
            None,
            "rejected-overlap",
            float(score),
            matched_title,
            f"overlap={overlap}<{min_overlap}",
        )
    if not _year_ok(feats.years, row.year):
        return (
            None,
            "rejected-year",
            float(score),
            matched_title,
            f"row_year={row.year} bib_years={feats.years}",
        )
    aov = _author_overlap(feats.surnames, index, row.arxiv_id)
    if aov == 0 and feats.surnames:
        return (
            None,
            "rejected-author",
            float(score),
            matched_title,
            f"bib_surnames={sorted(feats.surnames)[:4]} no overlap",
        )
    return (
        row.arxiv_id,
        "title-fuzzy",
        float(score),
        matched_title,
        f"overlap={overlap} row_year={row.year} authors={aov}",
    )


# Citation occurrence extraction (NEW)


@dataclass
class CitationOccurrence:
    """
    A single inline citation mention in a body paragraph
    """

    ordinal: int  # 0-based, in document order
    bib_local_id: str  # 'bib.bib7'
    cited_arxiv_id: str | None
    method: str
    score: float
    section: str | None
    sentence: str
    paragraph: str
    raw_bib_text: str
    co_cited_bibs: list[str]  # other bib ids in the same [1,2,3] group


def _nearest_ancestor(node: LexborNode, tags: set[str]) -> LexborNode | None:
    cur = node.parent
    while cur is not None:
        if cur.tag in tags:
            return cur
        cur = cur.parent
    return None


def _nearest_section_title(node: LexborNode) -> str | None:
    cur = node.parent
    while cur is not None:
        if cur.tag == "section":
            for h in cur.css("h1, h2, h3, h4"):
                t = _norm_text_stripping_math(h)
                if t:
                    return t
            return None
        cur = cur.parent
    return None


def _norm_text_stripping_math(node: LexborNode) -> str:
    # remove math subtrees from the rendered text
    for m in node.css("math"):
        m.decompose()  # pyright: ignore[reportAttributeAccessIssue]
    return " ".join(node.text(separator=" ", strip=False).split())


def _href_to_bib(href: str) -> str | None:
    if not href:
        return None
    m = _BIBHREF.match(href)
    return m.group(1) if m else None


def extract_citations(
    html_path: Path,
    index: Index,
    fuzzy_threshold: int = 88,
    min_overlap: int = 4,
) -> tuple[dict[str, ResolvedCitation], list[CitationOccurrence], dict[int, str]]:
    """
    Parse `html_path`, resolve all bibitems, walk every inline mention

    Returns:
            bibitems , dict[bib_local_id -> ResolvedCitation]
            occurs   , list[CitationOccurrence], one per `<a class~="ltx_ref">`.
    """
    data = html_path.read_text(encoding="utf-8", errors="replace")
    tree = LexborHTMLParser(data)

    # resolve bibitems first
    bibitems: dict[str, ResolvedCitation] = {}
    for it in tree.css("li.ltx_bibitem"):
        local_id = it.attributes.get("id") or ""
        if not local_id:
            continue
        feats = extract_features(it)
        aid, method, score, matched, note = _resolve(feats, index, fuzzy_threshold, min_overlap)
        bibitems[local_id] = ResolvedCitation(
            bib_local_id=local_id,
            raw_text=feats.raw_text,
            arxiv_id=aid,
            method=method,
            score=score,
            matched_title=matched,
            note=note,
        )

    # strip math subtrees once, globally, for clean context text
    for m in tree.css("math"):
        m.decompose()  # pyright: ignore[reportAttributeAccessIssue]

    # walk every inline ltx_ref that points at a bibitem, in document order
    occurs: list[CitationOccurrence] = []
    # pre-pass: find groups of co-cited bibs (same parent that holds multiple refs)
    inline_refs: list[tuple[LexborNode, str]] = []
    for a in tree.css("a.ltx_ref"):
        href = a.attributes.get("href") or ""
        bib = _href_to_bib(href)
        if bib is None:
            continue
        inline_refs.append((a, bib))

    # group by parent paragraph for co-citation detection
    parent_to_bibs: dict[int, list[str]] = defaultdict(list)
    for a, bib in inline_refs:
        para = _nearest_ancestor(a, {"p"})
        key = id(para) if para is not None else -1
        parent_to_bibs[key].append(bib)

    marker_text: dict[int, str] = {}
    for ordinal, (a, bib) in enumerate(inline_refs):
        para = _nearest_ancestor(a, {"p"})
        section = _nearest_section_title(a)
        marker_text[ordinal] = " ".join(a.text(separator=" ", strip=False).split())
        if para is None:
            paragraph = ""
            sentence = ""
        else:
            """
            The marker is a private-use codepoint because the HTML parser deletes NUL on insert,
            which is what silently disabled sentence extraction for the whole corpus.
            Each marker carries its ordinal, so a paragraph citing several works stays unambiguous.
            """
            a.replace_with(
                f"{SENTINEL}{ordinal}{SENTINEL}"
            )  # pyright: ignore[reportAttributeAccessIssue]
            paragraph = para.text(separator=" ", strip=False)
            sentence = ""

        bibitem = bibitems.get(bib)
        co_bibs = [b for b in parent_to_bibs[id(para) if para is not None else -1] if b != bib]
        occurs.append(
            CitationOccurrence(
                ordinal=ordinal,
                bib_local_id=bib,
                cited_arxiv_id=bibitem.arxiv_id if bibitem else None,
                method=bibitem.method if bibitem else "none",
                score=bibitem.score if bibitem else 0.0,
                section=section,
                sentence=sentence,
                paragraph=paragraph,
                raw_bib_text=bibitem.raw_text if bibitem else "",
                co_cited_bibs=co_bibs,
            )
        )

    return bibitems, occurs, marker_text


# CitationResolver public class (kept for backward compat)


class CitationResolver:
    """
    The resolver ladder bound to one loaded index
    """

    index: Index
    fuzzy_threshold: int
    min_overlap: int

    def __init__(
        self,
        pg_dest: str = "",
        fuzzy_threshold: int = 88,
        min_overlap: int = 4,
        verbose: bool = True,
        index: Index | None = None,
    ) -> None:
        self.index = index if index is not None else Index.load(pg_dest, verbose=verbose)
        self.fuzzy_threshold = fuzzy_threshold
        self.min_overlap = min_overlap

    def resolve_html(self, html_path: Path) -> list[ResolvedCitation]:
        """
        Resolve every bibitem in one rendered paper
        """
        bibitems, _, _ = extract_citations(
            html_path, self.index, self.fuzzy_threshold, self.min_overlap
        )
        return list(bibitems.values())


__all__ = [
    "BibFeatures",
    "CitationOccurrence",
    "CitationResolver",
    "Index",
    "IndexRow",
    "ResolvedCitation",
    "extract_citations",
    "extract_features",
    "year_from_arxiv_id",
]
