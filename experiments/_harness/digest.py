"""
The canonical digest: a node table plus an adjacency block grouped by citation intent

The representation experiments converged on this shape over flat lists, DOT, JSON and a matrix
It won on quality and on tokens, which is why the production digest is built the same way
"""

from __future__ import annotations

from collections import defaultdict

from graphiv.core.models import Edge, Landmark


def adjacency_digest(
    landmarks: list[Landmark],
    edges: list[Edge],
    content: dict[str, str],
    *,
    roles: dict[str, str] | None = None,
    alias: bool = False,
) -> str:
    """
    node table (+ optional role tag) + per-paper out-adjacency grouped by intent

        content holds the per-node text, either extracted fields or the abstract
        roles tags each node, and alias labels them [D1].. for the cheap-token variant
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
