"""
Topic-tree shape: leaf sizes, depth, and how coherence tracks leaf size

Every paper gets a leaf, so unlike a grid there is no noise bucket to report
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, LiteralString, cast

import matplotlib.pyplot as plt
import numpy as np
import psycopg
from _harness.report.theme import BARS, PRIMARY, SECONDARY, apply_theme  # noqa: E402

from graphiv.core.settings import PG_DSN

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]

CACHE = _EXP / "cache"
RESULTS = _EXP / "results"


def _q(conn: psycopg.Connection[tuple[Any, ...]], sql: str) -> list[tuple[Any, ...]]:
    return conn.execute(cast(LiteralString, sql)).fetchall()


def compute(use_cache: bool) -> dict[str, Any]:
    cache = CACHE / "summary.json"
    if cache.exists() and use_cache:
        return json.loads(cache.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
    out: dict[str, Any] = {}
    with psycopg.connect(PG_DSN) as conn:
        out["n_leaves"] = _q(conn, "SELECT count(*) FROM leaf")[0][0]
        out["n_assigned"] = _q(conn, "SELECT count(*) FROM paper_topic")[0][0]
        sizes = [int(r[0]) for r in _q(conn, "SELECT size FROM leaf ORDER BY size")]
        out["sizes"] = sizes
        out["size_stats"] = {
            "min": int(np.min(sizes)),
            "median": int(np.median(sizes)),
            "p90": int(np.percentile(sizes, 90)),
            "max": int(np.max(sizes)),
        }
        out["depth_hist"] = [
            [int(d), int(n)]
            for d, n in _q(conn, "SELECT depth, count(*) FROM leaf GROUP BY depth ORDER BY depth")
        ]
        out["radii"] = [
            float(r[0]) for r in _q(conn, "SELECT radius FROM leaf WHERE radius IS NOT NULL")
        ]
        out["size_radius"] = [
            [int(s), float(r)]
            for s, r in _q(conn, "SELECT size, radius FROM leaf WHERE radius IS NOT NULL")
        ]
    CACHE.mkdir(parents=True, exist_ok=True)
    _ = cache.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def figures(s: dict[str, Any]) -> None:
    apply_theme()
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    _ = ax.hist(s["sizes"], bins=60, color=PRIMARY, alpha=0.85)
    _ = ax.axvline(
        s["size_stats"]["median"],
        color=SECONDARY,
        linestyle="--",
        label=f"median {s['size_stats']['median']}",
    )
    ax.set_xlabel("leaf size (papers)")
    ax.set_ylabel("# leaves")
    ax.set_title(f"Leaf-size distribution ({s['n_leaves']:,} leaves, no noise bucket)")
    _ = ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "leaf_size.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    d = s["depth_hist"]
    bars = ax.bar(
        [str(x[0]) for x in d],
        [x[1] for x in d],
        color=[BARS[i % len(BARS)] for i in range(len(d))],
    )
    ax.set_xlabel("tree depth")
    ax.set_ylabel("# leaves")
    ax.set_title("Leaf depth distribution (deep where dense, shallow where coherent)")
    for b, x in zip(bars, d, strict=False):
        ax.text(
            b.get_x() + b.get_width() / 2,
            x[1],
            f"{x[1]}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(RESULTS / "leaf_depth.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.8, 4.5))
    xs = [p[0] for p in s["size_radius"]]
    ys = [p[1] for p in s["size_radius"]]
    _ = ax.scatter(xs, ys, s=6, color=PRIMARY, alpha=0.4)
    ax.set_xlabel("leaf size")
    ax.set_ylabel("radius (RMS coherence)")
    ax.set_title("Coherence vs leaf size (early-stop keeps leaves tight)")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(RESULTS / "size_vs_radius.png", dpi=130)
    plt.close(fig)


def tables(s: dict[str, Any]) -> None:
    st = s["size_stats"]
    md = [
        "| metric | value |",
        "|---|--:|",
        f"| leaves | {s['n_leaves']:,} |",
        f"| papers assigned | {s['n_assigned']:,} |",
        f"| leaf size min / median / p90 / max | {st['min']} / {st['median']} / "
        f"{st['p90']} / {st['max']} |",
    ]
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    macros = [
        f"\\newcommand{{\\NLeaves}}{{{s['n_leaves']:,}}}",
        f"\\newcommand{{\\NAssigned}}{{{s['n_assigned']:,}}}",
        f"\\newcommand{{\\LeafMedian}}{{{st['median']}}}",
        f"\\newcommand{{\\LeafMax}}{{{st['max']}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

    tab = [
        "\\begin{tabular}{lr}",
        "\\toprule",
        "metric & value \\\\",
        "\\midrule",
        f"leaves & {s['n_leaves']:,} \\\\",
        f"papers assigned & {s['n_assigned']:,} \\\\",
        f"leaf size min/median/p90/max & {st['min']} / {st['median']} / {st['p90']} / "
        f"{st['max']} \\\\",
        "\\bottomrule",
        "\\end{tabular}",
    ]
    _ = (RESULTS / "table.tex").write_text("\n".join(tab) + "\n", encoding="utf-8")


def run(use_cache: bool) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"[05-topic-tree] computing (use_cache={use_cache}) ...", flush=True)
    s = compute(use_cache)
    figures(s)
    tables(s)
    print(
        f"[05-topic-tree] {s['n_leaves']:,} leaves / {s['n_assigned']:,} papers; "
        f"wrote 3 figures + tables",
        flush=True,
    )
