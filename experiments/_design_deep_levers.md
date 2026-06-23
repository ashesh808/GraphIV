# Design: deep levers (experiments 9–12) + what 6–8 tell us

Status 2026-06-23. Assessment of the completed cheap levers (6–8) and the design for the deep
levers (9–12) on the battery. Companion to `tasks.md`.

## 1. Are we in a good direction? (reading 6–8)

**Yes on the objective axis — that's the spine of the paper.** The structural metrics discriminate
cleanly and reproduce every prior finding across 27 topics:
- `n_edges`: full 5589 · no_cluster 2329 · **no_graph 0** — the citation graph (and the topic tree's
  contribution to it) is real and measurable.
- `frontier_count`: **no_graph 65** (vector-only inflates) vs full 36 — the gaming demonstration.
- `n_2026`: frontier_pull **on 1.89 / off 0.00** — structural proof of the delta-coverage component.
- recency sweep: monotonic frontier 3.7→30.8, recall 0.09→0.04 — a clean trade-off curve.
- `num_density` (specificity): no_graph 45.9 vs ~50–52 elsewhere — discriminates.

**Three problems that DON'T bite 6–8 but WILL bite 9–11.** 9–11 test *quality refinement*, not
structural knockouts, so the weak instruments below become the bottleneck:

1. **The LLM judge is saturated near ceiling.** Per-axis means across the 5 ablation configs:
   - `j_coherence` 4.96–5.00 — dead. `faithfulness` 0.95–0.96 — dead as a discriminator (keep it as a
     tripwire only). `j_overall` 4.64–4.90 — compressed.
   - `j_coverage` 4.13–4.65 and `j_lineage` 4.67–4.98 — **the only axes that actually move.**
   - ⇒ For 9–11, an absolute 1–5 judge can't resolve a "slightly better" review. Use (a) `j_coverage`
     + `j_lineage` only, and (b) a **pairwise relative judge** (A-vs-B preference → win-rate), which
     discriminates even at ceiling.
2. **`landmark_recall` is diluted to noise.** Only 3/27 topics have gold canonical sets, so 24 topics
   contribute pure zeros and the 0.07–0.09 aggregate is meaningless in absolute terms (only the
   within-gold-topic contrast matters). ⇒ Report a **gold-only recall aggregate** (mean over the
   gold-bearing topics), separate from the all-topic vector.
3. **[FIXED] Deep config-dir collision.** `deep_loop.py` cfg omitted `critique_k` + `recency`, so
   exp10's k0/k4/k8 all wrote `standard-ppr-deep2-nofig` and clobbered. Fixed to
   `{effort}-{rank}-deep{rounds}-k{critique_k}-r{recency}…`. This was also a prerequisite for the cache.

## 2. Cross-cutting design for 9–12

### 2a. Unified config-cache (the dedup the user asked for)
`runner.run_phase6` currently always recomputes. Add a cache: key = sha1 of
`(question, effort, rank, recency, no_cluster, no_graph, no_frontier_pull, max_rounds, critique_k,
figures, deep)`; a manifest `results/_cache/manifest.json` maps key → out_dir. On hit, skip the LLM
run and re-evaluate from the on-disk `run.json` + `report.md`. **Why it matters:** 9/10/11 share the
exact cell `{standard, deep, rounds-2, k4, figs-off}` — without the cache that's 3× redundant deep
runs per topic; with it, once. Also makes re-runs / metric tweaks free (no recompute).

### 2a-bis. Two-phase driver — batch evaluation by model (the model-thrash fix)
**Problem:** 4 big models share one 24GB GPU (Code=generation, Gemma-4-26B=judge+faith,
Vision=figures+caption-check, nomic=embed), loaded on demand. The current driver interleaves per run
(generate→judge→faith→vision), so each run pays ~2 extra 26B loads (~2-3 min each) just for eval —
~650 loads across 27×12. **Fix:** decouple generation from evaluation.
- **Phase 1 — generate all runs → cache** (Code+nomic; Vision only for the few `figures-on` cells;
  exp9/exp10 are figures-off ⇒ pure Code/nomic, zero Vision thrash).
- **Phase 2 — evaluate cached reports grouped by model:** load `Gemma-4-26B` ONCE → all judge +
  faithfulness + pairwise; load `Vision` ONCE → all caption checks.
- Eval model-loads: ~650 → **2**. This is what makes the all-27 deep sweep tractable.

### 2a-ter. Judge decision (resolved by batching)
KEEP the independent `Gemma-4-26B` judge (NOT the Code generator — independence avoids self-favoring
bias); batching makes its cost ~1 load total, so independence is free. Add a **pairwise (A-vs-B)**
mode in the batched judge pass; report `j_coverage` + `j_lineage` (the only axes that moved in 6-8);
`faithfulness` stays a tripwire, not a discriminator. Drop `j_coherence`/`j_overall` as signals.

### 2b. Deep panel, not all 27
Deep runs are ~11 min each; mechanism levers need *robustness*, not statistical breadth (that's what
6–8 gave us). Define `DEEP_PANEL` (8 topics, spanning the design + all 3 gold sets):
`diffusion, testtime, transformer` (gold) · `gnn, ssm, llm_agents` (foundational/frontier) ·
`diffusion_video, gnn_drug` (compositional). Editable, like `topics.json`.

### 2c. New metrics to add to `_harness/metrics.py`
- `rounds_run` (already emitted) — does the judge actually spend the budget?
- `delta_landmarks` / round — marginal coverage per extra round (the diminishing-returns curve).
- `n_distinct_cited` — distinct valid arXiv ids cited (breadth, ungameable by repetition).
- `j_pairwise_winrate` — from the new pairwise judge (per lever, top condition vs baseline).
- `gold_recall` aggregate (gold-bearing topics only).

## 3. The four experiments

**exp9 — judge-loop rounds (test-time compute).** Lever: `max_rounds ∈ {1,2,4,6}` (extend to show the
saturation point; judge owns early stop). Hold k4, figs-off. Headline: `rounds_run` vs cap +
`delta_landmarks`/round (diminishing returns) + `frontier_count` + pairwise win-rate (rounds-6 vs
rounds-1). Hypothesis: more inference-time compute → more coverage with diminishing returns; judge
auto-terminates before the cap.

**exp10 — critique depth.** Lever: `critique_k ∈ {0,4,8}` (now that the cfg collision is fixed). Hold
rounds-2, figs-off. Headline: `num_density` (specificity), `grounded`, `n_critiques`, `j_grounding`,
pairwise grounding (k8 vs k0). Legacy logged this as a NULL result — design keeps it honest; a null is
a publishable finding (full-PDF critique doesn't beat good abstracts on these metrics).

**exp11 — vision figures.** Lever: `figures` on/off. Hold rounds-2, k4. Headline: `n_figures`,
**`caption_faithfulness`** (the vision model re-checks each caption against its saved crop — a
non-saturated objective metric, the one bright spot in the instrument set), `words`. Already
well-instrumented; just add to panel + cache.

**exp12 — deep dogfood (holistic before/after).** Not a single lever: `before-2023` (single-pass,
indegree, recency 0, frontier_pull OFF — the old default) vs `after-deep` (deep judge-loop, ppr,
recency 0.5, k6, figures on). The long md/tex reviews are the primary artifact; the table quantifies
the jump (n_2026, words, grounded, figures, j_coverage). The deep-showcase already IS the "after"
exemplar; this adds the matched "before."

## 4. Run plan & cost
1. (done) fix deep cfg collision · (todo) add config-cache to `runner.py` · add `DEEP_PANEL` +
   the 5 metrics · widen 9–12 `topic_keys` to the panel · add pairwise judge to `_harness/judge.py`.
2. Run sequentially (single GPU). With the cache deduping the shared cell, est. ~10–12 unique deep
   cells/topic × 8 topics × ~11 min ≈ **~15–18 h** overnight.
3. Each experiment refreshes `results/{metrics.md,ablation.png,README.md}` as 6–8 do; gold_recall and
   pairwise win-rate reported alongside the objective vector.

## 5. Open choices (for the user)
- **Panel size:** 8 (recommended) vs all 27 (≈40 h+, marginal for mechanism levers).
- **Pairwise judge:** add it (recommended — the absolute judge can't resolve refinement) vs rely on
  `j_coverage`/`j_lineage` + objective metrics only.
