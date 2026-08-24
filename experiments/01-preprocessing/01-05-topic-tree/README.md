# 05 — topic tree

**What:** the shape of the shipped density-aware bisecting topic tree (`leaf` + `paper_topic`) —
leaf-size/depth distributions and coherence-vs-size. Pure SQL, no LLM. *(Offline-browse artifact,
off the phase-6 retrieval hot path.)*

**Conclusion:** **3,582** leaves over **2.92M** papers, **no noise bucket** (vs the DBSCAN design's
~355k "Miscellaneous" dump); non-uniform depth + a flat coherence-vs-size scatter confirm the
early-stop keeps leaves tight while adapting grain to density.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py [--no-cache]`.
