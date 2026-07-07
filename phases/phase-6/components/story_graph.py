"""Story graph: the narrative skeleton drawn from the intent-typed citation subgraph.

Generalizes the single `main_path` spine into a story object the writer, the digest, and the
visualization all consume: *threads* (chronological extends/uses lineage chains running
foundation -> frontier), *tensions* (compares/critiques edges, computed upstream), *motivations*
(motivates edges among landmarks), and *connectors* — non-landmark pool papers sitting on 1-2
intermediate-hop citation paths between landmarks. Connectors stay graph context (viz + one-line
digest mentions), never writer content.
"""

from __future__ import annotations

from dataclasses import dataclass

from subgraph import Edge, Landmark, PoolNode

THREAD_INTENTS: frozenset[str] = frozenset({"extends", "uses"})
MAX_THREADS = 5
MIN_THREAD_LEN = 3
MAX_CONNECTORS = 40


@dataclass
class Story:
    threads: list[list[str]]  # each oldest -> newest landmark ids
    tensions: list[Edge]
    motivations: list[Edge]
    connectors: list[str]  # non-landmark pool ids bridging landmarks


def _lineage_succ(landmarks: list[Landmark], edges: list[Edge]) -> dict[str, list[str]]:
    """older -> newer adjacency over landmark extends/uses edges (year-ordered DAG)."""
    lm_year = {lm.arxiv_id: lm.year for lm in landmarks if lm.year is not None}
    succ: dict[str, list[str]] = {i: [] for i in lm_year}
    for e in edges:
        if e.intent not in THREAD_INTENTS:
            continue
        ys, yd = lm_year.get(e.src), lm_year.get(e.dst)
        if ys is None or yd is None or yd >= ys:
            continue
        succ[e.dst].append(e.src)  # dst older: chronological step dst -> src
    return succ


def _longest_chain(
    order: list[str], succ: dict[str, list[str]], alive: set[str]
) -> list[str]:
    """Longest chronological path over the still-alive nodes (same DP as main_path)."""
    best_len: dict[str, int] = {i: 1 for i in alive}
    best_next: dict[str, str | None] = {i: None for i in alive}
    for node in reversed(order):
        if node not in alive:
            continue
        for nxt in succ.get(node, []):
            if nxt in alive and best_len[nxt] + 1 > best_len[node]:
                best_len[node] = best_len[nxt] + 1
                best_next[node] = nxt
    if not best_len:
        return []
    start = max(best_len, key=lambda i: best_len[i])
    chain: list[str] = []
    cur: str | None = start
    while cur is not None:
        chain.append(cur)
        cur = best_next[cur]
    return chain


def threads(landmarks: list[Landmark], edges: list[Edge]) -> list[list[str]]:
    """Up to MAX_THREADS node-disjoint lineage chains (extends/uses), longest first."""
    lm_year = {lm.arxiv_id: lm.year for lm in landmarks if lm.year is not None}
    succ = _lineage_succ(landmarks, edges)
    order = sorted(lm_year, key=lambda i: lm_year[i] or 0)
    alive = set(lm_year)
    out: list[list[str]] = []
    while len(out) < MAX_THREADS:
        chain = _longest_chain(order, succ, alive)
        if len(chain) < MIN_THREAD_LEN:
            break
        out.append(chain)
        alive -= set(chain)
    return out


def motivations(landmarks: list[Landmark], edges: list[Edge]) -> list[Edge]:
    lm_ids = {lm.arxiv_id for lm in landmarks}
    return [
        e
        for e in edges
        if e.intent == "motivates" and e.src in lm_ids and e.dst in lm_ids
    ]


def connectors(
    landmarks: list[Landmark],
    edges: list[Edge],
    pool: dict[str, PoolNode],
    max_out: int = MAX_CONNECTORS,
) -> list[str]:
    """Non-landmark pool papers on landmark->...->landmark paths with 1-2 intermediates.

    1 intermediate: L -> X -> L'. 2 intermediates: L -> X -> Y -> L'. Ranked by cosine score
    so the viz shows the most on-topic bridges first.
    """
    lm_ids = {lm.arxiv_id for lm in landmarks}
    cited_by_lm: set[str] = set()  # X with some L -> X
    cites_lm: set[str] = set()  # X with some X -> L
    for e in edges:
        if e.src in lm_ids and e.dst not in lm_ids:
            cited_by_lm.add(e.dst)
        if e.dst in lm_ids and e.src not in lm_ids:
            cites_lm.add(e.src)
    found: set[str] = cited_by_lm & cites_lm  # 1 intermediate
    for e in edges:  # 2 intermediates: X -> Y with L -> X and Y -> L'
        if (
            e.src in cited_by_lm
            and e.dst in cites_lm
            and e.src not in lm_ids
            and e.dst not in lm_ids
        ):
            found.add(e.src)
            found.add(e.dst)
    ranked = sorted((a for a in found if a in pool), key=lambda a: -pool[a].score)
    return ranked[:max_out]


def build_story(
    landmarks: list[Landmark],
    edges: list[Edge],
    tens: list[Edge],
    pool: dict[str, PoolNode],
) -> Story:
    return Story(
        threads=threads(landmarks, edges),
        tensions=tens,
        motivations=motivations(landmarks, edges),
        connectors=connectors(landmarks, edges, pool),
    )


def story_digest_block(
    story: Story, by_id: dict[str, Landmark], pool: dict[str, PoolNode]
) -> str:
    """The story section appended to the digest: threads with titles, connector one-liners."""
    parts: list[str] = ["STORY THREADS (lineage chains, oldest -> newest):"]
    if story.threads:
        for i, chain in enumerate(story.threads, 1):
            steps = " -> ".join(
                f"arXiv:{a} ({by_id[a].year})" for a in chain if a in by_id
            )
            parts.append(f"  [T{i}] {steps}")
            for a in chain:
                if a in by_id:
                    parts.append(f'       arXiv:{a} "{by_id[a].title[:80]}"')
    else:
        parts.append("  (no dominant lineage chains)")
    if story.motivations:
        parts.append("MOTIVATION LINKS (problem-framing):")
        for e in story.motivations[:10]:
            parts.append(f"  arXiv:{e.src} motivated-by arXiv:{e.dst}")
    if story.connectors:
        parts.append(
            "CONNECTORS (bridge papers between landmarks; context only, do NOT analyze):"
        )
        for a in story.connectors[:15]:
            n = pool.get(a)
            if n is not None:
                parts.append(f'  arXiv:{a} ({n.year or "?"}) "{n.title[:80]}"')
    return "\n".join(parts)
