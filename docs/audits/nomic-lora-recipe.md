# nomic-LoRA: graph-structural fine-tune (scratch)

Goal: LoRA fine-tune `nomic-embed-text-v2-moe` so cosine reflects citation-graph
structure, not just text — a 2026 retread of node2vec-style structural embeddings.
LoRA (not full fine-tune): ~1/10 the cost and dodges MoE expert/router collapse.

## Label scheme (LOCKED)

- **Positives** — sampled primarily from `extends`/`uses` citation edges (real
  lineage). Intent taxonomy is `uses,extends,compares,motivates,background,critiques`
  (`phases/phase-3/components/label/_common.py`); only extends/uses are lineage.
- **Hard negatives** — `soft_score ≈ 0` (disjoint OR hub-only shared ancestry)
  AND high text-cosine (mined off the existing HNSW). Text-close + graph-far is
  what teaches structure the encoder doesn't already get from text.
- **Soft/middle** — graded by `soft_score` (below).

## soft_score = IC-weighted ancestor-bag cosine (`graph_sim.py`, toy-verified)

- `ic(x) = -log((1+indeg(x))/N)/log(N)` ∈ (0,1]; hubs→~0.1, niche→~0.8.
- ancestor bag = papers reachable via extends/uses to depth D=3, weight
  `decay^depth · ic`, decay=0.5.
- score = cosine(bag_A, bag_B) ∈ [0,1].
- Property that resolves the LCA question: **sharing a hub LCA ≈ 0**, so a generic
  common ancestor lands in the negative band automatically (toy: C~D share hub → 0.015).
  Bands: direct edge or score≥~0.5 → positive; ≈0 + text-close → hard neg; else soft.

## Loss

InfoNCE over extends/uses positives + in-batch + mined hard negatives (the
node2vec/SPECTER workhorse). Optional aux `MSE(cos(enc(A),enc(B)), soft_score)` on
middle pairs — add only if the middle band proves informative. Keep v1 simple.

## Blockers / scheduling

- PG down now (`.pg:5433 no response`) — needed for triplet mining (citation table,
  173M edges, intent-labeled). Bring up via flake `pg-start`.
- GPU: router holds ~17.8/24 GB (llamactl :11434). Training + bulk re-embed want it
  freed or scheduled when idle.
- Tail cost (any tier): re-embed 3.07M with tuned encoder (~2–4h) + rebuild HNSW (~1–2h).

## Eval

A/B tuned vs current retrieval on the litmus/landmark battery (pool-hit,
landmark-hit, gold gate). Ship only if Pareto (project rule: measure both sides).
