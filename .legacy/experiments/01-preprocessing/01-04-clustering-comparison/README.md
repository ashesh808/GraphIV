# 04 — clustering comparison

**What:** the shipped density-aware bisecting topic tree vs k-means / DBSCAN / HDBSCAN on a common
sample (30k papers, PCA-50). SQL + sklearn, no LLM. *(Topic tree is an offline-browse artifact, off
the phase-6 retrieval hot path.)*

**Conclusion:** the decisive axis is the **noise bucket** — HDBSCAN dumps **59 %** of papers into
noise, DBSCAN collapses to one cluster; the bisecting tree places **every** paper (0 % noise) at a
fine, density-adaptive grain. Silhouette is the wrong lens at this grain.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py [--no-cache] [--n N]`.
