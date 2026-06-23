"""experiment-4 — clustering comparison: the bisecting tree vs uniform k-means vs DBSCAN/HDBSCAN.

The shipped topic tree (read from `paper_topic`) is a density-aware *bisecting* tree with a
coherence early-stop and NO noise bucket. This compares it, on a common sample, against the old-style
approaches: a uniform k-means grid and DBSCAN/HDBSCAN (which dump low-density points into a "noise"
bucket — the 355k "Miscellaneous" problem the tree was built to avoid). Metrics: noise fraction,
cluster count, mean coherence (RMS radius), silhouette. Sampled for tractability; results cached.

    uv run python experiments/experiment-4-clustering-comparison/run.py [--force] [--n 30000]
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
from sklearn.cluster import DBSCAN, MiniBatchKMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_REPO / "experiments"))
from _harness.theme import BARS, apply_theme  # noqa: E402

RESULTS = _HERE / "results"
PG_DSN = os.environ.get("ARXIVKG_PG_DSN", f"host={_REPO}/.pg port=5433 dbname=arxivkg")


def _coherence(x: np.ndarray, labels: np.ndarray) -> float:
    """Mean RMS distance of points to their cluster centroid (lower = tighter), noise excluded."""
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
        idx = np.random.choice(
            np.where(mask)[0], min(5000, int(mask.sum())), replace=False
        )
        sil = float(silhouette_score(x[idx], labels[idx]))
    return {
        "method": name,
        "noise_frac": round(noise, 4),
        "n_clusters": n_clusters,
        "coherence": round(_coherence(x, labels), 4),
        "silhouette": round(sil, 4),
    }


def compute(force: bool, n: int) -> dict[str, Any]:
    cache = RESULTS / "summary.json"
    if cache.exists() and not force:
        return json.loads(
            cache.read_text(encoding="utf-8")
        )  # pyright: ignore[reportAny]
    print(
        f"[exp4] sampling {n:,} embedded papers (with a shipped leaf) ...", flush=True
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
    print(f"[exp4] PCA-50 on {vecs.shape} ...", flush=True)
    x = PCA(n_components=50, random_state=42).fit_transform(vecs)
    k = len(set(tree_labels.tolist()))

    results: list[dict[str, Any]] = [
        _metrics("bisecting-tree (shipped)", x, tree_labels)
    ]
    print("[exp4] k-means uniform grid ...", flush=True)
    km = MiniBatchKMeans(
        n_clusters=max(8, k), random_state=42, n_init="auto", batch_size=4096
    ).fit_predict(x)
    results.append(_metrics("k-means (uniform grid)", x, km))
    print("[exp4] DBSCAN ...", flush=True)
    db = DBSCAN(eps=2.5, min_samples=10, n_jobs=-1).fit_predict(x)
    results.append(_metrics("DBSCAN", x, db))
    try:
        from sklearn.cluster import HDBSCAN  # noqa: PLC0415

        print("[exp4] HDBSCAN ...", flush=True)
        hd = HDBSCAN(min_cluster_size=25).fit_predict(x)
        results.append(_metrics("HDBSCAN", x, hd))
    except Exception as e:  # noqa: BLE001
        print(f"[exp4] HDBSCAN unavailable: {e}", flush=True)

    out: dict[str, Any] = {
        "n_sample": len(rows),
        "tree_leaves_in_sample": k,
        "results": results,
    }
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
        for b, v in zip(bars, vals):
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


def main() -> None:
    force = "--force" in sys.argv[1:]
    n = 30000
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    RESULTS.mkdir(parents=True, exist_ok=True)
    s = compute(force, n)
    figures(s)
    rows = "\n".join(
        f"| {r['method']} | {r['noise_frac'] * 100:.1f}% | {r['n_clusters']:,} | {r['coherence']} | {r['silhouette']} |"
        for r in s["results"]
    )
    readme = f"""# Experiment 4 — Clustering comparison

**What:** the shipped density-aware **bisecting tree** (read from `paper_topic`) vs a uniform
k-means grid and DBSCAN/HDBSCAN, on a common sample of {s["n_sample"]:,} embedded papers (768-d nomic
→ PCA-50). **Why:** the tree was built to avoid the old design's DBSCAN "noise bucket" that swallowed
355k niche papers into "Miscellaneous"; this quantifies the noise/coherence/separation trade-off.

**Reproduce:** `uv run python experiments/experiment-4-clustering-comparison/run.py` (sampled;
`--force`, `--n N`).

## Results (sample n={s["n_sample"]:,}, tree leaves in sample = {s["tree_leaves_in_sample"]:,})

| method | noise bucket | clusters | coherence ↓ | silhouette ↑ |
|---|--:|--:|--:|--:|
{rows}

![noise](results/noise.png)

![coherence](results/coherence.png)

![silhouette](results/silhouette.png)

## Read

The **bisecting tree assigns every paper a leaf (0% noise)** — the niche papers DBSCAN/HDBSCAN drop
into the noise bucket are exactly the ones phase-6 needs to retrieve. k-means also has no noise but
imposes a uniform grain; the tree's coherence early-stop adapts grain to density. Caveat: sampled +
PCA-50 (not the full UMAP-50 build); a fair *full* rebuild is heavier, but the noise-bucket contrast
is the structural point and is grain-robust.
"""
    _ = (RESULTS / "metrics.md").write_text(
        "# clustering\n\n" + rows + "\n", encoding="utf-8"
    )
    _ = (_HERE / "README.md").write_text(readme, encoding="utf-8")
    print(
        f"[exp4] compared {len(s['results'])} methods; wrote 3 figures + README",
        flush=True,
    )


if __name__ == "__main__":
    main()
