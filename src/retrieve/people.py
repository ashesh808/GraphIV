"""
One person's papers out of everyone who shares their name, and those papers grouped by topic

arXiv has no author id, so a known paper spreads over shared coauthors and shared references
A common name still floods through coauthors whose own names collide, which only an id would fix
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import psycopg

CANDIDATES = """
SELECT arxiv_id, authors FROM papers
WHERE %s = ANY(surnames) AND authors ILIKE %s AND stage >= 3
"""
REFERENCES = """
SELECT DISTINCT source_id, target_id FROM citations
WHERE source_id = ANY(%s) AND target_id IS NOT NULL
"""
TOPICS = "SELECT arxiv_id, level_0, level_1 FROM topic_tree WHERE arxiv_id = ANY(%s) AND stage = 1"
TOPIC_NAMES = """
SELECT level_0, level_1, name FROM topic_names WHERE level_2 IS NULL AND level_1 IS NOT NULL
"""

SPLIT = re.compile(r",\s*|\s+and\s+")
# a paper sharing nothing with what is known stays near 0.05
PRIOR = -3.0
KNOWN = 6.0
# one shared coauthor alone is not enough and two are
COAUTHOR = 2.0
# per log1p of shared references, so about seven of them count as one coauthor
REFERENCE = 0.5
ROUNDS = 5
# only the strongest few links count, so thousands of weak ones under a common name cannot add up
LINKS = 3
THRESHOLD = 0.5
UNPLACED = (-1, -1)


@dataclass(frozen=True)
class Person:
    """
    One author as the caller names them, with the papers that say which of the namesakes is meant
    """

    name: str
    known: tuple[str, ...]


@dataclass
class Found:
    """
    What one person's name matched and what the propagation kept
    """

    person: Person
    candidates: int
    kept: list[str] = field(default_factory=list)


def as_people(raw: list[dict[str, object]] | None) -> list[Person]:
    """
    The people a tool call names, each needing a name and at least one known paper

    Args:
        raw: Each entry as {"name": ..., "known": [...]}.

    Returns:
        The people.

    Raises:
        ValueError: When an entry has no name or no known paper.
    """
    out: list[Person] = []
    for entry in raw or []:
        name = " ".join(str(entry.get("name", "")).split())
        given = entry.get("known", [])
        known = tuple(str(k).strip() for k in (given if isinstance(given, list) else [given]))
        known = tuple(k for k in known if k)
        if not name or not known:
            raise ValueError(f"each person needs a name and at least one known arxiv id: {entry}")
        out.append(Person(name, known))
    return out


def authors(listed: str) -> list[str]:
    """
    The names on one paper, whitespace normalized

    Args:
        listed: The authors column as arXiv writes it.

    Returns:
        One name per author.
    """
    return [" ".join(a.split()) for a in SPLIT.split(listed or "") if a.strip()]


def shared(items: dict[str, set[str]]) -> dict[str, Counter[str]]:
    """
    For every paper, how many items it shares with every other paper

    Args:
        items: The coauthors or the references of each paper.

    Returns:
        Paper to the count it shares with each other paper.
    """
    index: dict[str, list[str]] = defaultdict(list)
    for paper, held in items.items():
        for item in held:
            index[item].append(paper)
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for papers in index.values():
        for p in papers:
            for q in papers:
                if p != q:
                    out[p][q] += 1
    return out


def propagate(
    coauthors: dict[str, set[str]], references: dict[str, set[str]], known: set[str]
) -> dict[str, float]:
    """
    The probability that each paper is the known papers' author's, spread out from the known ones

    Each round a paper's logit is the prior plus its strongest links, each a shared coauthor and
    shared reference weight times how sure the paper on the other end already is.

    Args:
        coauthors: Each candidate's coauthors, the name itself left out.
        references: Each candidate's resolved references.
        known: The papers fixed as theirs.

    Returns:
        Paper to probability, for every candidate.
    """
    ids = list(coauthors)
    co, ref = shared(coauthors), shared(references)
    links: dict[str, dict[str, float]] = {}
    for p in ids:
        links[p] = {
            q: COAUTHOR * co[p][q] + REFERENCE * math.log1p(ref[p][q])
            for q in set(co[p]) | set(ref[p])
        }
    prob = {p: 1.0 if p in known else sigmoid(PRIOR) for p in ids}
    for _ in range(ROUNDS):
        prob = {
            p: (
                1.0
                if p in known
                else sigmoid(
                    PRIOR
                    + sum(sorted((prob[q] * w for q, w in links[p].items()), reverse=True)[:LINKS])
                )
            )
            for p in ids
        }
    return prob


def sigmoid(logit: float) -> float:
    """
    A logit as a probability, clamped so a large one cannot overflow

    Args:
        logit: The log odds.

    Returns:
        The probability.
    """
    return 1.0 / (1.0 + math.exp(-min(max(logit, -30.0), 30.0)))


def find(dsn: str, person: Person) -> Found:
    """
    One person's papers, every paper listing the name kept where the propagation clears the bar

    Args:
        dsn: libpq connection string.
        person: Who.

    Returns:
        How many papers the name matched and which were kept, newest id order kept by the store.
    """
    surname = person.name.split()[-1]
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(CANDIDATES, (surname, f"%{person.name}%")).fetchall()
        coauthors = {
            str(a): {x for x in authors(str(s)) if x != person.name}
            for a, s in rows
            if person.name in authors(str(s))
        }
        references: dict[str, set[str]] = defaultdict(set)
        for source, target in conn.execute(REFERENCES, (list(coauthors),)):
            references[str(source)].add(str(target))
    known = {k for k in person.known if k in coauthors}
    if not known:
        return Found(person, len(coauthors))
    prob = propagate(coauthors, references, known)
    return Found(person, len(coauthors), [p for p in coauthors if prob[p] >= THRESHOLD])


def topics(dsn: str, arxiv_ids: list[str]) -> dict[tuple[int, int], list[str]]:
    """
    Papers grouped by their parent topic in the tree, the unplaced ones under one key of their own

    Args:
        dsn: libpq connection string.
        arxiv_ids: The papers.

    Returns:
        (level_0, level_1) to the papers under it, in the order given.
    """
    with psycopg.connect(dsn) as conn:
        placed = {str(a): (int(l0), int(l1)) for a, l0, l1 in conn.execute(TOPICS, (arxiv_ids,))}
    return group(arxiv_ids, placed)


def group(
    arxiv_ids: list[str], placed: dict[str, tuple[int, int]]
) -> dict[tuple[int, int], list[str]]:
    """
    Papers grouped by topic key

    Args:
        arxiv_ids: The papers.
        placed: Each paper's topic key, missing for one the tree has not placed.

    Returns:
        Topic key to its papers, in the order given.
    """
    out: dict[tuple[int, int], list[str]] = defaultdict(list)
    for a in arxiv_ids:
        out[placed.get(a, UNPLACED)].append(a)
    return dict(out)


def topic_names(dsn: str) -> dict[tuple[int, int], str]:
    """
    The tree's own name for every parent topic

    Args:
        dsn: libpq connection string.

    Returns:
        (level_0, level_1) to its name.
    """
    with psycopg.connect(dsn) as conn:
        return {(int(a), int(b)): str(n) for a, b, n in conn.execute(TOPIC_NAMES)}


def best_topic(
    groups: dict[tuple[int, int], list[str]], cosines: dict[str, float]
) -> tuple[int, int] | None:
    """
    The topic whose papers sit closest to a question on average

    Args:
        groups: Topic key to its papers.
        cosines: Each paper's cosine to the question.

    Returns:
        The key, or None when no paper has a cosine.
    """
    means = {
        key: sum(cosines[a] for a in papers if a in cosines) / n
        for key, papers in groups.items()
        if (n := sum(1 for a in papers if a in cosines))
    }
    return max(means, key=lambda k: means[k]) if means else None
