"""
Draw evaluation samples from an already-labeled store

The gold source is the human gold_label table in Postgres, the teacher source is labels.db
Both draws are seed-deterministic, so a refine run is reproducible from its seed alone
"""

from __future__ import annotations

import random
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import cast

import psycopg

from ._common import ARXIVKG_PG_DSN, INTENTS, LABELS_DB

# the relational classes the review's tensions are built from, thin next to background and uses
RARE_INTENTS: tuple[str, ...] = ("extends", "compares", "critiques", "motivates")

SOURCES: tuple[str, ...] = ("gold", "teacher")


@dataclass(frozen=True)
class Sample:
    """
    One labeled citation occurrence, with the text a labeler is shown
    """

    citing_id: int
    ordinal: int
    section: str
    sentence: str
    intent: str


def _from_gold() -> list[Sample]:
    """
    Every human-labeled occurrence, joined to its sentence
    """
    sql = (
        "SELECT g.citing_id, g.ordinal, COALESCE(c.section,''), c.sentence, g.intent "
        "FROM gold_label g JOIN citation c "
        "ON c.citing_id = g.citing_id AND c.ordinal = g.ordinal "
        "WHERE c.sentence IS NOT NULL AND g.intent IS NOT NULL"
    )
    with psycopg.connect(ARXIVKG_PG_DSN) as conn:
        rows = cast(list[tuple[int, int, str, str, str]], conn.execute(sql).fetchall())
    return [Sample(*r) for r in rows]


def _from_teacher() -> list[Sample]:
    """
    Every teacher-labeled occurrence that parsed, joined to its sentence
    """
    with sqlite3.connect(f"file:{LABELS_DB}?mode=ro", uri=True) as db:
        labeled = cast(
            list[tuple[int, int, str]],
            db.execute(
                "SELECT citing_id, ordinal, intent FROM label "
                "WHERE ok = 1 AND intent IS NOT NULL"
            ).fetchall(),
        )
    by_key = {(cid, ordn): intent for cid, ordn, intent in labeled}
    if not by_key:
        return []
    out: list[Sample] = []
    keys = list(by_key)
    with psycopg.connect(ARXIVKG_PG_DSN) as conn:
        for start in range(0, len(keys), 5000):
            chunk = keys[start : start + 5000]
            values = ",".join("(%s,%s)" for _ in chunk)
            params: list[int] = [v for pair in chunk for v in pair]
            sql = (
                "SELECT c.citing_id, c.ordinal, COALESCE(c.section,''), c.sentence "
                f"FROM citation c JOIN (VALUES {values}) AS v(cid, ord) "
                "ON c.citing_id = v.cid AND c.ordinal = v.ord "
                "WHERE c.sentence IS NOT NULL"
            )
            rows = cast(list[tuple[int, int, str, str]], conn.execute(sql, params).fetchall())
            for cid, ordn, section, sentence in rows:
                out.append(Sample(cid, ordn, section, sentence, by_key[(cid, ordn)]))
    return out


def load(source: str = "gold") -> list[Sample]:
    """
    Read every labeled occurrence from one source
    """
    if source not in SOURCES:
        raise ValueError(f"unknown source '{source}', expected one of {SOURCES}")
    return _from_gold() if source == "gold" else _from_teacher()


def _by_intent(pool: list[Sample]) -> dict[str, list[Sample]]:
    """
    Group a pool by its intent label
    """
    out: dict[str, list[Sample]] = defaultdict(list)
    for s in pool:
        out[s.intent].append(s)
    return out


def _draw(pool: list[Sample], classes: tuple[str, ...], n: int, seed: int) -> list[Sample]:
    """
    Take an equal share of each class, then top up from the largest classes
    """
    rng = random.Random(seed)
    groups = _by_intent(pool)
    share = max(1, n // max(1, len(classes)))
    picked: list[Sample] = []
    for intent in classes:
        rows = sorted(groups.get(intent, []), key=lambda s: (s.citing_id, s.ordinal))
        rng.shuffle(rows)
        picked.extend(rows[:share])
    if len(picked) < n:
        chosen = {(s.citing_id, s.ordinal) for s in picked}
        rest = [s for s in pool if s.intent in classes and (s.citing_id, s.ordinal) not in chosen]
        rest.sort(key=lambda s: (s.citing_id, s.ordinal))
        rng.shuffle(rest)
        picked.extend(rest[: n - len(picked)])
    rng.shuffle(picked)
    return picked[:n]


def label_stratified(n: int = 300, source: str = "gold", seed: int = 0) -> list[Sample]:
    """
    An equal-per-intent draw across all six classes
    """
    return _draw(load(source), INTENTS, n, seed)


def label_rare(n: int = 200, source: str = "gold", seed: int = 0) -> list[Sample]:
    """
    An equal-per-intent draw restricted to the four relational classes
    """
    return _draw(load(source), RARE_INTENTS, n, seed)
