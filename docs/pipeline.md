# phase-6 retrieval → report pipeline

Ordered steps for one question, as implemented. Single-pass = `pipeline.run`; the deep loop
(`deep_loop.run_deep`) re-runs steps 1–8 each judge round (expanding the pool), then composes.

Each step: **name** — what it does — `code path`.

---

### 0. Query shaping (HyDE)
An LLM writes a hypothetical 4–6 sentence arXiv abstract for the topic; the EMBEDDED query is
`"Title: {question}\nAbstract: {hypothetical}"` (doc-shaped), not the raw question. Falls back
to the bare question on LLM failure.
`pipeline.hyde_query` → `retrieve.embed_query` (nomic on GPU, then `free_model()`)

### 1. Hybrid pool
Two candidate pools fused: vector arm = pgvector HNSW cosine KNN over `paper_embedding`
(top `n_pool` = 400 standard / 600 deep); lexical arm = Postgres `tsvector` rank over paper
**titles** (top 400). Fused by Reciprocal Rank Fusion (RRF_K=60); `.score` becomes the RRF score.
`retrieval_hybrid.hybrid_pool`, `store.vector_pool`, `store.lexical_pool`

### 2. Frontier detection
From the pool's year histogram (anchored to now), walk back while each year holds ≥30% of the
recent-peak volume; clamp to `[now-6, latest]`. Yields `frontier_year` and
`recent_floor = round(recency · m)` (landmark slots reserved for frontier work).
`recency.detect_frontier`

### 3. Refined pool (topic-leaf anchor + drill + recency inject)  — skipped by `--include-no-cluster`
Vote a single home leaf from the top-30 seeds' leaf membership; **prune the pool to that leaf
(+ same-parent-path siblings)**; then add leaf members that have a CITES edge to the pool
(citation-aware drill, scored by similarity); then inject top-k recent (≥ `frontier_year`) leaf
members, newest-cohort-first.
`retrieval_refined.refined_pool`, `topic_anchor.dominant_leaf`/`anchor_keep`

### 4. Frontier pull (leaf-independent)  — skipped by `--include-no-frontier-pull`
Vector-search the 1500 nearest papers, keep those ≥ `frontier_year`, pick `want` newest-cohort-
first. Bypasses the topic tree (which predates the 2025/26 delta, so new papers have no leaf).
`retrieval_refined.frontier_pull`, `store.vector_pool_recent`

### 5. Ancestor augmentation
Add the pool's most-cited one-hop-back papers (ranked by # of distinct pool citers, ≥3 min),
scored by similarity, up to 120 — recovers foundational lineage that isn't a top embedding
neighbour of the query.
`subgraph.augment_with_ancestors`, `store.ancestors`

### 6. Induce citation subgraph  — skipped by `--include-no-graph`
All CITES edges with BOTH endpoints in the pool; parallel (src,dst) occurrences collapse to one
edge carrying the strongest-signal intent (extends > uses > compares > critiques > motivates >
background) and that edge's polarity.
`subgraph.induce_subgraph`, `store.edges_among`

### 7. Rank landmarks (top `m` = 40/80/120)
Default `ppr`: personalized PageRank over citing→cited edges, teleporting to the query-similarity
seed; then reserve `recent_floor` frontier slots (newest-year-first), fill the rest by PPR score
(age-normalized tiebreak). Alternatives: `frontier` (age-normalized in-degree) / `indegree` (bare).
`pagerank.rank_landmarks_ppr` (`frontier_rank` / `subgraph.rank_landmarks`)

### 8. Structure
Eras = year tertiles (Origins / Key Advances / Current Frontier); main_path = longest
chronological citation chain among landmarks (DP, drops same-year/undated edges); tensions =
compare/critique/motivate edges among on-topic landmarks, negative-polarity first.
`subgraph.assign_eras`, `subgraph.main_path`, `subgraph.tensions`

### 9. Schema → extract → compose
Propose a question-specific extraction schema from the question + top-6 landmark abstracts; fill
it per landmark from full text (ar5iv cache, keyed by arxiv_id+schema_hash); build the digest and
compose. Single-pass: one `narrate` call. Deep: judge-driven gap rounds → per-paper full-PDF
critique → sectioned `long_compose` (outline → per-section → intro/close) → vision figure gallery
→ `report.md` + `report.tex`. Citations post-checked (grounded / off-digest / fabricated).
`schema.propose_schema`, `extract.extract_many`, `compose_report.build_digest`/`compose`,
`long_compose.compose_long`, `figures.figures_for`, `narrate.check_citations`
