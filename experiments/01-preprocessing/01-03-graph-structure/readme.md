# 03 — graph structure

**What:** characterizes the intent-typed citation graph from Postgres — scale, in/out-degree
distributions, edge typing, growth, top-cited papers. Pure SQL, no LLM.

**Conclusion:** a **36.7M-distinct-edge**, near-scale-free graph over **3.07M** papers; its in-degree
ranking recovers the canonical ML landmarks (ResNet/BERT/Transformer/…), confirming the resolved
graph is sound. Heavy-tailed hubs motivate phase-6's "induce within a topical pool"; per-edge
intent/polarity typing is the differentiator.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py [--no-cache]`.
