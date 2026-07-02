"""Steps 2-4 of the narrative layer: turn a query vector into a bounded,
on-topic citation subgraph with landmarks, eras, a main path, and tensions.

The hub-explosion trap (ResNet/Adam have 100k citers) is avoided by inducing the
subgraph *within* a similarity-ranked topical pool rather than expanding outward
from seeds: the citation structure inside the on-topic cloud is automatically
relevant and bounded.

No LLM and no embedding model here — callers pass a pre-computed query vector
(so VRAM can be sequenced: embed -> free_model -> load narrator).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from store import Store

# Strongest-signal-first; used to collapse parallel edges to one intent and to
# pick the "tension" edges. extends/uses = builds-on; compares/critiques/motivates
# = limitation/problem-framing; background = weakest.
INTENT_PRIORITY: list[str] = [
    "extends",
    "uses",
    "compares",
    "critiques",
    "motivates",
    "background",
]
_INTENT_RANK: dict[str, int] = {name: i for i, name in enumerate(INTENT_PRIORITY)}
TENSION_INTENTS: frozenset[str] = frozenset({"compares", "critiques", "motivates"})


@dataclass
class PoolNode:
    arxiv_id: str
    title: str
    year: int | None
    category: str | None
    score: float  # cosine sim to the query


@dataclass
class Edge:
    src: str  # citing (newer) -> dst cited (older)
    dst: str
    intent: str | None
    polarity: str | None


@dataclass
class Landmark:
    arxiv_id: str
    title: str
    year: int | None
    category: str | None
    score: float
    in_degree: int  # # of distinct pool papers citing this one
    era: int = -1  # filled by assign_eras


@dataclass
class Era:
    index: int
    label: str
    year_lo: int
    year_hi: int


# ---------------------------------------------------------------------------
# Step 2 — topical pool (vector)


def topical_pool(store: Store, qvec: list[float], n_pool: int) -> dict[str, PoolNode]:
    """Top-`n_pool` papers by cosine sim to the query, keyed by arxiv_id."""
    return store.vector_pool(qvec, n_pool)


# ---------------------------------------------------------------------------
# Step 2b — backward-ancestor augmentation (graph)
#
# The similarity pool is dominated by recent application/survey papers; the
# FOUNDATIONAL lineage (e.g. DDPM, LDM, score-SDE for diffusion) is cited by
# nearly the whole pool yet is rarely a top-N embedding neighbour of the query.
# We pull those most-cited ancestors in — bounded (one hop back, ranked by # of
# distinct pool citers) — so "Origins" and the main-path spine actually exist.


def augment_with_ancestors(
    store: Store,
    pool: dict[str, PoolNode],
    qvec: list[float],
    max_add: int = 150,
    min_citers: int = 3,
    category_prefix: str | None = None,
    min_cosine: float = 0.0,
) -> int:
    """Add the pool's most-cited ancestors to `pool` (mutates). Returns # added.

    Ranked by how many distinct pool papers cite each ancestor; scored by true cosine sim to the
    query. If `category_prefix` is given, only ancestors in that arXiv category group are added
    (prevents famous cross-field papers from hijacking a polysemous query's pool). `min_cosine`
    gates the injection: fame ranks the candidates, so without a floor famous cross-field hubs
    enter regardless of relevance (02-03: 0.35 is Pareto, on a 0.25-0.35 recall plateau).
    """
    if not pool:
        return 0
    added = 0
    for n in store.ancestors(list(pool), qvec, max_add, min_citers, category_prefix):
        if n.arxiv_id in pool or n.score < min_cosine:
            continue
        pool[n.arxiv_id] = n
        added += 1
    return added


# ---------------------------------------------------------------------------
# Step 3 — induce the citation subgraph (graph)


def induce_subgraph(store: Store, pool_ids: list[str]) -> list[Edge]:
    """All CITES edges with both endpoints in the pool, parallel edges collapsed.

    Multiple (src,dst) citation occurrences collapse to one edge carrying the
    strongest-signal intent (INTENT_PRIORITY) and that edge's polarity.
    """
    best: dict[tuple[str, str], Edge] = {}
    for src, dst, intent_raw, polarity_raw in store.edges_among(pool_ids):
        if src == dst:
            continue
        intent = str(intent_raw) if intent_raw is not None else None
        polarity = str(polarity_raw) if polarity_raw is not None else None
        key = (src, dst)
        prev = best.get(key)
        if prev is None or _intent_rank(intent) < _intent_rank(prev.intent):
            best[key] = Edge(src=src, dst=dst, intent=intent, polarity=polarity)
    return list(best.values())


def _intent_rank(intent: str | None) -> int:
    """Lower = stronger signal; unknown intents sort last."""
    if intent is None:
        return len(INTENT_PRIORITY)
    return _INTENT_RANK.get(intent, len(INTENT_PRIORITY))


# ---------------------------------------------------------------------------
# Step 4 — rank + structure (Python, no GDS)


def rank_landmarks(
    pool: dict[str, PoolNode], edges: list[Edge], m: int
) -> list[Landmark]:
    """Top-`m` by within-pool in-degree (primary), sim-to-query (tiebreak)."""
    in_degree: dict[str, int] = {}
    for e in edges:
        in_degree[e.dst] = in_degree.get(e.dst, 0) + 1
    landmarks = [
        Landmark(
            arxiv_id=n.arxiv_id,
            title=n.title,
            year=n.year,
            category=n.category,
            score=n.score,
            in_degree=in_degree.get(n.arxiv_id, 0),
        )
        for n in pool.values()
    ]
    landmarks.sort(key=lambda lm: (lm.in_degree, lm.score), reverse=True)
    return landmarks[:m]


def assign_eras(landmarks: list[Landmark], n_eras: int = 3) -> list[Era]:
    """Bucket landmarks into year tertiles; sets `era` on each, returns Era meta.

    Mutates `landmarks` in place (fills `.era`). Landmarks with no year go to the
    first era so they still appear at the origins end.
    """
    labels = ["Origins", "Key Advances", "Current Frontier"]
    years = [lm.year for lm in landmarks if lm.year is not None]
    if not years:
        for lm in landmarks:
            lm.era = 0
        return [Era(index=0, label=labels[0], year_lo=0, year_hi=0)]
    lo, hi = min(years), max(years)
    span = max(1, hi - lo)
    bounds = [lo + round(span * i / n_eras) for i in range(n_eras + 1)]
    for lm in landmarks:
        y = lm.year if lm.year is not None else lo
        idx = n_eras - 1
        for i in range(n_eras):
            if y <= bounds[i + 1]:
                idx = i
                break
        lm.era = idx
    return [
        Era(
            index=i,
            label=labels[i] if i < len(labels) else f"Era {i}",
            year_lo=bounds[i],
            year_hi=bounds[i + 1],
        )
        for i in range(n_eras)
    ]


def main_path(landmarks: list[Landmark], edges: list[Edge]) -> list[str]:
    """Longest chronological citation chain among landmarks (oldest -> newest).

    Citation edges run newer(src) -> older(dst); reverse them to older -> newer
    and DP a longest path over the resulting year-ordered DAG. Edges between
    same-year or year-unknown papers are dropped (ambiguous direction).
    """
    lm_year: dict[str, int] = {
        lm.arxiv_id: lm.year for lm in landmarks if lm.year is not None
    }
    lm_ids = set(lm_year)
    # older -> newer adjacency
    succ: dict[str, list[str]] = {i: [] for i in lm_ids}
    for e in edges:
        if e.src not in lm_ids or e.dst not in lm_ids:
            continue
        ys, yd = lm_year[e.src], lm_year[e.dst]
        if yd < ys:  # dst older than src: chronological step dst -> src
            succ[e.dst].append(e.src)
    order = sorted(lm_ids, key=lambda i: lm_year[i])
    best_len: dict[str, int] = {i: 1 for i in lm_ids}
    best_next: dict[str, str | None] = {i: None for i in lm_ids}
    # process newest-first so successors are already solved
    for node in reversed(order):
        for nxt in succ[node]:
            if best_len[nxt] + 1 > best_len[node]:
                best_len[node] = best_len[nxt] + 1
                best_next[node] = nxt
    if not best_len:
        return []
    start = max(order, key=lambda i: best_len[i])
    chain: list[str] = []
    cur: str | None = start
    while cur is not None:
        chain.append(cur)
        cur = best_next[cur]
    return chain


def tensions(
    landmarks: list[Landmark], edges: list[Edge], sim_floor_frac: float = 0.5
) -> list[Edge]:
    """Edges among landmarks whose intent signals a comparison/critique/limitation.

    Both endpoints must be reasonably on-topic (sim >= `sim_floor_frac` * the best
    landmark sim) — otherwise an off-topic cluster pulled in via citation adjacency
    (e.g. a string-theory critique edge under a condensed-matter query) can hijack
    the section. Negative-polarity ones first (the sharpest open problems).
    """
    score = {lm.arxiv_id: lm.score for lm in landmarks}
    if not score:
        return []
    floor = sim_floor_frac * max(score.values())
    out = [
        e
        for e in edges
        if e.intent in TENSION_INTENTS
        and score.get(e.src, -1.0) >= floor
        and score.get(e.dst, -1.0) >= floor
    ]
    out.sort(key=lambda e: (e.polarity != "negative", _intent_rank(e.intent)))
    return out
