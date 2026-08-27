"""
Readers: the stage that assigns a role and a relevance, or declines to

Only LlmReader needs an endpoint, so the others make an LLM-free path a configuration
A reader never silently degrades, since a run missing its reader must fail rather than score low
"""

from __future__ import annotations

import asyncio
import hashlib

from graphiv.core.settings import PG_DSN
from graphiv.core.store import Store
from graphiv.retrieve.api import Pool, Query
from graphiv.retrieve.grade import Grade, candidates, grade_many


def _in_degree(pool: Pool) -> dict[str, int]:
    d: dict[str, int] = {}
    for e in pool.edges:
        d[e.dst] = d.get(e.dst, 0) + 1
    return d


def _shortlist(q: Query, pool: Pool) -> list[str]:
    return candidates(pool.nodes, _in_degree(pool), q.budget)


class NullReader:
    """
    Grades nothing, so every downstream signal is graph or text only
    """

    name = "null"

    def grade(self, q: Query, pool: Pool) -> dict[str, Grade]:
        """
        An empty verdict set
        """
        _ = (q, pool)
        return {}


class ConstantReader:
    """
    Gives every candidate the same verdict, which neutralises the reader without removing it

        Fusion still runs and nothing is evicted, so this isolates what the graph does alone.
    """

    name = "constant"

    def __init__(self, relevance: int = 1, role: str = "core") -> None:
        self.relevance = relevance
        self.role = role

    def grade(self, q: Query, pool: Pool) -> dict[str, Grade]:
        """
        One identical verdict per shortlisted candidate
        """
        return {a: Grade(self.role, self.relevance, "constant reader") for a in _shortlist(q, pool)}


class GoldReader:
    """
    Grades from an answer key, which measures what a perfect reader would be worth

        Evaluation only.
        Passing this an answer key at serve time would leak the thing being measured.
    """

    name = "gold"

    def __init__(self, gold: dict[str, set[str]]) -> None:
        self.gold = gold

    def grade(self, q: Query, pool: Pool) -> dict[str, Grade]:
        """
        Relevance 2 for a paper in the key, -2 for anything else on the shortlist
        """
        keep = self.gold.get(q.text, set())
        return {
            a: (
                Grade("core", 2, "in the answer key")
                if a in keep
                else Grade("unrelated", -2, "not in the answer key")
            )
            for a in _shortlist(q, pool)
        }


class LlmReader:
    """
    The production reader, cache-first and keyed by the question hash
    """

    name = "llm"

    def grade(self, q: Query, pool: Pool) -> dict[str, Grade]:
        """
        Role and relevance per shortlisted candidate, reading the cache before the endpoint
        """
        cand = _shortlist(q, pool)
        if not cand:
            return {}
        qhash = hashlib.sha1(q.text.encode()).hexdigest()[:12]
        store = Store(PG_DSN, max_yymm=q.max_yymm, exclude=q.exclude)
        try:
            abstracts = store.abstracts(cand)
        finally:
            store.close()
        return asyncio.run(grade_many(q.text, qhash, pool.nodes, cand, abstracts))


READERS: dict[str, type[NullReader] | type[ConstantReader] | type[LlmReader]] = {
    "null": NullReader,
    "constant": ConstantReader,
    "llm": LlmReader,
}
