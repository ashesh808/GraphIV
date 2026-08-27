"""
The shipped bisecting tree against a uniform grid and against density clustering

All arms run on one common sample of embedded papers, reduced by PCA
Metrics are the noise fraction, the cluster count, mean coherence and silhouette
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, LiteralString, cast

import matplotlib.pyplot as plt
import numpy as np
import psycopg
from _harness.report.theme import BARS, apply_theme  # noqa: E402
from sklearn.cluster import DBSCAN, MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from graphiv.core.settings import PG_DSN

_HERE = Path(__file__).resolve()
_EXP = _HERE.parents[1]
_REPO = _HERE.parents[4]

CACHE = _EXP / "cache"
RESULTS = _EXP / "results"


def _coherence(x: np.ndarray, labels: np.ndarray) -> float:
    """
    Mean RMS distance of points to their cluster centroid (lower = tighter), noise excluded
    """
    tot, k = 0.0, 0
    for c in set(labels.tolist()):
        if c < 0:
            continue
        pts = x[labels == c]
        if len(pts) < 2:
            continue
        tot += float(np.sqrt(((pts - pts.mean(0)) ** 2).sum(1).mean()))
        k += 1
    return tot / max(1, k)


def _metrics(name: str, x: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    noise = float((labels < 0).mean())
    n_clusters = len({c for c in labels.tolist() if c >= 0})
    mask = labels >= 0
    sil = 0.0
    if n_clusters > 1 and mask.sum() > 1000:
        idx = np.random.choice(np.where(mask)[0], min(5000, int(mask.sum())), replace=False)
        sil = float(silhouette_score(x[idx], labels[idx]))
    return {
        "method": name,
        "noise_frac": round(noise, 4),
        "n_clusters": n_clusters,
        "coherence": round(_coherence(x, labels), 4),
        "silhouette": round(sil, 4),
    }


def compute(use_cache: bool, n: int) -> dict[str, Any]:
    cache = CACHE / "summary.json"
    if cache.exists() and use_cache:
        return json.loads(cache.read_text(encoding="utf-8"))  # pyright: ignore[reportAny]
    print(
        f"[04-clustering] sampling {n:,} embedded papers (with a shipped leaf) ...",
        flush=True,
    )
    with psycopg.connect(PG_DSN) as conn:
        rows: list[tuple[Any, ...]] = conn.execute(
            cast(
                LiteralString,
                "SELECT e.embedding::text, t.leaf_id FROM paper_embedding e "
                "JOIN paper_topic t USING (arxiv_id) ORDER BY random() LIMIT %s",
            ),
            (n,),
        ).fetchall()
    vecs = np.array(
        [[float(v) for v in r[0].strip("[]").split(",")] for r in rows],
        dtype=np.float32,
    )
    tree_labels = np.array([int(r[1]) for r in rows])
    print(f"[04-clustering] PCA-50 on {vecs.shape} ...", flush=True)
    x = PCA(n_components=50, random_state=42).fit_transform(vecs)
    k = len(set(tree_labels.tolist()))

    results: list[dict[str, Any]] = [_metrics("bisecting-tree (shipped)", x, tree_labels)]
    print("[04-clustering] k-means uniform grid ...", flush=True)
    km = MiniBatchKMeans(
        n_clusters=max(8, k), random_state=42, n_init="auto", batch_size=4096
    ).fit_predict(x)
    results.append(_metrics("k-means (uniform grid)", x, km))
    print("[04-clustering] DBSCAN ...", flush=True)
    db = DBSCAN(eps=2.5, min_samples=10, n_jobs=-1).fit_predict(x)
    results.append(_metrics("DBSCAN", x, db))
    try:
        from sklearn.cluster import HDBSCAN  # noqa: PLC0415

        print("[04-clustering] HDBSCAN ...", flush=True)
        hd = HDBSCAN(min_cluster_size=25).fit_predict(x)
        results.append(_metrics("HDBSCAN", x, hd))
    except Exception as e:  # noqa: BLE001
        print(f"[04-clustering] HDBSCAN unavailable: {e}", flush=True)

    out: dict[str, Any] = {
        "n_sample": len(rows),
        "tree_leaves_in_sample": k,
        "results": results,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    _ = cache.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def figures(s: dict[str, Any]) -> None:
    apply_theme()
    res = s["results"]
    names = [r["method"] for r in res]
    for key, title, fname in [
        (
            "noise_frac",
            "Noise-bucket fraction (lower = better; tree has none)",
            "noise.png",
        ),
        ("coherence", "Mean coherence / RMS radius (lower = tighter)", "coherence.png"),
        ("silhouette", "Silhouette (higher = better separated)", "silhouette.png"),
    ]:
        fig, ax = plt.subplots(figsize=(7.0, 4.0))
        vals = [r[key] for r in res]
        bars = ax.bar(
            range(len(names)),
            vals,
            color=[BARS[i % len(BARS)] for i in range(len(names))],
        )
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=20, ha="right", fontsize=8)
        ax.set_title(title)
        for b, v in zip(bars, vals, strict=False):
            ax.text(
                b.get_x() + b.get_width() / 2,
                v,
                f"{v:g}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        fig.tight_layout()
        fig.savefig(RESULTS / fname, dpi=130)
        plt.close(fig)


def tables(s: dict[str, Any]) -> None:
    res = s["results"]
    md = [
        f"Sample n={s['n_sample']:,}, tree leaves in sample = {s['tree_leaves_in_sample']:,}.",
        "",
        "| method | noise bucket | clusters | coherence (lower) | silhouette (higher) |",
        "|---|--:|--:|--:|--:|",
    ]
    for r in res:
        md.append(
            f"| {r['method']} | {r['noise_frac'] * 100:.1f}% | {r['n_clusters']:,} | "
            f"{r['coherence']} | {r['silhouette']} |"
        )
    _ = (RESULTS / "metrics.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    macros = [
        f"\\newcommand{{\\NSample}}{{{s['n_sample']:,}}}",
        f"\\newcommand{{\\TreeLeaves}}{{{s['tree_leaves_in_sample']:,}}}",
    ]
    _ = (RESULTS / "macros.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

    tab = [
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "method & noise & clusters & coherence & silhouette \\\\",
        "\\midrule",
    ]
    for r in res:
        tab.append(
            f"{r['method']} & {r['noise_frac'] * 100:.1f}\\% & {r['n_clusters']:,} & "
            f"{r['coherence']} & {r['silhouette']} \\\\"
        )
    tab += ["\\bottomrule", "\\end{tabular}"]
    _ = (RESULTS / "table.tex").write_text("\n".join(tab) + "\n", encoding="utf-8")


def run(use_cache: bool, n: int) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    s = compute(use_cache, n)
    figures(s)
    tables(s)
    print(
        f"[04-clustering] compared {len(s['results'])} methods; wrote 3 figures + tables",
        flush=True,
    )
