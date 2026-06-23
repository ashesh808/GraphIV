"""experiment-3 — citation-graph structure, computed from the single Postgres store.

Pure-SQL aggregations + themed figures (no LLM). Idempotent: caches results/summary.json and
reuses it on re-run, repopulating README.md + metrics.md. Pass --force to recompute from the DB.

    uv run python experiments/experiment-3-graph-structure/run.py [--force]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "code"))

from analyze import compute, figures  # noqa: E402

RESULTS = _HERE / "results"


def _counts_table(s: dict[str, Any]) -> str:
    rows = [
        ("papers (nodes)", s["n_papers"]),
        ("citation occurrences", s["n_citations"]),
        ("resolved occurrences", s["n_resolved"]),
        ("distinct edges", s["n_edges"]),
    ]
    body = "\n".join(f"| {k} | {v:,} |" for k, v in rows)
    res_pct = 100.0 * s["n_resolved"] / max(1, s["n_citations"])
    return (
        f"| metric | value |\n|---|--:|\n{body}\n\n*Resolution rate: {res_pct:.1f}%.*"
    )


def _top_cited_table(s: dict[str, Any]) -> str:
    head = "| rank | in-deg | year | arXiv | title |\n|--:|--:|--:|---|---|"
    lines = [
        f"| {i + 1} | {n:,} | {y or ''} | {a} | {t} |"
        for i, (a, n, t, y) in enumerate(s["top_cited"])
    ]
    return head + "\n" + "\n".join(lines)


def _readme(s: dict[str, Any], figs: list[str]) -> str:
    _ = figs  # figures are embedded inline by section below
    return f"""# Experiment 3 — Citation-graph structure

**What:** the shape of the 68.9M-edge intent-typed citation graph, read straight from the single
Postgres+pgvector store (`./data/pg`). Pure SQL + matplotlib, no LLM. **Why:** characterizes the
substrate phase-6 retrieves over — scale-free degree structure, the intent/polarity typing that
edges carry, and how citation activity grows over time.

**Reproduce:** `uv run python experiments/experiment-3-graph-structure/run.py` (idempotent; caches
`results/summary.json`, `--force` to recompute).

## Global counts

{_counts_table(s)}

## Degree distributions

Both in- and out-degree are heavy-tailed (near scale-free) — a few papers accrue enormous
in-degree while most are cited rarely; this is exactly the hub structure phase-6's pool induction
avoids by ranking *within* an on-topic pool rather than expanding from hubs.

![indegree](results/indegree_loglog.png)

![outdegree](results/outdegree_loglog.png)

## Edge typing (the differentiator)

Every resolved edge carries an intent + polarity (DistilBERT student over the corpus). The mix is
dominated by `background`/`uses`; the rare relational intents (`compares`/`critiques`/`motivates`)
are what feed phase-6's "tensions"/open-problems surfacing.

![intent](results/intent_mix.png)

![polarity](results/polarity_mix.png)

## Citation activity over time

![per_year](results/per_year.png)

## Top-cited papers (within-corpus in-degree)

{_top_cited_table(s)}

## Caveats

In-degree here is *within-corpus* (arXiv→arXiv resolved citations only); true citation counts are
higher. Unresolved occurrences (no `cited_id`) are excluded from the graph but retained in the
store for the resolver analysis (experiment-1).
"""


def main() -> None:
    force = "--force" in sys.argv[1:]
    RESULTS.mkdir(parents=True, exist_ok=True)
    print(
        "[exp3] computing graph-structure stats (cached unless --force) ...", flush=True
    )
    stats = compute(RESULTS, force)
    figs = figures(stats, RESULTS)
    _ = (RESULTS / "metrics.md").write_text(
        f"# graph structure\n\n{_counts_table(stats)}\n\n## top cited\n\n{_top_cited_table(stats)}\n",
        encoding="utf-8",
    )
    _ = (_HERE / "README.md").write_text(_readme(stats, figs), encoding="utf-8")
    print(f"[exp3] wrote {len(figs)} figures + README.md", flush=True)


if __name__ == "__main__":
    main()
