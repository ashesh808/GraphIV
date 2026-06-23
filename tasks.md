# tasks.md — arxivkg handoff (2026-06-22)

Status snapshot + what's left. The project is now a **self-contained single Postgres+pgvector store
under `./data`**, Neo4j-free, secret-free, compressed, with a validated 11-experiment suite.

## How to run anything

```bash
nix develop                 # ships pg-init/pg-start/pg-stop/pg-console + psql17+pgvector
pg-start                    # brings up the project DB (./data/pg, socket .pg:5433, db arxivkg)
# inside nix develop, ARXIVKG_PG_DSN points at the project socket; .venv has the python deps
ruff check phases/ experiments/ ; black phases/ experiments/ ; pyright phases/ experiments/   # all 0/0
```
Store facts: `./data/pg` (90 GB logical, btrfs-zstd on disk, halfvec embeddings), `./data/models/`
nomic, role password in `data/pg.password` (random, gitignored). **`/Vault` is deprecated/ignorable.**

## ✅ DONE
- **Phase A** — migrated SQLite+Postgres+Neo4j → one Postgres+pgvector (`phases/phase-4/components/migrate_pg.py`,
  schema `data/metadata/pg_schema.sql`); rewrote phase-6 retrieval to pgvector/SQL (`store.py`);
  restored HyDE (`pipeline.hyde_query`); de-Neo4j'd entirely; flake-launched per-project PG.
- **Footprint** — btrfs zstd + halfvec embeddings (102→90 GB logical).
- **2026 fix** — embedded the 151k 2026 delta papers (`embed_delta.py`, now a `migrate_pg` stage);
  full corpus = 3,073,288 embeddings; frontier_pull 2026 restored (exp-8 on=2.0 vs off=0.0).
- **Phase B0/B1** — `_harness/theme.py` (theme.json + Google Sans Flex), editable `_harness/topics.json`
  (27 topics), experiment suite renumbered 1–12.
- **Experiments built + run on the new store** (all lint-clean, figures + auto-READMEs):
  - 1 resolver-quality (40.18% resolution), 2 labeling-quality (intent macro-F1 0.723; **stage-1 only**),
    3 graph-structure (70.6M edges, ResNet/BERT/Transformer hubs), 4 clustering (HDBSCAN 59% noise vs
    tree 0%), 5 topic-tree.
  - 6–12 phase-6 levers re-run on 2 gold topics: all reproduce original findings.
- **Gold-label web tool** built: `experiments/experiment-2-labeling-quality/code/gold_tool.py`.

## 🔴 NEEDS YOU (human-only)
1. **Hand-label ~1000 citations** (unlocks E2 stage-2, the citable human-gold benchmark):
   ```bash
   nix develop --command python experiments/experiment-2-labeling-quality/code/gold_tool.py
   # open http://localhost:8765 ; keys 1–6 intent, z/x/c polarity (auto-advances). Doom-scroll.
   ```
   Then re-run `experiment-2-labeling-quality/run.py` (extend it to read `gold_label` for stage-2 PRF).
2. **Expert human-eval** (N≈15–20) — "which review tells the better-grounded story" vs the Phase-C
   baselines (item B below). Needs real people; design a simple A/B form over saved reports.
3. **Reclaim `/Vault`** (327 GB old DB, pure redundancy now): `dropdb -h /run/postgresql arxiv-citations`
   (no sudo, you own it; do NOT `rm /Vault/postgresql` — shared cluster). Data is safe in `./data/pg`
   + the release dump.
4. **Paper writeup / positioning** — drop "first open arXiv KG" (OpenAlex/S2ORC/unarXive exist); the
   defensible claim is "first intent-typed, recency-aware, dual-graph arXiv KG + grounded
   developmental-review endpoint, single-store + single-box reproducible, with an open edge benchmark."

## 🟢 BATTERY + DEEP SHOWCASE — DONE (2026-06-23)
- **Cheap-lever battery** (`bb1mqdn9e`): exp6/7/8 across ALL 27 topics (via `_harness.topics.battery()`;
  `EXP_TOPICS=a,b,c` subsets). 324 phase-6 runs, ~7.4 h. All three findings reproduced at 27-topic
  scale: exp6 `no_graph` games frontier(65) while zeroing edges+recall+judge; exp7 recency = monotonic
  lineage↔frontier dial (frontier 3.7→30.8, recall 0.09→0.04, sweet spot 0.4–0.6); exp8 `frontier_pull`
  on→1.89 / off→0.00 2026 papers. Refreshed `results/{metrics.md,ablation.png,README.md}` in each.
- **Deep showcase** (`bhhb013w4`): HIGHEST-QUALITY phase-6 on all 27 topics
  (`--set-effort deep --set-rank ppr --set-max-rounds 6 --set-critique-k 8`). **27/27 rc=0, 4 h 57 m**
  (cache-warm from the battery; ~11 min/topic). Each: ~29–36k-char sectioned review + `report.tex` +
  9–14 vision figures, under `phases/phase-6/output/research/<slug>/deep-ppr-deep6/`. Index:
  `experiments/showcase/deep-reviews-2026-06-23.md`; one tracked sample at
  `experiments/showcase/sample/transformer-attention-deep/`. (`output/` is gitignored.)
- **DESIGN for deep levers (9–12) on the battery:** build a unified config-cache — run each unique
  (topic, config) phase-6 cell ONCE keyed by config-hash, then have each experiment DERIVE its table
  from the cache instead of re-invoking. 9–12 all share the deep base (vary only rounds/critique-k/
  vision) so dedup is huge there; the deep-showcase run above already caches their top cell. Do this
  BEFORE putting 9–12 on 27 topics (naive = days).

## 🟡 RUNNABLE AUTONOMOUSLY NEXT (resume plan — non-destructive; multi-hour)
Priority order C→B→A→(release done):
- **(C) Lineage/developmental metrics** — add to `_harness/metrics.py`: spine/main-path recall (already
  have `topics.recall`), chronological-faithfulness (is the report's claimed order consistent with
  citation directions?), frontier-coverage. Small build; feeds B.
- **(B) Baselines** — add two conditions to `_harness` + a driver:
  - *STORM-style*: pure vector+lexical retrieval, NO graph (set `no_graph=True`, skip ancestor/PPR).
  - *GraphRAG-style*: build an LLM-extracted entity graph over the pool's abstracts, retrieve over
    that instead of the citation graph.
  Run all three (ours / STORM / GraphRAG) on the battery; the research claim = citation-graph grounding
  wins on faithfulness + lineage + recency. *Hours of LLM.*
- **(A) Levers on the full 27-topic battery** — experiments 6–12 only ran on 2 gold topics; re-run
  across `topics.json` for statistical robustness (most battery topics lack gold sets → recall metrics
  skip, but the metric vector still computes). Each lever's `run.py` takes `topic_keys` — widen it.
  *Many hours (deep levers × 27 topics); run sequentially (single GPU, VRAM).*
- **Release** — slim `pg_dump -Fc` of the store → `data/release/arxivkg-2026-06-22.dump` (KICKED OFF
  this session; check `/tmp/arxivkg_release_dump.log`). Package with the builder (`migrate_pg` + flake)
  + the E2 benchmark for the open-resource release.
- **Cleanups** — `uv lock && uv sync` to drop the now-unused `neo4j` from `.venv` (low priority; it's
  harmless in the lockfile but removed from `pyproject.toml`). Refresh experiments 6–12 hand-written
  READMEs to the new-store numbers.

## Open notes
- frontier_pull n_2026 is modest for diffusion/testtime (HyDE query embeds near 2020–23 classics, few
  2026 in the nearest-1500 probe) — structurally correct (on>off), just topic-dependent magnitude.
- A5 (optional Neo4j export) was retired during de-Neo4j; not coming back.
