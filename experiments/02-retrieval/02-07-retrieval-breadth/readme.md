# 02-07 — retrieval breadth & landmark budget (the `ef_search` bug + the coupled floor/m package)

**Hypothesis:** the "highly relevant papers never become landmarks" failure (02-06's per-paper
autopsy) is dominated by *retrieval breadth and budget constants*, not by the selection
objective — and the three knobs (vector-channel width, ancestor cosine floor, landmark budget m)
are COUPLED: each is only safe or useful in combination with the others.

**The bug.** pgvector's HNSW index returns at most `hnsw.ef_search` rows regardless of the
query's `LIMIT`, and the parameter was never set — so since the 2026-06 PG consolidation every
vector KNN returned ≤40 rows (the pgvector default). `n_pool=400/600` was fiction; pools were
carried by the lexical RRF channel (fine for short battery topics, catastrophic for long
multi-sentence questions whose BM25 title match is thin: litmus pools ran 60–137 vs the
intended ~500). Verified directly: `SELECT ... ORDER BY emb <=> q LIMIT 2000` returned exactly
40 rows; after `SET hnsw.ef_search = 1000` (the parameter's maximum) it returns 1000.
**Fix shipped in `Store.__init__`** (one session-scoped `SET` on connect).

**Why each condition exists** (one decision per condition):

| condition | ef | floor | m | justifies |
|---|---|---|---|---|
| A_old_shipped | 40 | 0.35 | 40 | pre-fix production baseline (reproduces the 02-06 ppr row) |
| B_ef_fix | 1000 | 0.35 | 40 | the bug fix alone: pool-hit jumps, but landmark-hit DROPS — bigger pools make m=40 more competitive, so ef cannot ship alone |
| C_floor_only | 1000 | 0.30 | 40 | floor relaxation without budget: extra ancestors dilute gold recall at m=40 — so the floor cannot ship without the m bump |
| D_shipped | 1000 | 0.30 | 60 | **the shipped package**: gold gate must hold 0.753/0.917 |
| E_paid_upgrade | 1000 | 0.30 | 80 | the next tier up: better hits AND gold, at ~2× grading (candidates=4m) — documented, not shipped as fast-tier default |
| F_floor_abl | 1000 | 0.35 | 60 | floor ablation at the shipped budget: BYOL (cosine 0.340, graded foundational/+2 when admitted, PPR rank 4) misses the pool by 0.010 |

**Why floor 0.30:** BYOL is the vocabulary-shift case — a pre-JEPA foundational paper whose
abstract never says "JEPA"; embedding-invisible (corpus KNN rank >1000), reachable ONLY via the
ancestor channel (cited by 57/240 of the live JEPA cohort), and blocked by the 0.35 floor by
one hundredth. The floor's original job (keep famous cross-field hubs out of landmarks) is now
done by the reader: an admitted junk hub grades −2, leaves the landmark ranking, and stays a
graph connector. The 02-03 sweep that set 0.35 ran under the ef=40 cap and predates the reader.

**Why m=60 (fast tier):** grading cost scales with m only (`candidates = top-2m cosine ∪
top-2m in-degree`), NOT with ef or pool size — so the ef fix is free and the budget is the real
cost dial. m=60 is the largest budget with no measured cost beyond ~1.5× grading calls.

**Results** (30 topics = 27-topic battery + 3 adversarial litmus; gold = grader-independent
canonical/spine sets; see `results/metrics.md` + per-paper outcomes in `results/metrics.json`):

| condition | ef_search | floor | m | landmark_recall_gold3 | spine_recall_gold3 | relevance_rate | litmus_pool_hit | litmus_landmark_hit | frontier_mean | edges_per_landmark | wall_seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A_old_shipped | 40 | 0.35 | 40 | 0.753 | 0.917 | 1.0 | 0.857 | 0.524 | 18.0 | 4.75 | 34.6 |
| B_ef_fix | 1000 | 0.35 | 40 | 0.753 | 0.917 | 1.0 | 0.952 | 0.476 | 18.8 | 4.78 | 114.7 |
| C_floor_only | 1000 | 0.3 | 40 | 0.711 | 0.85 | 1.0 | 1.0 | 0.476 | 17.5 | 4.79 | 117.4 |
| D_shipped | 1000 | 0.3 | 60 | 0.753 | 0.917 | 1.0 | 1.0 | 0.619 | 29.4 | 6.19 | 117.4 |
| E_paid_upgrade | 1000 | 0.3 | 80 | 0.819 | 0.917 | 1.0 | 1.0 | 0.714 | 44.0 | 7.03 | 117.4 |
| F_floor_abl | 1000 | 0.35 | 60 | 0.753 | 0.917 | 1.0 | 0.952 | 0.571 | 31.3 | 6.12 | 114.7 |

Reading the table row-by-row: **A** reproduces the 02-06 ppr baseline exactly (validating the
harness). **B** proves the coupling: the bug fix alone lifts pool-hit 0.857→0.952 but landmark-hit
FALLS 0.524→0.476 (bigger pools, same 24 non-reserved slots — even vLLM drops to rank 26/24).
**C** proves the other coupling: the floor alone at m=40 costs gold (0.753→0.711, spine
0.917→0.85) — the admitted ancestors absorb early PPR ranks. **D** (shipped) recovers both: the
gate holds exactly and litmus landmark-hit reaches 0.619 with pool-hit 1.0 (BYOL: in pool,
graded foundational/+2, PPR rank 4). **F** isolates the floor's benefit at the shipped budget:
identical gold, but pool-hit 0.952 — the missing 0.048 is exactly BYOL. **E** shows the budget
curve is still rising (gold 0.819) at ~2× grading cost; standard/deep tiers (m=80/120) already
sit there. wall_seconds is retrieval+selection for all 30 topics (grading excluded, cache-hot):
the uncapped channel costs ~3.3× on retrieval (~2.7s→~3.9s/topic) — negligible vs any LLM stage.

**Conclusion.** Shipped D (ef=1000 + floor 0.30 + fast m=60): litmus pool-hit 0.857 → 1.0,
landmark-hit 0.524 → ~0.62, gold gate held. E documents the paid upgrade path. The residual
litmus misses (KIVI/Quest/CLA/SimPO/KTO/IPO at PPR rank 63–97 with rel=+2) are the
directionally-starved-leaf class — parametrically unreachable; see the facet-quota /
expansion-channel follow-ups in the project notes.

Run: `uv run python experiments/02-retrieval/02-07-retrieval-breadth/run.py` (grades shared via
`grade_cache.db`; ~20 min warm-cache on the 3090).
