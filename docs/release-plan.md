# GraphIV release plan

Converged plan (from `reply.md` + vetting, 2026-07-03). Remote: `ssh://forgejo@metatron/kkuroma/GraphIV.git`.
Name: **GraphIV** (graph + ar**Xiv** — the IV is arXiv's tail, same wordplay lineage as arXiv itself).
Prose uses GraphIV; internal identifiers (`arxivkg` DB name, DSN env var, dump filename) stay as-is.

## STATUS (2026-07-03, all pushed to main through `3354376`)

Steps 1–6 **done**; step 7 done except the two user-side items + the paper narrative:
- ✅ 1 pre-push batch → `35d74a2` · 2+3 mechanical guard + bibtex + lazy fetch → `88bec7c`
  · 4 judge robustness → `83b75f7` · 5 floor sweep + authors backfill → `8479102`
  · 6 MCP + dump regen + cold timing → `7aae766` · 7 dogfood + h2h GraphIV side → `1267832`, `3354376`
- **Headline numbers now:** flagship pairwise **8/0/0 on ALL axes, 3 judges, untruncated**
  (`deep-research/results/multi_judge.md`; old 5/2/1 was a 16k-truncation artifact); 0.35 ancestor
  floor = max-precision edge of a 0.25–0.35 recall plateau, shipped (02-03); h2h GraphIV side
  **267/267 citations verified, 0 fabricated, 40× 2026 papers** (`deep-research/results/h2h/`);
  cold-cache effort-4 = **8:38**; dogfood exhibit committed (`deep-research/results/dogfood/`).
- **User queue:** (a) run the 5 h2h strings in Claude+Gemini deep research (strings + protocol in
  `results/h2h/graphiv_counts.md`; decline refinement; save outputs, then `h2h_verify.py` on them);
  (b) HF upload of `data/release/graphiv-2026-07-03.dump` (23 GB — the Jun-22 dump is superseded,
  deletable); (c) librechat-on-zaphkiel nix service (MCP config in `docs/restore.md`).
- **2026-07-11 MCP research-reuse update** (post-`3354376`, tool surface changed): runs addressed
  by `research_id` (= slug, optional `slug/config`); `get_report`/`ask_report` →
  `retrieve_research(research_ids)` / `ask_research(research_ids, question)` (1-3 ids, cross-report
  synthesis); new `similar_reports` + a `deep_research` guard that LLM-matches the question against
  past runs and offers reuse before burning a GPU run (`force_new` overrides). Tool list in
  `docs/restore.md` + CLAUDE.md.
- **Next Claude deliverable:** full paper narrative rewrite for user veto (user explicitly asked);
  best written after the commercial h2h outputs land so the comparison table ships in one pass.

## STATUS (2026-08-27) — version candidate

The tree is version-ready and uncommitted. Three things changed since the block above.

**The package refactor landed.** `phases/` is gone, its code lives in `graphiv/` behind
`scripts/` entrypoints, and `tests/` now holds 62 unit tests that need no database. Five gates
run clean: ruff, black, pyright, import-linter, pytest, plus the comment linter.

**Retrieval became modular and mode-driven.** `graphiv/retrieve/api.py` defines the contract
(`PoolBuilder`, `Reader`, `Selector`, `Retriever`) and `build.py` assembles a pipeline from
registry names. One `Recipe` drives every selector, so the five hand-written rankers collapsed
into a score function plus two flags, verified bit-identical against the old code on 60 frozen
pools for four of five arms. `refine_question` now tags each candidate `survey` or `frontier`
and `deep_research` takes that mode, so the ranker is chosen from the question rather than
defaulted.

**Phase 3 was rebuilt around reliability.** Eleven lever experiments became four, all on one
metric: is a sentence backed by a paper.

| number | value |
| --- | --- |
| cited sentences supported | 0.714 Gemma, 0.744 Qwen, agreeing on 90.6% (kappa 0.762) |
| broken citations the checker approves | 0.153 against 0.714 for real ones |
| sentences carrying a citation | 818/1372 = 0.596 |
| effect of the citation graph on any of the above | none |

**Still user-side:** the two items above (commercial h2h, HF dump upload), plus
`~/System/nixos-configs/parts/services/graphiv.nix` still pointing at `phases/phase-6/serve_mcp.py`
instead of `scripts/serve.py`, which crash-loops the unit on restart.

**Known gaps, recorded not hidden:** how many uncited sentences invent something is unmeasured
and unmeasurable by prompt (two schemes failed a second judge, the second at kappa 0.003), and
`M_SCALE = 1.3` is hand-set, shortening a deep frontier run from 240 landmarks to 156 without a
re-measurement.

## Prod deployment plan (2026-07-16)

Machines: **zaphkiel** (dev, 20 TB vault) · **metatron** (NAS, tailnet) · **prod** (10 TB, NO
tailscale). Measured store (zaphkiel `vault/research/arxiv`): PDFs **5.6 TB** + HTML **489 GB**
+ 48 GB misc = **~6.1 TB** total (pool at 8.93/20 TB).

**Decision: carry everything to prod — no mirror, no fetch.py changes.** Full store (~6.1 TB)
+ PG restore (~105 GB) + nomic model ≈ **6.3 TB**, fits prod's 10 TB with ~3.7 TB headroom.
Runs are fully local/on-prem; the existing lazy arXiv fetch stays as delta backfill only.

Transfer plan (2026-07-16): (1) scrub zaphkiel's `vault` (May-25 scrub logged 9 unrepairable
errors — single vdev, no redundancy; likely non-ECC RAM or link glitch, never recurred);
(2) re-download any flagged arxiv files (all re-fetchable), `zpool clear` if stale hex entries
linger; (3) rsync (not zfs send — path granularity, and the store spans a shared dataset) to
**prod** (ECC + raidz: full end-to-end integrity, self-healing) and to **metatron**
(raidz NAS → canonical backup). Zaphkiel (single vdev, non-ECC) is then the weakest copy —
acceptable: it's the build machine and everything is re-fetchable. Wire size ≈ 6.5–7 TB logical;
`rsync -aHW --partial --info=progress2`, no `-z` (PDFs incompressible). Scrub prod once after landing.

Rejected alternatives (kept for the record):
- ~~Metatron as a public arXiv mirror~~ — legality: most papers carry arXiv's default
  non-exclusive license (distribution rights are arXiv's only); a public unauthenticated mirror
  infringes. Private token-gated serving to our own machines would be fine (it's just internal
  transfer), but is unnecessary now.
- ~~PDF-only unification (GROBID/LaTeXML)~~ — GROBID mangles citations; local LaTeXML is
  expensive for marginal gain. Moot: HTML is only 489 GB, not worth dropping.
- ~~600 GB slim prod (local HTML + PDF mirror)~~ — viable fallback if prod ever shrinks:
  extraction is HTML-driven; PDFs serve only critique (~8/run), figures, and the reading panel.

## Positioning (pitch order)

1. **Local + verifiable** — one consumer GPU, open weights, a 17 GB dump; every citation resolves
   against the corpus *by construction* (after step 2).
2. **More up-to-date** — verified 2026 arXiv papers per report (9.0/topic vs 0 for the old baseline;
   head-to-head vs commercial deep research in step 7).
3. **Fast** — minutes per deep report on a single RTX 3090 (quote the *cold-cache* number, step 6).

Never claim bare "better than Gemini/Claude deep research" until the pairwise comparison (step 7+) exists.

## Step 1 — pre-push batch (blocks the push)

- [ ] Refresh stale readmes against fresh `results/`: `experiments/README.md`,
      `experiments/deep-research/README.md` (23/4/0 → 5/2/1 n=8, 3.3 → 9.0 2026/topic),
      the removed 03 suite (0.78/27-topic → fresh), audit all others.
- [ ] Name sweep: GraphIV in README/paper/docs prose; arXiv-tail etymology in README line one.
- [ ] Consolidate `phases/global-config.json`: retire the dead `postgres.dsn=arxiv-citations` (point at
      the arxivkg store, env-overridable); mark `/mnt/Vault-Academics` embedding paths build-time-only;
      move the Haruhana palette into the repo as `theme.json` (credit
      https://git.kuroma.dev/kkuroma/shunka-shuutou-theme in docs).
- [x] Every experiment's measurement code now lives in its own `src/`, and `scratchpad/` is gone.
- [ ] `docs/restore.md`: dump → `pg-init` → `pg_restore` → any OpenAI-compatible endpoint (model
      aliases documented; llama-router: https://git.kuroma.dev/kkuroma/llama-router) → serve.
      Placeholder link for the dump download (upload later).
- [ ] Probe llama-router at :11434 (availability + ctx limits) — informs the step-4 judge cap.
- [ ] Lint gate (`ruff` / `black` / `pyright`) then push to the forgejo remote.

## Step 2 — hallucination mechanics (makes claim 2 mechanical)

Order matters: (1) **fuzzy-correct** — an unknown id within edit distance 1–2 of a digest-pool id is a
typo, fix it in place; (2) **corpus-check** the rest against `paper`; (3) **strip** survivors;
(4) one **bounded repair pass** — tell the writer which claims lost citations, re-attribute or delete;
strip remains the backstop. Deterministic, terminating.

BibTeX: model output unchanged (inline `arXiv:<id>` — that discipline is what makes verification
possible; never let the LLM emit `\cite` keys). `latex_report.py` generates `refs.bib` from
`paper_meta` and rewrites ids → `\citep{<id>}`. Unresolvable keys become compile errors — a free
second tripwire. `report.md` stays a first-class artifact.

## Step 3 — lazy full-text fetch (required for claim 1)

The dump ships no full text, so extract/critique need per-paper fetch: look for local
`data/pdf|html/<YYMM>/` first, else fetch from arXiv/ar5iv with phase-2's token-bucket rate limiter
(~1 req/3 s, real User-Agent) and write through into the same layout. Extract already degrades to
abstract-only on a miss.

## Step 4 — judge robustness

- Raise pairwise truncation 2^14 → 2^15 chars (router ctx verified in step 1).
- One-shot **disjoint-family external judge** re-run of the flagship pairwise (8 topics × 2 orders;
  API model, cents). Report as confirmation — or investigate the disagreement.
- Paper framing: lead with grounding 8/0/0 (sign test p≈0.008); state overall 5/2/1 as directional
  (n=8, p≈0.22); the objective recency metrics carry the headline.

## Step 5 — 0.35 ancestor-floor vet

Sweep 0.25–0.45 (step 0.05). Plateau → robust: ship mid-plateau, report the range. Sharp peak →
overfit to 3 gold topics: re-validate on non-gold topics with role-judge precision, or reword the
paper. Only ship what survives (measure-before-ship).

## Step 6 — deploy ASAP

- CLI is the deployment (`run.py "<q>" --set-effort 4|5`).
- Thin MCP server: one tool `deep_research(question) → report.md`, synchronous (runs fit in-call),
  single-slot lock (one 3090). Hook to librechat on zaphkiel as a nix service.
- Measure and quote the **cold-cache** deep-run time (first-user experience, not warm-cache).
- Upload the dump (HF), replace the placeholder link. Regenerate first if PG changed after 2026-06-22.

## Step 7 — paper + demo evidence

- **Dogfood artifact (claim 3):** one fresh deep run on "grounded literature review generation with
  citation graphs and LLMs"; commit report + a short gap-surfaced → implemented note.
- **Cheap head-to-head:** 3–5 topics through Gemini/Claude deep research (manual) vs GraphIV; table of
  verified arXiv ids, ≥2025 counts, fabricated ids. This is the recency selling point with a number.
- Full paper narrative rewritten (draft → user veto). Full external-technique comparison stays a later
  experiment.

## Conventions (standing)

- Comments concise; multi-line comments reserved for function docstrings.
- Any run >30 min: 30-minute check-in timer.
- Measure before shipping; Pareto-only merges; never `kill -9` uv/torch; GPU is single-tenant.
