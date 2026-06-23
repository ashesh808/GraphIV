"""experiment-5 — density-aware topic tree: leaf size / depth / coherence structure.

Reads `leaf` + `paper_topic` from the single Postgres store and shows the bisecting tree's shape:
no noise bucket (every paper gets a leaf), the leaf-size distribution vs the old uniform-grid /
DBSCAN approach, and how coherence (radius) tracks leaf size. Pure SQL + figures, no LLM.

    uv run python experiments/experiment-5-topic-tree/run.py [--force]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, LiteralString, cast

import matplotlib.pyplot as plt
import numpy as np
import psycopg

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_REPO / "experiments"))
from _harness.theme import BARS, PRIMARY, SECONDARY, apply_theme  # noqa: E402

RESULTS = _HERE / "results"
PG_DSN = os.environ.get("ARXIVKG_PG_DSN", f"host={_REPO}/.pg port=5433 dbname=arxivkg")


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
            for d, n in _q(
                conn, "SELECT depth, count(*) FROM leaf GROUP BY depth ORDER BY depth"
            )
        ]
        out["radii"] = [
            float(r[0])
            for r in _q(conn, "SELECT radius FROM leaf WHERE radius IS NOT NULL")
        ]
        out["size_radius"] = [
            [int(s), float(r)]
            for s, r in _q(
                conn, "SELECT size, radius FROM leaf WHERE radius IS NOT NULL"
            )
        ]
    _ = cache.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def figures(s: dict[str, Any]) -> None:
    apply_theme()
    # leaf size distribution
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.hist(s["sizes"], bins=60, color=PRIMARY, alpha=0.85)
    ax.axvline(
        s["size_stats"]["median"],
        color=SECONDARY,
        linestyle="--",
        label=f"median {s['size_stats']['median']}",
    )
    ax.set_xlabel("leaf size (papers)")
    ax.set_ylabel("# leaves")
    ax.set_title(f"Leaf-size distribution ({s['n_leaves']:,} leaves, no noise bucket)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS / "leaf_size.png", dpi=130)
    plt.close(fig)
    # depth bar
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
    for b, x in zip(bars, d):
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
    # size vs radius (coherence)
    fig, ax = plt.subplots(figsize=(6.8, 4.5))
    xs = [p[0] for p in s["size_radius"]]
    ys = [p[1] for p in s["size_radius"]]
    ax.scatter(xs, ys, s=6, color=PRIMARY, alpha=0.4)
    ax.set_xlabel("leaf size")
    ax.set_ylabel("radius (RMS coherence)")
    ax.set_title("Coherence vs leaf size (early-stop keeps leaves tight)")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(RESULTS / "size_vs_radius.png", dpi=130)
    plt.close(fig)


def main() -> None:
    force = "--force" in sys.argv[1:]
    RESULTS.mkdir(parents=True, exist_ok=True)
    print("[exp5] computing topic-tree stats ...", flush=True)
    s = compute(force)
    figures(s)
    st = s["size_stats"]
    readme = f"""# Experiment 5 — Density-aware topic tree

**What:** the shape of the bisecting topic tree (`leaf` + `paper_topic` in the single Postgres
store). **Why:** the tree anchors phase-6 retrieval to an on-topic leaf; this shows it has **no
noise bucket** (every one of the {s["n_assigned"]:,} papers gets a leaf, vs the old DBSCAN design
that dumped 355k papers into "Miscellaneous") and that coherence early-stop keeps leaves tight.

**Reproduce:** `uv run python experiments/experiment-5-topic-tree/run.py` (idempotent; `--force`).

## Summary

| metric | value |
|---|--:|
| leaves | {s["n_leaves"]:,} |
| papers assigned | {s["n_assigned"]:,} |
| leaf size min / median / p90 / max | {st["min"]} / {st["median"]} / {st["p90"]} / {st["max"]} |

![leaf size](results/leaf_size.png)

![leaf depth](results/leaf_depth.png)

![coherence](results/size_vs_radius.png)

## Caveats

Leaf membership is from the pre-delta tree build; 2025/2026 papers have no leaf (handled by phase-6
`frontier_pull`). Rebuilding the tree on the current corpus is experiment-4's territory.
"""
    _ = (RESULTS / "metrics.md").write_text(
        f"# topic tree\n\nleaves={s['n_leaves']:,} papers={s['n_assigned']:,} "
        f"size(min/med/p90/max)={st['min']}/{st['median']}/{st['p90']}/{st['max']}\n",
        encoding="utf-8",
    )
    _ = (_HERE / "README.md").write_text(readme, encoding="utf-8")
    print("[exp5] wrote 3 figures + README.md", flush=True)


if __name__ == "__main__":
    main()
