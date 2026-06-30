# 03-07-graph-representation

**What:** how the retrieved citation subgraph is serialized into the LLM prompt. Phase 1 settles the
STRUCTURE axis (flat / adjacency / dot / subtree / json / matrix); phase 2 layers the orthogonal axes
(roles / extracted-content / alias) onto the adjacency winner. 8 deep-panel topics, absolute 4-axis +
order-debiased pairwise.

**Conclusion:** **production digest = adjacency-list + extracted content + role tags + aliasing.**
adjacency_list wins structure (pair_net 0.5) at the fewest tokens; extracted full-text content is the
biggest lever (0.75); roles help only WITH content; aliasing is a free token win. Winner
`adj_roles_extracted` tops every axis (overall 4.906, pairwise 7/1/0).

Full write-up: [`report/report.md`](report/report.md) · [`report/report.tex`](report/report.tex) →
`report/report.pdf`. Run: `uv run python run.py` (`--phase2` for the axes phase).
