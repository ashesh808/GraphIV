# GraphIV — project status snapshot

_Last synced 2026-07-28 from agent memory + `scratchpad/experiment-finalization.md` + live tree._

**What it is.** A knowledge-graph deep-research engine over the whole arXiv corpus (3.10M papers,
178.7M intent-typed citations). Public as **GraphIV** (graph + ar**Xiv**), GPLv3, at
`ssh://forgejo@metatron/kkuroma/GraphIV.git` (internal id stays `arxivkg`). A question →
retrieve/rank/extract/compose → grounded, cited literature review (md + tex + bib + figures + graph).

**Where we are.** The system works and is deployed (live librechat+MCP demo, read-only public
mirror). The current phase is **finalization**: turning a working dev pipeline into a defensible
research project where *every hardcoded number is deliberate* — either measured, derived from a
named profile, or explicitly flagged-arbitrary-and-isolated. Nothing below is "ship a feature";
it's "justify or delete each knob, then rerun cleanly."

The forward plan the user set: **one more rerun → redesign the `experiments/` organization →
final rerun.** The AI runs experiments as a *guide for how the user compiles the paper*; the user
writes the paper.

---

## The three-run structure

Everything is organized into three phases. The `experiments/` tree already mirrors this
(`01-preprocessing/`, `02-retrieval/`, `03-generation/`). The finalization doc defines a leaner
*Run N.x* plan that supersedes/reruns the old numbered experiments.

### 1. Preprocessing — build the KG (raw arXiv → resolved citations → embeddings → topic tree)
Design **locked**. Reruns planned, not redesigns.
- **1.1 resolver quality** ✅ approved — census (SQL `GROUP BY method×category×era` over 178.7M
  rows) + precision sample (~100/rung, LLM-verify, human only on fuzzy-title disagreements) →
  graph-wide wrong-edge rate.
- **1.2 labeling quality** ✅ approved, **REDO** — human gold-1000 (intent+polarity, doomscroll UI),
  600/400 split, macro-F1; **DSPy GEPA** APE loop (old teacher vs evolved vs student). Re-teacher +
  re-distill only if it wins (cost-gated).
- **1.3 topology census** — rerun old 01-01/01-03 SQL on 3.10M; add degree tails, giant component,
  intent×era. No new design.
- **1.4 cluster/topic-tree worth** ⏳ — decided by the `no_cluster` battery arm in Run 2. If the
  leaf anchor loses, phase-5 exits the retrieval path.

### 2. Retrieval — FINALIZED architecture (2026-07-20); constants audit = `scratchpad/RETRIEVAL_AUDIT.pdf`
Six modular steps: **V∪L → reranker → topic map → injection → grading → selection**.
- Reranker = swappable slot, RRF `1/(60+rank)` = default impl (not the definition).
- **Frontier line = mean+1SD** of the core-cohort year histogram — kills `_WINDOW`/`_ACTIVE_SHARE`/
  `_MAX_SPAN`. Precursor-by-distribution REJECTED (pool left edge is vocabulary-censored); past
  enters via citations only (ancestor step, floor 0.30, kept + measured).
- Grading renamed m/2m, **m=200** → candidate set ≈ whole pool (eligibility question dissolves);
  full-text grading REJECTED (ctx + prompt-processing cost). Abstracts only.
- **Selection = "Leyline"** (the magnetic Monte-Carlo BFS sampler, user's own algorithm; file
  `trajectory_select.py`, rename pending) / PPR hybrid / pure-Leyline, q×γ swept. Empty-magnet
  guard = warn + PPR fallback.
- Run-2 experiments: 2.1 channels (n_pool×k_lexical, cheap) · 2.2 reranker (RRF_K) · 2.3 topic map
  on/off (= 1.4 verdict) · 2.4 injection (+1SD vs old, ancestors-off arm) · 2.5 grading accuracy
  (optional, piggybacks 1.2 UI) · 2.6 selection (q×γ, pure-Leyline endpoint).
- **External validation (silver qrels):** trajectory beats PPR **6/6 cells** on landmark core-ref
  recall at ≥2/≥3 mentions (standard tier, 3 capped surveys). Confirms the sampler independently.

### 3. Generation — design FINALIZED (2026-07-20), code still skeleton
Module `graphiv/generate/` mirrors `retrieve/` (plural `.py` = swappable Protocol family). **Seven
stages**, all locked:
`loop (harness) → schema+extract → digest → write → judge → ground → render`.
- **critique CUT** (03-09: pairwise k8-vs-k0 = 2W/2L/4T coin-flip, faithfulness+lineage tick *down*).
- **digest LOCKED** — timeline + intent-grouped adjacency + hub marks + tensions; NO taxonomy
  (topic tree too coarse, raw facets too fine — canonicalization deferred behind a measured need).
- **write LOCKED** — sectioned compose (03-07 winner); number+citation verification MOVED to ground;
  all length knobs → ONE "research depth" profile.
- **judge LOCKED** — 6 axes (grounding/coverage/lineage/coherence/frontier/focus 1-5) + saturated +
  gaps; Gemma default. Self-grading bias cancels in within-model A/B, bites only the termination bool.
- **loop LOCKED** — plain async harness (NO agent framework); gaps re-enter through the SAME
  `Retriever.retrieve(gaps, entered_via="gap")`, killing the `_inject_gap_ids` fake-score side channel.
- **ground LOCKED** — the single verification home: mechanical id-grounding (fuzzy-correct → corpus-
  verify → strip fabricated; every surviving id exists by construction) + number-check.
- **render LOCKED** — independent emitters: markdown / latex (KEEP TeX accents in .bib) / figures
  (role-gated vision gallery) / graph (deterministic scatter x=month, y=cosine).
- Libs: **pydantic** (all LLM outputs, dynamic model from schema) + **dspy** (every LLM stage: typed
  signatures, GEPA reuse from 1.2, model-as-arg, built-in cache replaces 3 sqlite caches).
  **pydantic-ai NOT used** (loop is deterministic, not an LLM-driven agent).
- Run-3 experiments: **3.1 judge validity** (keystone — judge vs user's pairwise ranking via
  doomscroller) · 3.2 critique ✅ resolved-cut · 3.3 rounds curve (1/2/4/6) · 3.4 compose format
  (only if an itch).

---

## The "all numbers deliberate" ledger (generation)
Every hardcoded gen number, by disposition:
- **→ research-depth profile** (deliberate by construction): sections 5-8, words/section 350-600,
  coverage/tens/recent caps, max_rounds, M_GROW 40, M_MAX 260, GAP_POOL 150, frontier_pull 30.
- **ARBITRARY, flagged** (the only genuinely-unmeasured knobs): salient char-budgets
  **abstract 600 / intro 700 / method 900 / results 700**, value-clip 300, judge digest-trunc 12000
  — isolated behind the `FullTextProvider` slot; tuned only if a report reads thin, not an experiment.
- **model-as-arg** via dspy LM: Gemma-4-26B (extract) / Gemma-4-26B-Code (schema/write/judge) / vision.
- **PROVEN, locked** (don't touch): sectioned compose (03-07), judge 6-axis, skeleton-in-loop split,
  digest adjacency roles, critique-cut (8-0-0 / pool~1700 / 03-09).
- **low-stakes keep**: temps, max_tokens, concurrency, edit-cap 2, number+unit regex, fig-cap 14.

---

## Codebase status — `graphiv/` package (LIVE; pyright/ruff/black clean; `phases/` untouched, prod unaffected)
- **core/** — `config.toml` + store/embed/llm/models. New.
- **retrieve/** — six steps FULLY REIMPLEMENTED per the finalized design (+1SD frontier, m=200,
  Leyline naming, empty-magnet guard, telemetry). Live-smoke-tested steps 1–4.
- **download/ + preprocess/** — PORTED (wiring-only, logic verbatim; `Downloader`/`Preprocessor`
  composers). Style debt paid when Run 1.x touches each module.
- **generate/** — DESIGN FINALIZED, code still SKELETON. Build gated on Run-3 verdict.
- **serve/** — skeleton.
- **tools/doomscroll/** — labeling UI (JSONL + `--to-pg gold_label`), axes configurable. Serves
  both 1.2 (labeling gold) and 3.1 (pairwise report ranking).

**Existing `experiments/` results** (measured, but some on the pre-consolidation "dead stack";
audited in `scratchpad/EXPERIMENTS_AUDIT.pdf`): 01-01…01-05, 02-01…02-07, 03-01…03-11 all have
`results/`. Rerun shortlist from the audit — HIGH: 02-07 (regression harness), 03-05 (delta
retrievability); MEDIUM: 03-02, 02-01, 01-01/01-03 censuses; SKIP: superseded (02-02/03/04, 03-06)
+ nulls. **Awaiting the user's audit verdicts on which to rerun.**

---

## Infrastructure / deployment
- **Single store** — project-owned Postgres + pgvector at `./data/pg` (db `arxivkg`, socket peer-auth,
  port 5433). Holds `paper` / `citation` / `paper_meta` / `paper_embedding` (sym, demoted to research/
  A-B) / **`paper_embedding_asym`** (halfvec, THE prod space) / `paper_topic` / `leaf` / `gold_label`.
  Neo4j + the global `arxiv-citations` PG are retired. `/Vault` deprecated.
- **Embedding is an endpoint** — no in-process SentenceTransformer; queries/deltas hit the
  `llama-embed` systemd unit (nomic-embed-text-v2-moe f16 GGUF, `--embedding --pooling mean`,
  client-side token-truncation via `/tokenize`). Parity vs ST cosine >0.999.
- **Delta re-ingest DONE (2026-07-15)** — new **phase-0** wgets the Kaggle zip unauthenticated;
  chain 0→5 idempotent; corpus 3.07M → 3.10M. Two consolidation bugs fixed (`paper.id` identity,
  `stage_meta` delta-awareness).
- **Live demo** — librechat + MCP on zaphkiel; tailnet `graphiv.zaphkiel` (full) + public
  `graphiv.kuroma.dev` (read-only, caddy-gated). Research Library dashboard (`components/webui.py`).
- **Homelab** — zaphkiel (this box, 3090, the stack) / metatron (forgejo, to leverage) / raziel.
  nixos-configs, sops, tailscale.

---

## Open items / awaiting the user
1. **Experiment reorg** — map the finalized Run 1.x/2.x/3.x plan onto the `experiments/` tree
   (retire superseded folders, rename to the three-run skeleton). User drives this next.
2. **Rerun verdicts** — which of the existing experiments to rerun on the 3.10M/asym stack.
3. **Run-3 approval** — 3.1 judge-validity is the keystone; 3.3 rounds curve; 3.4 optional.
4. **generate/ build** — gated on the Run-3 verdict; skeleton only today.
5. **20-survey silver-qrels battery** → Consensus-friend demo review → paper narrative rewrite →
   Yizhou Sun outreach ([[user_ucla_mscs]] — incoming UCLA MSCS 2026-07, lab-fit).
6. **Not-yet-coded**: trajectory empty-magnet guard (retrieve/ has it; verify phases/ path), abstract-
   derived question generator, battery driver, GEPA harness, run-1.1 census/precision scripts.
7. **Parked**: `nomic-arxiv` LoRA (DEAD-END track-1, do NOT train); `paper_fulltext` self-contained
   profile (storage discussion, "team will discuss"); PG fold into system `services.postgresql`
   (plan-only, do NOT execute until asked).

---

## Standing conventions & gotchas
- **Measure before shipping** — prototype + measure both sides; ship only Pareto wins; tradeoffs are
  discuss-not-change. PPR-vs-set-coverage is SETTLED (02-06) — do not relitigate.
- **Commit/push only when explicitly asked.** Large in-flight uncommitted diffs exist in `phases/`
  (trajectory_select + pipeline/webui/serve_mcp/store/config, cap feature, embed-endpoint cutover) —
  **do not touch/revert** the user's in-flight `phases/` work. `data/pg.password` is an uncommitted secret.
- **Kill scratch servers by PID** — `pkill -f serve_mcp` also hits the prod `graphiv-mcp.service`
  (no auto-restart, needs interactive sudo). Verify `systemctl is-active graphiv-mcp` after cleanup.
- **User handles ALL sudo.** LLM health checks via `/v1/models` or `nvidia-smi`, never chat.completions.
- **Style**: plain language, prose over popups, minimal deliberate comments, own errors plainly
  (the word "fair" is banned when corrected). Refine phase-6 from real report outputs, not metrics.
- **Kaggle TeX accents** (`G\^arbacea`) — never strip backslashes in `.bib` fields.
