"""Resolver-quality compute + figures + tables (experiment 01).

Reads `citation.method` (+ category/year joins) from the single Postgres store and characterizes the
layered resolver (L0 link -> L1 text -> L2 doi -> L3 jref -> L4 title-exact -> L5 title-fuzzy, with
rejected-*/none for misses). Pure SQL + figures, no LLM. The heavy join is cached to cache/summary.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, LiteralString, cast

import matplotlib.pyplot as plt
import psycopg

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]  # the NN-slug experiment dir
_REPO = _HERE.parents[
    4
]  # repo root: code -> NN-slug -> preprocessing -> experiments -> repo
sys.path.insert(0, str(_REPO / "experiments"))
from _harness.theme import BARS, PRIMARY, SECONDARY, apply_theme  # noqa: E402

CACHE = _EXP / "cache"
RESULTS = _EXP / "results"
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


def compute(use_cache: bool) -> dict[str, Any]:
    cache = CACHE / "summary.json"
    if cache.exists() and use_cache:
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
        out["layer_share"] = [[m, n] for m, n in out["method_mix"] if m in LAYERS]
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
    CACHE.mkdir(parents=True, exist_ok=True)
    _ = cache.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def figures(s: dict[str, Any]) -> None:
    apply_theme()
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

    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    bc = s["by_category"]
    rates = [100.0 * r / max(1, t) for _, r, t in bc]
    _ = ax.bar(range(len(bc)), rates, color=PRIMARY)
    ax.set_xticks(range(len(bc)))
    ax.set_xticklabels([x[0] for x in bc], rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("resolution rate (%)")
    ax.set_title("Resolution rate by citing-paper category")
    ax.grid(True, axis="y")
    fig.tight_layout()
    fig.savefig(RESULTS / "by_category.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    by = s["by_year"]
    ys = [int(y) for y, _, _ in by]
    rates = [100.0 * r / max(1, t) for _, r, t in by]
    _ = ax.plot(ys, rates, color=SECONDARY, linewidth=2)
    _ = ax.fill_between(ys, rates, color=SECONDARY, alpha=0.3)
    ax.set_xlabel("year")
    ax.set_ylabel("resolution rate (%)")
    ax.set_title("Resolution rate over time (ar5iv HTML coverage drives this)")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(RESULTS / "by_year.png", dpi=130)
    plt.close(fig)


def tables(s: dict[str, Any]) -> None:
    """Write results/metrics.md (+ metrics.tex) — the single source the reports import."""
    rate, res, tot = s["resolution_rate"], s["resolved"], s["total"]
    md = [
        f"**Overall resolution rate: {rate}%** ({res:,} / {tot:,}).",
        "",
        "| layer (method) | resolved | share of resolved |",
        "|---|--:|--:|",
    ]
    for m, n in s["layer_share"]:
        md.append(f"| {m} | {n:,} | {100.0 * n / max(1, res):.1f}% |")
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    macros = [
        f"\\newcommand{{\\ResRate}}{{{rate}\\%}}",
        f"\\newcommand{{\\ResCount}}{{{res:,}}}",
        f"\\newcommand{{\\CitTotal}}{{{tot:,}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

    tab = [
        "\\begin{tabular}{lrr}",
        "\\toprule",
        "layer (method) & resolved & share of resolved \\\\",
        "\\midrule",
    ]
    for m, n in s["layer_share"]:
        tab.append(f"{m} & {n:,} & {100.0 * n / max(1, res):.1f}\\% \\\\")
    tab += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(tab) + "\n", encoding="utf-8")


def run(use_cache: bool) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"[01-resolver] computing (use_cache={use_cache}) ...", flush=True)
    s = compute(use_cache)
    figures(s)
    tables(s)
    print(
        f"[01-resolver] resolution rate {s['resolution_rate']}%; wrote 3 figures + tables",
        flush=True,
    )
