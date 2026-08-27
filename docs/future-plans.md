# GraphIV — analysis, limitations & future plans

> **Numbers here rest on the 27-topic battery, which is no longer trusted.** The retrieval
> claims were re-measured on a 60-survey qrels benchmark (`experiments/02-retrieval`) and the
> generation claims were replaced by four reliability experiments
> (`experiments/03-generation`). The limitations and the direction still read true; the figures
> do not.

Synthesis of the deep-lever experiment campaign (experiments 9–12), run across the full **27-topic
battery** on a single 3090 (2026-06-24/25). This is an honest engineering post-mortem, not a pitch:
it records what each lever actually bought, what is still broken, and what to do next. Numbers come
from `experiments/experiment-{9,10,11,12}-*/results/{metrics.md,pairwise.json}`; the per-run reviews
are indexed in `experiments/showcase/deep-levers-index.md` (27 topics · 243 runs).

## Headline results (order-debiased pairwise; absolute LLM-judge is saturated and uninformative)

| exp | lever | comparison | overall | lineage | coverage | grounding | verdict |
|-----|-------|-----------|---------|---------|----------|-----------|---------|
| 9  | judge-loop rounds | rounds-6 vs rounds-1 | **0.78** | 0.78 | 0.67 | 0.63 | real win, **saturates ~round 3** |
| 10 | critique depth (k) | k8 vs k0 | 0.63 | 0.63 | 0.56 | **0.48** | weak: helps narrative, **null on grounding** |
| 11 | vision figures | on vs off | — | — | flat | flat | presentation win, **neutral on text substance** |
| 12 | full deep vs pre-2023 baseline | after-deep vs before-2023 | **0.85** | 0.85 | 0.78 | **1.00** | **decisive end-to-end validation** |

Pairwise win-rate = fraction of 27 topics where the "stronger" condition wins a head-to-head,
order-debiased (forward+reverse pass, disagreement→tie). The absolute 4-axis judge sat at
**4.85–4.94 / 5** across *every* condition in every experiment — it cannot discriminate at this
quality band, so pairwise is the only metric that sees the effects below. **That the absolute judge
is useless here is itself a finding** (see Limitations).

---

## Per-experiment analysis

### exp9 — judge-driven deep loop (max_rounds 1→2→4→6)
- **Real, decisive win:** rounds-6 beats rounds-1 on 21/27 topics overall (0.78), strongest on
  **lineage 0.78** — the developmental-narrative axis that is the project's core claim. Only 2 losses.
- **But it saturates by ~round 3.** `rounds_run` (where the thinking judge *chose* to stop) averaged
  **2.78 at cap-4 and 2.81 at cap-6** — the judge self-terminates around round 3 regardless of the
  cap. So rounds-4 ≈ rounds-6 on every metric (landmarks 151 vs 150, frontier 52 vs 53, j_overall
  4.89 vs 4.94). The monotonic lift is front-loaded: landmarks 77→114→151, frontier 33→46→64 over
  rounds 1→2→4, then flat.
- **Action: default `max_rounds≈4`.** Setting 6 burns compute for ~1 extra landmark. The judge
  owning termination is working as designed; the cap past 4 is mostly inert.

### exp10 — per-paper full-PDF critique depth (k = 0, 4, 8 papers)
- At 27 topics, k8 beats k0 **0.63 overall** — this **refutes** the earlier 8-topic "≈0.50 null."
  But the lift is entirely on the *narrative* axes (lineage 0.63, coverage 0.56) and **grounding is a
  dead heat (0.48 — 9 of 27 ties, 13–5 split).**
- Interpretation: deeper critique reshapes *how the story is told* (it feeds richer per-paper detail
  into compose), but it does **not** change *which papers anchor the review* — grounding is set by
  retrieval/ranking, upstream of critique. 
- **Action: keep a moderate k (4–6); do not max it.** k8 roughly doubles full-PDF cost for a
  narrative-only, grounding-neutral gain.

### exp11 — vision figure gallery (on vs off)
- **Clean qualitative win, neutral on substance.** Figures-on adds **12.4 figures/report at 0.93
  caption-faithfulness** (Vision captions are 93% grounded in the actual figure) and **+36% words**
  (3909 vs 2877). But every *textual* quality metric is statistically identical: grounded 48.2 vs
  47.7, gold_recall 0.92 = 0.92, coverage 4.67 vs 4.65.
- Interpretation: figures make the review a **richer, more complete artifact**, not better
  scholarship. Worth keeping ON as a default presentation feature; it is not a substance lever and
  shouldn't be sold as one.

### exp12 — end-to-end dogfood: full deep pipeline vs a pre-2023 single-pass baseline
- **The strongest result of the campaign.** after-deep vs before-2023 (indegree rank, recency 0, no
  frontier-pull — i.e. "what the tool would have produced before the deep features existed"):
  **grounding 1.00 (27–0, a clean sweep), lineage 0.85, overall 0.85, coverage 0.78 — zero baseline
  wins on any axis.**
- The supporting metric deltas explain why: frontier_count **51 vs 16** (3.2×), grounded citations
  **50.7 vs 29.4** (+72%), recent papers ≥2025 **16.3 vs 0.6** (the baseline structurally cannot see
  the 2025–26 frontier; frontier-pull + topic-adaptive recency is exactly what fixes that), words
  **3921 vs 797**.
- **Honest nuance:** the baseline has *higher* gold-landmark recall (**0.96 vs 0.85**). Indegree
  ranking over classic-era papers naturally recalls canonical landmarks better; the deep pipeline
  spends some attention budget on the frontier and gives a little classic-recall back. This is a
  deliberate, sensible trade (a little canonical recall for 27× more recent coverage), but it should
  be stated, not hidden — and it argues for **prestige-aware ranking** (below) to recover both.

---

## Known defects (each with a proposed fix)

1. **`frontier_year` misfire on sparse / very-recent topics.** `recency.detect_frontier` sometimes
   infers the frontier year as 2026 (or 2025), so `recent_floor` filters the pool down to a handful
   of papers (progsynth k0/k8 → edges=0, pool 8–124; diffusion_audio after-deep → pool 265;
   rl_theorem before-2023 → frontier=1). Result: a stunted report. **Fix:** clamp the detected
   frontier year to `≤ now − 1`, and add a **min-pool guard** that widens the year window / falls
   back to leaf-anchor retrieval when the post-filter pool drops below a floor (e.g. <150).

2. **Long-compose outliner intermittently collapses to a generic 3-section outline.** "Origins /
   Key Advances / Current Frontier" (~14–21k chars) appears even when the round *saturated at 5.0*
   and **all** PDFs were critiqued — seen on progsynth r1, rl_theorem r2/r6/after-deep, gnn_recsys
   k8. It is a non-deterministic miss in the outline LLM call, not a data problem. **Fix:** validate
   the outline (reject the trivial 3-section template; require ≥5 sections / a length floor) and
   **retry** with a stricter prompt; this is the single highest-leverage quality fix.

3. **Truncated / very short opening sections.** Some figures-on reports had a first section of
   ~1000 chars vs ~3000 for the rest (e.g. long_context 1053). **Fix:** per-section min-length check
   with one retry, same machinery as #2.

4. **PDF critique/caption drops from MuPDF.** `MuPDF error: could not parse color space` on
   malformed arXiv PDFs causes "critiqued/captioned N−1/N" (rl_theorem, diffusion_driving, etc.).
   Non-fatal but loses a paper. **Fix:** wrap the PDF read in a sanitize/fallback (pikepdf
   re-save, or skip-and-substitute the next-ranked paper so k stays whole).

5. **Gemma-4-26B-Code proxy-connection blips on model swap.** Recurrent
   `InternalServerError: proxy error: Could not establish connection` during model swaps; the
   pipeline self-heals via `/router/restart → 200`, so benign, but it adds latency. **Fix:** a warm
   pool / keepalive on the router so the Code model doesn't cold-swap mid-pipeline.

6. **No prestige / citation-count weighting in ranking.** Obscure very-recent papers are cited with
   the same authority as landmark papers (e.g. workshop-tier 2025 SSM papers alongside S4/Mamba).
   This also drives the exp12 gold-recall dip. **Fix:** blend a citation-count / age prior into the
   ranking score (PPR already exists; add a log-indegree term) so canonical work is weighted up.

7. **Citation-format inconsistency.** Reports mix `[arXiv:XXXX]` and bare `arXiv:XXXX` within one
   document. **Fix:** normalize in the hallucination post-check pass (already iterates every cite).

---

## Limitations (honest scope of these results)

- **Gold metrics are thin.** `gold_recall` / landmark / spine recall only exist for the **3
  gold-bearing topics** (diffusion, test-time, transformer); the other 24 report 0.0 by absence, not
  by failure. Gold coverage is the #1 evaluation gap.
- **LLM-judge self-preference + saturation.** The absolute 4-axis judge is pinned at the ceiling
  (4.85–4.94) and shares a model family with the generator, so it likely flatters in-distribution
  prose. Pairwise mitigates *ordering* bias but not *family* bias — a different-family judge and/or
  human eval is needed to close this.
- **Single-GPU model-swap thrash is the dominant runtime cost.** nomic (~18 GB) is reloaded on
  *every* retrieval round and swapped against the ~17 GB LLM; the deep loop pays this 1–6× per cell.
  This, not the LLM calls, is why a 27-topic deep sweep takes hours.
- **Recency-as-importance bias.** Without prestige weighting (defect #6) the pipeline treats "recent"
  as "important," occasionally elevating minor frontier papers and **omitting genuine landmarks**
  (e.g. Mamba-2 / SSD `2405.21060` was absent from the SSM review even at deep6).
- **Sample is modest and CS-skewed.** 27 topics, all ML/CS, 3 with gold sets. Findings are
  directionally solid but not a broad benchmark yet.

---

## Future plans

### Immediate (cheap, high-leverage)
- **Set `max_rounds≈4` as the deep default** (exp9: rounds-6 buys ~nothing over 4).
- **Default vision figures ON** (exp11: free completeness, faithful, neutral risk).
- **Keep critique `k≈4–6`**, not maxed (exp10).
- Land defect fixes #1 (frontier floor / min-pool guard) and #2 (outline validation+retry) first —
  they remove the only systematic quality failures observed across 243 runs.

### Phase B2 — analysis experiments (the remaining built suite)
- **E1** 5-layer resolver: resolution-success by topic / category / era (needs the full-corpus stats
  pass; current `citation_stats/summary.json` is a partial 612k-paper run).
- **E2** labeling quality: per-class confusion + precision/recall/F1 for the intent (6-way) and
  polarity (3-way) heads, teacher↔student agreement on the held-out split now; human-gold later.
- **E3** graph-structure viz: degree distributions, components, category mix, temporal growth.
- **E4** clustering comparison: shipped density-aware bisecting tree vs legacy kmeans→DBSCAN vs
  HDBSCAN, on coherence / no-noise-bucket / downstream retrieval edges.
- **E5** topic-tree viz/analysis: leaf-size distribution, depth, coherence, 2D projection.

### Phase C — research-paper / open-resource layer
- **Baselines** in `_harness`: a **STORM-style** (pure-retrieval, no graph) and a **GraphRAG-style**
  (LLM-extracted entity graph) condition, so the central claim — *citation-graph grounding beats
  text-extracted-graph and pure retrieval on faithfulness / recency / lineage* — is **tested, not
  asserted**. (exp12 already shows deep ≫ our own pre-graph baseline; the external baselines are the
  harder, fairer comparison.)
- **Formalize lineage/developmental metrics:** spine / main-path recall, chronological faithfulness,
  frontier coverage — the axes where this system is differentiated and where exp9/exp12 already show
  the largest, most reliable wins.
- **~1000-label human gold benchmark** via a doom-scrollable web labeling tool (FastAPI + one HTML
  page over the PG `gold_label` table) → unlocks E2 stage-2 human PRF and widens gold coverage
  beyond 3 topics.
- **Prestige-aware ranking** (defect #6) to recover gold-landmark recall without sacrificing frontier
  coverage — directly addresses the one axis where the deep pipeline regressed.
- **Resource release:** the sub-100GB `pg_dump` (typed citation graph + embeddings + topic tree) +
  the reproducible builder + the E2 edge-quality benchmark.
- **Small expert human-eval (N≈15–20):** "which review tells the better-grounded developmental
  story" vs the STORM/GraphRAG baselines — the evidence the LLM-judge cannot provide.

---

*Generated 2026-06-25 from the 27-topic exp9–12 deep-lever campaign. Per-run reviews:
`experiments/showcase/deep-levers-index.md`. Roll-ups: `experiments/experiment-{9,10,11,12}-*/results/`.*
