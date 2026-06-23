"""experiment-1 — the 5-layer citation resolver: what resolved, by method / category / era.

Reads `citation.method` (+ joins category/year) from the single Postgres store and characterizes
the layered resolver (L0 link -> L1 text -> L2 doi -> L3 jref -> L4 title-exact -> L5 title-fuzzy,
with rejected-* / none for misses). Pure SQL + figures, no LLM. Heavy joins are cached.

    uv run python experiments/experiment-1-resolver-quality/run.py [--force]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, LiteralString, cast

import matplotlib.pyplot as plt
import psycopg

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_REPO / "experiments"))
from _harness.theme import BARS, PRIMARY, SECONDARY, apply_theme  # noqa: E402

RESULTS = _HERE / "results"
PG_DSN = os.environ.get("ARXIVKG_PG_DSN", f"host={_REPO}/.pg port=5433 dbname=arxivkg")
# resolved methods, cheapest-first (the layer order)
LAYERS = [
    "link",
    "text",
    "doi",
    "jref",
    "title-exact",
    "title-exact-noyr",
    "title-fuzzy",
]


def _q(conn: psycopg.Connection[tuple[Any, ...]], sql: str) -> list[tuple[Any, ...]]:
    return conn.execute(cast(LiteralString, sql)).fetchall()


def compute(force: bool) -> dict[str, Any]:
    cache = RESULTS / "summary.json"
    if cache.exists() and not force:
        return json.loads(
            cache.read_text(encoding="utf-8")
        )  # pyright: ignore[reportAny]
    out: dict[str, Any] = {}
    with psycopg.connect(PG_DSN) as conn:
        _ = conn.execute("SET statement_timeout='1800s'")
        out["method_mix"] = [
            [str(m), int(n)]
            for m, n in _q(
                conn,
                "SELECT method, count(*) FROM citation GROUP BY method ORDER BY count(*) DESC",
            )
        ]
        total = sum(n for _, n in out["method_mix"])
        resolved = sum(n for m, n in out["method_mix"] if m in LAYERS)
        out["total"] = total
        out["resolved"] = resolved
        out["resolution_rate"] = round(100.0 * resolved / max(1, total), 2)
        # per-layer share of *resolved*
        out["layer_share"] = [[m, n] for m, n in out["method_mix"] if m in LAYERS]
        # resolution rate by citing-paper category (top 15 by volume)
        out["by_category"] = [
            [str(cat), int(res), int(tot)]
            for cat, res, tot in _q(
                conn,
                "SELECT m.primary_category, "
                "count(*) FILTER (WHERE c.cited_id IS NOT NULL) AS res, count(*) AS tot "
                "FROM citation c JOIN paper p ON p.id=c.citing_id "
                "JOIN paper_meta m ON m.arxiv_id=p.arxiv_id "
                "WHERE m.primary_category IS NOT NULL "
                "GROUP BY m.primary_category ORDER BY tot DESC LIMIT 15",
            )
        ]
        # resolution rate by era (citing-paper year)
        out["by_year"] = [
            [int(y), int(res), int(tot)]
            for y, res, tot in _q(
                conn,
                "SELECT m.year, count(*) FILTER (WHERE c.cited_id IS NOT NULL) AS res, "
                "count(*) AS tot FROM citation c JOIN paper p ON p.id=c.citing_id "
                "JOIN paper_meta m ON m.arxiv_id=p.arxiv_id WHERE m.year IS NOT NULL "
                "GROUP BY m.year ORDER BY m.year",
            )
        ]
    _ = cache.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def figures(s: dict[str, Any]) -> None:
    apply_theme()
    # method mix (log y)
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    mm = s["method_mix"]
    bars = ax.bar(
        range(len(mm)),
        [x[1] for x in mm],
        color=[BARS[i % len(BARS)] for i in range(len(mm))],
    )
    ax.set_yscale("log")
    ax.set_xticks(range(len(mm)))
    ax.set_xticklabels([x[0] for x in mm], rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("# citations (log)")
    ax.set_title("Resolution method mix (5-layer resolver outcomes)")
    for b, x in zip(bars, mm):
        ax.text(
            b.get_x() + b.get_width() / 2,
            x[1],
            f"{x[1]:,}",
            ha="center",
            va="bottom",
            fontsize=6,
        )
    fig.tight_layout()
    fig.savefig(RESULTS / "method_mix.png", dpi=130)
    plt.close(fig)
    # resolution rate by category
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    bc = s["by_category"]
    rates = [100.0 * r / max(1, t) for _, r, t in bc]
    ax.bar(range(len(bc)), rates, color=PRIMARY)
    ax.set_xticks(range(len(bc)))
    ax.set_xticklabels([x[0] for x in bc], rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("resolution rate (%)")
    ax.set_title("Resolution rate by citing-paper category")
    ax.grid(True, axis="y")
    fig.tight_layout()
    fig.savefig(RESULTS / "by_category.png", dpi=130)
    plt.close(fig)
    # resolution rate by era
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    by = s["by_year"]
    ys = [int(y) for y, _, _ in by]
    rates = [100.0 * r / max(1, t) for _, r, t in by]
    ax.plot(ys, rates, color=SECONDARY, linewidth=2)
    ax.fill_between(ys, rates, color=SECONDARY, alpha=0.3)
    ax.set_xlabel("year")
    ax.set_ylabel("resolution rate (%)")
    ax.set_title("Resolution rate over time (ar5iv HTML coverage drives this)")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(RESULTS / "by_year.png", dpi=130)
    plt.close(fig)


def main() -> None:
    force = "--force" in sys.argv[1:]
    RESULTS.mkdir(parents=True, exist_ok=True)
    print("[exp1] computing resolver stats (cached unless --force) ...", flush=True)
    s = compute(force)
    figures(s)
    layer_rows = "\n".join(
        f"| {m} | {n:,} | {100.0 * n / max(1, s['resolved']):.1f}% |"
        for m, n in s["layer_share"]
    )
    readme = f"""# Experiment 1 — The 5-layer citation resolver

**What:** which of the layered resolver's stages (L0 link → L1 text → L2 doi → L3 jref → L4
title-exact → L5 title-fuzzy; `rejected-*`/`none` for misses) actually resolve citations, and how
resolution varies by field and era. Read straight from `citation.method` in the single store.
**Why:** the resolver is cheapest-first with early termination — high-confidence exact methods
short-circuit before fuzzy is ever tried; this quantifies each layer's contribution and the tail.

**Reproduce:** `uv run python experiments/experiment-1-resolver-quality/run.py` (idempotent;
`--force`). Heavy joins cached to `results/summary.json`.

## Headline

Overall resolution rate: **{s["resolution_rate"]}%** ({s["resolved"]:,} / {s["total"]:,}).

| layer (method) | resolved | share of resolved |
|---|--:|--:|
{layer_rows}

![method mix](results/method_mix.png)

## By field and era

Resolution rate varies by field (HTML/LaTeX availability + citation style) and rises over time as
ar5iv HTML coverage improves.

![by category](results/by_category.png)

![by year](results/by_year.png)

## Caveats

`rejected-*` rows are real resolver decisions (a fuzzy candidate that failed the year/author/overlap
gate) — kept in the store precisely so this analysis can show the precision/recall trade-off of the
fuzzy layer, not silently dropped.
"""
    _ = (RESULTS / "metrics.md").write_text(
        f"# resolver\n\nresolution_rate={s['resolution_rate']}%  resolved={s['resolved']:,}/{s['total']:,}\n",
        encoding="utf-8",
    )
    _ = (_HERE / "README.md").write_text(readme, encoding="utf-8")
    print(
        f"[exp1] resolution rate {s['resolution_rate']}%; wrote 3 figures + README",
        flush=True,
    )


if __name__ == "__main__":
    main()
