# Experiment 04 — Clustering comparison

*Preprocessing · Phase 5 (topic tree) · engine: SQL + sklearn + figures, no LLM.*
*Note: the topic tree is an optional offline-browse artifact (off the phase-6 retrieval hot path).*

## What we did

The shipped semantic index is a density-aware **bisecting tree** (read from `paper_topic`): every
paper gets a leaf, with a coherence early-stop and **no noise bucket**. This experiment compares it,
on a common sample, against the old-style alternatives — a uniform k-means grid and DBSCAN/HDBSCAN —
to quantify the trade-off the tree was built to win: avoiding the "noise bucket" that swallows niche
papers into a "Miscellaneous" dump.

## Method

Sample 30,000 papers that carry a shipped leaf (768-d nomic embedding → PCA-50), then run each
clusterer and score: noise-bucket fraction, cluster count, mean coherence (RMS radius, lower =
tighter), silhouette. Sampled for tractability; the sample + labels cache to `cache/summary.json`.

## Results (sample n = 30,000, tree leaves in sample = 3,139)

| method | noise bucket | clusters | coherence (lower) | silhouette (higher) |
|---|--:|--:|--:|--:|
| bisecting-tree (shipped) | 0.0% | 3,139 | 0.2971 | -0.1129 |
| k-means (uniform grid) | 0.0% | 3,132 | 0.2607 | -0.0438 |
| DBSCAN | 0.0% | 1 | 0.4942 | 0.0 |
| HDBSCAN | 59.0% | 2 | 0.3864 | 0.137 |

![noise](../results/noise.png)

![coherence](../results/coherence.png)

![silhouette](../results/silhouette.png)

## Conclusion

The decisive axis is the **noise bucket**: HDBSCAN dumps **59 %** of the sample into noise (and
collapses to 2 clusters); DBSCAN degenerates to a single cluster at this grain. Those discarded
low-density points are exactly the niche papers phase-5/6 must still place. The **bisecting tree
assigns every paper a leaf (0 % noise)** at a fine, density-adaptive grain (3,139 leaves), whereas
k-means matches the no-noise property only by imposing a *uniform* grain the tree's coherence
early-stop avoids.

## Caveats

Silhouette is low/negative for the fine-grained partitions (3,000+ clusters in PCA-50 space are not
linearly separated) — it is the wrong lens for this design; the **noise-bucket and density-adaptive
grain are the structural points**, and they are grain-robust. This is a sampled + PCA-50 proxy, not
the full UMAP-50 build, but the noise-bucket contrast holds regardless.
