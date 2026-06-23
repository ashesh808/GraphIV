"""Citation-graph structure analysis, computed directly from the single Postgres store.

Pure SQL + matplotlib (no LLM). Heavy aggregations are cached to results/summary.json so re-runs
are instant; pass force=True to recompute. Produces: global counts, in/out-degree distributions
(log-log), intent + polarity mix, citations-per-era, and the top-cited papers.
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
_REPO = _HERE.parents[2]
sys.path.insert(0, str(_REPO / "experiments"))
from _harness.theme import BARS, ON_SURFACE, PRIMARY, SECONDARY, apply_theme  # noqa: E402  # fmt: skip

PG_DSN = os.environ.get("ARXIVKG_PG_DSN", f"host={_REPO}/.pg port=5433 dbname=arxivkg")


def _q(conn: psycopg.Connection[tuple[Any, ...]], sql: str) -> list[tuple[Any, ...]]:
    return conn.execute(cast(LiteralString, sql)).fetchall()


def compute(results_dir: Path, force: bool) -> dict[str, Any]:
    """Compute (or load cached) graph-structure stats as a JSON-able dict."""
    cache = results_dir / "summary.json"
    if cache.exists() and not force:
        return json.loads(
            cache.read_text(encoding="utf-8")
        )  # pyright: ignore[reportAny]

    out: dict[str, Any] = {}
    with psycopg.connect(PG_DSN) as conn:
        _ = conn.execute("SET statement_timeout='1200s'")
        out["n_papers"] = _q(conn, "SELECT count(*) FROM paper")[0][0]
        out["n_citations"] = _q(conn, "SELECT count(*) FROM citation")[0][0]
        out["n_resolved"] = _q(
            conn, "SELECT count(*) FROM citation WHERE cited_id IS NOT NULL"
        )[0][0]
        out["n_edges"] = _q(
            conn,
            "SELECT count(DISTINCT (citing_id, cited_id)) FROM citation WHERE cited_id IS NOT NULL",
        )[0][0]
        # in-degree histogram (citations received per paper)
        indeg = _q(
            conn,
            "SELECT indeg, count(*) FROM (SELECT cited_id, count(*) AS indeg FROM citation "
            "WHERE cited_id IS NOT NULL GROUP BY cited_id) t GROUP BY indeg ORDER BY indeg",
        )
        out["indegree_hist"] = [[int(d), int(n)] for d, n in indeg]
        # out-degree histogram (references emitted per paper, resolved only)
        outdeg = _q(
            conn,
            "SELECT od, count(*) FROM (SELECT citing_id, count(*) AS od FROM citation "
            "WHERE cited_id IS NOT NULL GROUP BY citing_id) t GROUP BY od ORDER BY od",
        )
        out["outdegree_hist"] = [[int(d), int(n)] for d, n in outdeg]
        # intent + polarity mix (labeled, resolved edges)
        out["intent_mix"] = [
            [str(i), int(n)]
            for i, n in _q(
                conn,
                "SELECT intent, count(*) FROM citation WHERE intent IS NOT NULL "
                "GROUP BY intent ORDER BY count(*) DESC",
            )
        ]
        out["polarity_mix"] = [
            [str(p), int(n)]
            for p, n in _q(
                conn,
                "SELECT polarity, count(*) FROM citation WHERE polarity IS NOT NULL "
                "GROUP BY polarity ORDER BY count(*) DESC",
            )
        ]
        # citations per era (by citing-paper year)
        out["per_year"] = [
            [int(y), int(n)]
            for y, n in _q(
                conn,
                "SELECT m.year, count(*) FROM citation c JOIN paper p ON p.id=c.citing_id "
                "JOIN paper_meta m ON m.arxiv_id=p.arxiv_id WHERE m.year IS NOT NULL "
                "GROUP BY m.year ORDER BY m.year",
            )
        ]
        # top-cited papers (within-corpus in-degree)
        out["top_cited"] = [
            [str(a), int(n), str(t or "")[:60], int(y) if y is not None else None]
            for a, n, t, y in _q(
                conn,
                "SELECT p.arxiv_id, c.n, m.title, m.year FROM "
                "(SELECT cited_id, count(*) AS n FROM citation WHERE cited_id IS NOT NULL "
                " GROUP BY cited_id ORDER BY n DESC LIMIT 20) c "
                "JOIN paper p ON p.id=c.cited_id LEFT JOIN paper_meta m ON m.arxiv_id=p.arxiv_id "
                "ORDER BY c.n DESC",
            )
        ]
    _ = cache.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def _loglog(hist: list[list[int]], title: str, xlabel: str, out_path: Path) -> None:
    apply_theme()
    xs = [h[0] for h in hist if h[0] > 0]
    ys = [h[1] for h in hist if h[0] > 0]
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.scatter(xs, ys, s=8, color=PRIMARY, alpha=0.6)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("# papers")
    ax.set_title(title)
    ax.grid(True, which="both")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _bars(
    pairs: list[list[Any]], title: str, out_path: Path, ylabel: str = "count"
) -> None:
    apply_theme()
    labels = [str(p[0]) for p in pairs]
    vals = [float(p[1]) for p in pairs]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    bars = ax.bar(
        range(len(vals)), vals, color=[BARS[i % len(BARS)] for i in range(len(vals))]
    )
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v,
            f"{v:,.0f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=ON_SURFACE,
        )
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _line(pairs: list[list[int]], title: str, out_path: Path) -> None:
    apply_theme()
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.fill_between(xs, ys, color=SECONDARY, alpha=0.35)
    ax.plot(xs, ys, color=SECONDARY, linewidth=2)
    ax.set_xlabel("year (citing paper)")
    ax.set_ylabel("# citations emitted")
    ax.set_title(title)
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def figures(stats: dict[str, Any], results_dir: Path) -> list[str]:
    """Render all figures; return their filenames (for the README)."""
    _loglog(
        stats["indegree_hist"],
        "In-degree distribution (citations received)",
        "in-degree",
        results_dir / "indegree_loglog.png",
    )
    _loglog(
        stats["outdegree_hist"],
        "Out-degree distribution (references emitted)",
        "out-degree",
        results_dir / "outdegree_loglog.png",
    )
    _bars(
        stats["intent_mix"],
        "Citation intent mix (corpus-wide)",
        results_dir / "intent_mix.png",
    )
    _bars(
        stats["polarity_mix"],
        "Citation polarity mix (corpus-wide)",
        results_dir / "polarity_mix.png",
    )
    _line(
        stats["per_year"], "Citation activity over time", results_dir / "per_year.png"
    )
    return [
        "indegree_loglog.png",
        "outdegree_loglog.png",
        "intent_mix.png",
        "polarity_mix.png",
        "per_year.png",
    ]
