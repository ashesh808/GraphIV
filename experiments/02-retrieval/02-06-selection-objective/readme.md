# 02-06-selection-objective

**What:** the pool->landmark selection objective on trial — PPR as a contestant, not the
incumbent. Motivated by adversarial dogfooding (SimPO/KTO never became landmarks for the RL
question): is item-wise citation centrality the wrong objective vs set-coverage selection
(facility location / MMR / cluster-proportional)? Six arms over an identical front-end (pool +
0.35 ancestor gate + reader grades + fusion + frontier reservation), scored on gold recall (the
gate), relevance, pool coverage, cluster recall, named-paper litmus hits at BOTH boundaries
(pool vs landmark), frontier count, edge density, wall time. 27-topic battery + 3 adversarial
litmus questions.

**Conclusion: PPR is VINDICATED — it keeps the job.** Gold recall: ppr **0.753/0.917** vs
facility 0.436/0.467, fused_topk 0.314/0.450, mmr 0.300/0.367, proportional 0.325/0.450. The
"rich-get-richer" structural bias is precisely the mechanism that recovers foundational lineage
(canonical/spine papers are low-cosine, high-structure ancestors that every pure-semantic arm
drops), and its old noise problem is already gone — relevance_rate is 1.0 on every arm because
fusion (02-05) handles precision. The ppr_facility hybrid trades gold recall (0.686) for ~nothing
(pool_coverage 0.840 vs 0.836; cluster_recall 0.930 vs 0.923): NOT Pareto. Litmus landmark hits
tie ppr = facility = 0.524 — set-coverage buys nothing even on the adversarial questions.

**Where the "highly relevant papers rejected" failure actually lives** (per-paper autopsy):
1. **Pool-miss** — SimPO, CLA, BYOL never reach the pool at all (retrieval breadth, not
   selection; pool_hit caps every arm at 0.857).
2. **Lukewarm grade** — KTO and IPO are in-pool but graded rel=1 ("alignment, not reasoning");
   under budget pressure every arm drops rel-1 for rel-2 papers. The reader under-grades
   question-NAMED entities (the question says "DPO and its variants").
3. **Budget pressure** — KIVI and Quest (rel=2) are missed by ppr AND facility at the fast-tier
   m=40; the deep tier's m=120-260 takes them (both were landmarks in the live deep runs).

None of these is fixed by changing the selection objective; all three are addressed by the
Part-1 judge fix (gap-ids: the context-aware judge names the missing papers and they are
force-injected corpus-verified), plus possible follow-ups: retrieval breadth for (1), a
question-entity grade floor for (2) — measure before shipping either.

Caveat: litmus pools ran small at the fast tier (60-137); production deep runs carry 300-1700
with gap expansion, so absolute litmus numbers understate production, but arm-relative
comparisons hold (identical front-end per arm).

Run: `uv run python experiments/02-retrieval/02-06-selection-objective/run.py` (grades shared
with 02-05/production via `grade_cache.db`; selection arms live in
`phases/phase-6/components/landmark_select.py`).

---

**2026-07-07 addendum — verdict re-checked on UNCAPPED pools.** The original run (and every
experiment since the PG consolidation) executed under an unnoticed `hnsw.ef_search=40` default
that truncated every vector KNN to 40 rows (see 02-07-retrieval-breadth for the bug and its
fix). Re-running all six arms at ef=1000 (pools 42-503 -> ~470-510) STRENGTHENS the verdict:
ppr gold recall 0.711-0.753 vs facility **0.297** (was 0.436), mmr 0.258, fused_topk 0.150,
proportional 0.356 — the embedding-coverage objectives collapse as pools grow (more semantic
distractors for similarity-coverage to waste slots on), while PPR's lineage-recall mechanism is
pool-size-robust. relevance_rate stays 1.0 on every arm. The pool-miss class (1) is now closed
by 02-07 (litmus pool-hit 1.0); the budget class (3) is addressed by the fast-tier m=60 shipped
with it; the residual misses are rel=+2 papers at PPR rank 63-97 (directionally-starved recent
leaves) — a structural, not parametric, gap.
