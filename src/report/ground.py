"""
The guard every draft passes through, so no arXiv id leaves this package unless the corpus holds it

An id inside two edits of one the writer was given is a typo and is corrected where it stands
Anything else that does not exist is cut out of the sentence rather than left for a reader to chase
"""

from __future__ import annotations

import logging
import re

from src.storage.corpus import CorpusSource, open_corpus

LOG = logging.getLogger(__name__)


# modern ids, legacy prefixed ids, and the bare legacy form, which is almost always invented
ID = r"([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5}|\d{7})"
# a document cites either as a link or as a mention, and both have to be checked
FOUND = re.compile(rf"(?:arXiv:\s?|arxiv\.org/abs/){ID}", re.IGNORECASE)
LINKED = re.compile(rf"\[[^\]]*\]\(\s*https?://arxiv\.org/abs/{ID}[^)]*\)", re.IGNORECASE)
MENTION = re.compile(rf"\s*[\[(]?\s*arXiv:\s?{ID}\s*[\])]?", re.IGNORECASE)
LINKABLE = re.compile(
    r"[\[(]?\s*arXiv:\s?([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5})(?:\s*[\])])?",
    re.IGNORECASE,
)

# an id the writer left without its prefix, never one inside a link, a path or a longer number
BARE = re.compile(r"(?<![\w/:.`\-])([a-z][a-z.\-]+/\d{7}|\d{4}\.\d{4,5})(?!\d)", re.IGNORECASE)

SHORT_ID = 8


class Grounded:
    """
    One checked draft, and everything the check had to do to it
    """

    def __init__(
        self,
        text: str,
        held: list[str],
        beyond: list[str],
        fixed: dict[str, str],
        cut: list[str],
    ) -> None:
        """
        Holds the clean text beside the account of what changed

        Args:
            text: The draft after correcting and cutting.
            held: Ids the writer was given and used.
            beyond: Ids that exist but were not in what the writer was given.
            fixed: Every typo corrected, from what was written to what it meant.
            cut: Every id removed because no paper carries it.
        """
        self.text = text
        self.held = held
        self.beyond = beyond
        self.fixed = fixed
        self.cut = cut


def distance(one: str, other: str, cap: int = 2) -> int:
    """
    Edit distance between two ids, stopping as soon as it passes the cap

    Args:
        one: The first id.
        other: The second id.
        cap: The most edits to count.

    Returns:
        The distance, or one past the cap when it is larger.
    """
    if abs(len(one) - len(other)) > cap:
        return cap + 1
    prev = list(range(len(other) + 1))
    for i, left in enumerate(one, 1):
        row = [i]
        for j, right in enumerate(other, 1):
            row.append(min(prev[j] + 1, row[-1] + 1, prev[j - 1] + (left != right)))
        if min(row) > cap:
            return cap + 1
        prev = row
    return prev[-1]


def nearest(bad: str, allowed: dict[str, str]) -> str | None:
    """
    Which given id a written one is a typo of, when exactly one answers

    Two edits only identify a paper when the id is long, so a short id is left alone.

    Args:
        bad: The id as written.
        allowed: Lowercased id to the id as the caller gave it.

    Returns:
        The intended id, or None when nothing or more than one matches.
    """
    close = [v for k, v in allowed.items() if distance(bad, k, 1) <= 1]
    if len(close) == 1:
        return close[0]
    if close or len(bad) < SHORT_ID:
        return None
    wider = [v for k, v in allowed.items() if distance(bad, k, 2) <= 2]
    return wider[0] if len(wider) == 1 else None


def read_ids(text: str) -> set[str]:
    """
    Every arXiv id a draft cites

    Args:
        text: The draft.

    Returns:
        The ids, lowercased.
    """
    return {m.group(1).lower() for m in FOUND.finditer(text)}


def exist(dsn: CorpusSource, arxiv_ids: list[str]) -> set[str]:
    """
    Which of a list of ids the corpus actually holds

    Args:
        dsn: A libpq connection string or corpus adapter.
        arxiv_ids: The ids to check.

    Returns:
        The ids that exist, lowercased.
    """
    if not arxiv_ids:
        return set()
    rows = open_corpus(dsn).existing_ids(arxiv_ids)
    return {str(r[0]).lower() for r in rows}


def strip(text: str, arxiv_ids: set[str]) -> str:
    """
    Removes every mention of a set of ids, and the brackets left around them

    Args:
        text: The draft.
        arxiv_ids: The ids to remove, lowercased.

    Returns:
        The text without them.
    """
    joined = LINKED.sub(lambda m: "" if m.group(1).lower() in arxiv_ids else m.group(0), text)
    out: list[str] = []
    last = 0
    for found in MENTION.finditer(joined):
        if found.group(1).lower() not in arxiv_ids:
            continue
        out.append(joined[last : found.start()])
        out.append(" ")
        last = found.end()
    out.append(joined[last:])
    joined = "".join(out)
    joined = re.sub(r"\(\s*\)|\[\s*\]", "", joined)
    joined = re.sub(r" {2,}", " ", joined)
    return re.sub(r"\s+([.,;])", r"\1", joined)


def mark(text: str) -> str:
    """
    Gives every bare id its prefix, since the check and the links only see a prefixed one

    Args:
        text: What the writer returned.

    Returns:
        The text with each bare id written as arXiv:<id>.
    """
    return BARE.sub(r"arXiv:\1", text)


def linkify(text: str) -> str:
    """
    Every citation as one markdown link, whatever brackets the writer put around it

    Applied once on the way out, so the draft the writer works on stays plain.

    Args:
        text: The draft.

    Returns:
        The text with every mention linked.
    """
    out: list[str] = []
    last = 0
    for found in LINKABLE.finditer(text):
        if found.end() < len(text) and text[found.end()] == "(":
            continue
        arxiv_id = found.group(1)
        before = text[last : found.start()]
        out.append(before)
        if before and not before[-1].isspace() and found.group(0)[0] in " ([":
            out.append(" ")
        out.append(f"[arXiv:{arxiv_id}](https://arxiv.org/abs/{arxiv_id})")
        last = found.end()
    out.append(text[last:])
    return "".join(out)


def check(dsn: CorpusSource, text: str, allowed: set[str]) -> Grounded:
    """
    Corrects the typos, keeps what exists and cuts what does not

    Args:
        dsn: A libpq connection string or corpus adapter.
        text: The draft.
        allowed: The ids the writer was given.

    Returns:
        The clean draft and the account of what changed.
    """
    lower = {a.lower(): a for a in allowed}
    fixed: dict[str, str] = {}
    for bad in sorted(read_ids(text) - set(lower)):
        good = nearest(bad, lower)
        if good is None:
            continue
        fixed[bad] = good
        text = re.sub(re.escape(bad), good, text, flags=re.IGNORECASE)

    found = read_ids(text)
    held = sorted(found & set(lower))
    off = sorted(found - set(lower))
    real = exist(dsn, off)
    cut = sorted(a for a in off if a not in real)
    if cut:
        text = strip(text, set(cut))
    if fixed or cut:
        LOG.info("grounding corrected %d and cut %d", len(fixed), len(cut))
    return Grounded(text, held, sorted(a for a in off if a in real), fixed, cut)
