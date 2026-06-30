"""Canonical adjacency-list digest — the exp-17 winner: node table + intent-grouped adjacency.

The representation experiments converged on this: a NODES table (id, year, optional role, title ::
content) + an ADJACENCY block (each paper -> the papers it cites, grouped by citation intent). It
beat flat lists / DOT / JSON / matrix on quality and tokens (exp-17). This is the single canonical
builder; `content` (extracted fields / abstract / vision read), `roles`, and `alias` naming are
parameters, replacing the ~6 copy-pasted `adj_encode` variants from this session's scratchpads.
"""

from __future__ import annotations

from collections import defaultdict

# force the sys.path bootstrap before importing phase-6 types by bare name
from ._boot import REPO as _REPO  # noqa: F401

from subgraph import Edge, Landmark  # noqa: E402


def adjacency_digest(
    landmarks: list[Landmark],
    edges: list[Edge],
    content: dict[str, str],
    *,
    roles: dict[str, str] | None = None,
    alias: bool = False,
) -> str:
    """node table (+ optional role tag) + per-paper out-adjacency grouped by intent.

    `content[arxiv_id]` is the per-node text (extracted fields or abstract). `roles[arxiv_id]` tags
    foundational/core/frontier/peripheral. `alias=True` labels nodes `[D1]..` (cheap-token variant)
    with an id table — the model still cites the arXiv id.
    """
    nodes = sorted(landmarks, key=lambda lm: (lm.year or 0, lm.arxiv_id))
    ids = {lm.arxiv_id for lm in nodes}
    al = {lm.arxiv_id: f"D{i + 1}" for i, lm in enumerate(nodes)}

    def ref(a: str) -> str:
        return al[a] if alias else f"arXiv:{a}"

    out: list[str] = ["NODES:"]
    for lm in nodes:
        a = lm.arxiv_id
        yr = lm.year if lm.year is not None else "?"
        role = f" [{roles[a]}]" if roles and roles.get(a) else ""
        idp = f"{al[a]} = arXiv:{a}" if alias else f"arXiv:{a}"
        out.append(f'{idp} ({yr}){role} "{lm.title}" :: {(content.get(a) or "")}')
    out += ["", "ADJACENCY (each paper -> papers it cites, grouped by intent):"]
    for lm in nodes:
        a = lm.arxiv_id
        grp: dict[str, list[str]] = defaultdict(list)
        for e in edges:
            if e.src == a and e.dst in ids:
                grp[e.intent or "cites"].append(ref(e.dst))
        parts = [f"{k}[{', '.join(v)}]" for k, v in grp.items()]
        out.append(f"{ref(a)}: {' '.join(parts) or '(no out-citations in-graph)'}")
    return "\n".join(out)
