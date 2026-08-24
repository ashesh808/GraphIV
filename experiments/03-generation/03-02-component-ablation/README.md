# 03-02-component-ablation

**What:** the classic "scientific-paper" ablation — knock out one pipeline component at a time
(`indegree` / `no_cluster` / `no_graph` / `no_fulltext` vs `full`) over the 27-topic battery, reading
the full metric vector + 4-axis judge + faithfulness tripwire.

**Conclusion:** **read the vector, never one number.** `no_graph` posts the highest frontier_count yet
0 edges, ~0 recall, and the worst judge — a surface metric improving while chronology collapses. The
full system is the only config that keeps every axis healthy at once.

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py`.
