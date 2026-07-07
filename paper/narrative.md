# GraphIV — Full Paper Narrative Draft

*Over-detailed by design. The author should cut, not add. Every number in this document traces to one of the source files read during composition; invented numbers are absent by construction.*

---

## §0 — Candidate Titles

**T1 (data-paper-first):**
GraphIV: A 173M-Edge Intent-Labeled Citation Graph and Grounded Literature-Review Engine over arXiv

**T2 (method-first):**
GraphIV: Citation-Graph-Native, Mechanically Grounded Literature Review over the Full arXiv Corpus

**T3 (systems-first):**
GraphIV: A Local, Verifiable, Up-to-Date Deep-Research System Built on a 173M-Edge arXiv Knowledge Graph

---

## §0 — Candidate Abstracts

### Abstract A — Data-paper-first emphasis

We release **GraphIV**, an open resource and research endpoint built over the entire arXiv corpus. The resource consists of a 173M-edge citation graph in which every edge carries a classified *intent* (background / uses / extends / compares / critiques / motivates) and polarity, 3.07M dense embeddings (768-dimensional nomic vectors, HNSW-indexed), a density-aware topic tree of 3,582 leaves covering 2.92M papers, and full paper metadata — all consolidated into a single Postgres+pgvector store distributed as a 23 GB restorable dump. The endpoint (phase 6) turns a natural-language question into a grounded, cited, chronological literature review by fusing vector retrieval, a Personalized PageRank–ranked citation subgraph, topic-adaptive recency, and a judge-driven deep loop with full-PDF critique; a mechanical grounding guard ensures that every cited identifier exists in the corpus by construction. We report a twelve-experiment suite (preprocessing, retrieval, generation) that justifies each design choice with a metric vector, and a flagship pairwise evaluation in which the full deep pipeline beats a strong single-pass baseline 8/0/0 on all four axes across eight topics, confirmed unanimously by three judges from disjoint model families (sign test *p* ≈ 0.008 per judge). A head-to-head comparison against commercial deep-research systems — 5 topics, 267 cited identifiers, 267 verified, 0 fabricated, 40 from 2026 — is reported with the GraphIV column complete; commercial columns are pending. GraphIV is released under the GNU GPLv3.

*(≈ 215 words)*

### Abstract B — Method-first emphasis

We present **GraphIV**, a citation-graph-native system that turns a natural-language question into a grounded, cited literature review over the entire arXiv corpus, running on one consumer GPU (RTX 3090) in under nine minutes cold-cache. Unlike retrieval-augmented generation over unstructured text, GraphIV induces a bounded on-topic subgraph ranked by Personalized PageRank, augments it with ancestor papers through a cosine-gated injection (0.35 floor, the max-precision edge of a validated recall plateau), and routes a judge-driven deep loop that self-terminates when the report is complete. A mechanical grounding guard — fuzzy-correct typo identifiers against the retrieval pool, corpus-verify survivors against the paper table, strip fabrications, one bounded repair pass — ensures that a report *cannot cite a nonexistent paper by construction*; this is evidenced over 314 verified identifiers across six fresh deep runs, not as an observed low rate. We evaluate with a twelve-experiment suite reporting metric vectors and identify *generic-hub dominance* — globally ubiquitous papers (e.g., "Attention Is All You Need", present in 27/27 of our deep reports) hijacking niche reviews — as the dominant quality failure of citation-graph retrieval, and address it with a validated compose-side guard that eliminates boilerplate sections at zero recall cost. The resource (173M intent-labeled edges, 3.07M embeddings, a 23 GB dump) is released open under the GNU GPLv3.

*(≈ 210 words)*

### Abstract C — Systems-first emphasis

**GraphIV** is a locally deployable, mechanically verifiable, up-to-date deep-research system built on a knowledge graph over all of arXiv. Three properties distinguish it from existing approaches. *Local and verifiable*: the system runs on one RTX 3090 against a self-contained Postgres+pgvector store (23 GB restorable dump, open weights throughout); every cited identifier is verified against the 3.07M-paper corpus by construction — a mechanical guarantee, not a benchmark score. *Up to date*: a leaf-independent frontier pull retrieves papers outside the topic tree's training distribution; our head-to-head exhibits verify 40 papers from 2026 across five topics, a figure commercial tools cannot match for the pre-cutoff window by construction since our corpus ends approximately 2026-06 and we report honestly in both directions. *Fast*: a full deep report (effort 4: judge-driven rounds, 200 landmarks, per-paper PDF critique, verified figure gallery, ≈ 30k characters) takes 8 minutes 38 seconds cold-cache on a single RTX 3090. The underlying resource — a 173M-edge intent-labeled citation graph, 3.07M dense embeddings, a density-aware topic tree of 3,582 leaves — is released as a 23 GB Postgres dump under the GNU GPLv3. A twelve-experiment ablation suite with metric vectors, negative results included, evidences every design choice.

*(≈ 198 words)*

---

## §1 — Introduction

### 1.1 The problem with literature review at scale

Scientific literature grows faster than any individual can read it. arXiv alone accumulates tens of thousands of new papers per month across mathematics, physics, computer science, quantitative biology, economics, and adjacent fields. A practitioner entering a subfield, or tracking the frontier of one they know, faces a structurally intractable triage problem: which papers are foundational, which are recent and relevant, and how do they connect? The standard remedies — keyword search, citation managers, recommendation engines — return lists. What a researcher actually needs is a *development*: a narrative that traces origins through methodological advances to the current frontier, specific enough to be useful for a niche query and grounded enough that every claim is checkable.

Large language models can write fluent text resembling such a development. The problem is that they fabricate. Citation hallucination — references to papers that do not exist, or that exist but do not say what the model claims — is not a minor quality issue; it is a validity-class failure that propagates into downstream work, grant proposals, and student training. The standard mitigation is post-hoc citation checking, but this is a palliative: a system that produces hallucinations and then catches some fraction of them is not the same as a system in which hallucination is structurally prevented. We want the stronger claim.

A second, less-discussed failure mode is *specificity*. Retrieval-augmented generation over unstructured text retrieves by semantic proximity, which tends to surface famous, heavily-cited papers that are adjacent to almost any query. A literature review on quantum error-correcting neural decoders that devotes its opening section to "Attention Is All You Need" is not wrong in a checkable sense — transformers are relevant to machine learning methods in general — but it is useless for someone who already knows the transformer literature and needs the decoder-specific papers. We show that this problem, which we call *generic-hub dominance*, is endemic to citation-graph retrieval and is not cleanly solvable in retrieval alone.

GraphIV addresses both problems. It is, first, an open resource: a 173M-edge citation graph over the entire arXiv corpus, where every edge carries a machine-classified intent (background / uses / extends / compares / critiques / motivates) and a polarity label, combined with 3.07M dense embeddings and a density-aware topic tree, all consolidated into a single Postgres+pgvector store distributed as a 23 GB restorable dump under the GNU GPLv3. It is, second, a proof-of-concept endpoint (phase 6 of a six-phase pipeline) that turns a natural-language question into a grounded, cited, chronological literature review using that resource — running on one consumer GPU, in under nine minutes cold-cache. The method is offered as evidence that the resource is useful, not as the primary claim.

### 1.2 Pitch order: what GraphIV is, in the right sequence

We foreground three properties in deliberate order, because the order encodes what we believe matters most.

**First: local and verifiable.** GraphIV runs on one RTX 3090 with open-weight models throughout. The entire served path lives under `./data`: the Postgres+pgvector store (project-local, port 5433, peer authentication, no external dependency), model weights, full-text caches. Anyone can restore the prebuilt store from the 23 GB dump and run the endpoint against any OpenAI-compatible inference server — local llama-router, remote API, or anything in between — without modifying any code. Every cited identifier in every generated report is verified against the 3.07M-paper corpus table by construction: the grounding guard cannot produce a report that cites a nonexistent paper. This is a *mechanical* property, not an empirical finding about observed rates.

**Second: up to date.** The corpus delta — papers ingested after the topic tree was trained — is handled by a leaf-independent frontier pull that bypasses the tree's distribution and retrieves directly against the embedding index by recency-weighted vector similarity. In a head-to-head exhibit across five topics using the same instruction template administered to GraphIV and (pending) to commercial deep-research systems, GraphIV's five reports cite 267 arXiv identifiers, all 267 verified, zero fabricated, 97 from 2025 or later, and 40 from 2026. The corpus delta ends approximately 2026-06; commercial tools that browse live arXiv have a structural advantage for papers after that date, and we state this honestly. Within the pre-cutoff window, the verified 2026 count is a direct consequence of the frontier pull and the mechanical grounding guard operating together.

**Third: fast.** A full deep report at effort level 4 — judge-driven rounds, up to 200 landmarks, per-paper full-PDF critique, sectioned long-form composition, caption-faithfulness-checked figure gallery, Markdown plus LaTeX plus BibTeX output — takes 8 minutes 38 seconds cold-cache on a single RTX 3090 (audio codecs topic, 2026-07-03 measurement). Warm-cache re-runs on the five head-to-head topics ranged from 2:46 to 7:38. This is end-to-end wall time for a complete, grounded, cited research document — not just retrieval or ranking.

### 1.3 The verifiability thesis

Hallucination in retrieval-augmented generation is typically framed as an empirical question: how often does the system get it right? We argue for a different frame: **verifiability as a structural property, enforced at generation time**. The GraphIV grounding guard is a four-step deterministic pipeline, applied unconditionally after every compose call:

1. *Fuzzy-correct*: any arXiv identifier in the output that is within edit distance 1–2 of an identifier in the retrieved pool is a typo — replace it in place.
2. *Corpus-verify*: check the remaining identifiers against the `paper` table (the full 3.07M-paper corpus).
3. *Strip*: remove any identifier that does not exist in the corpus.
4. *Bounded repair pass*: the section that lost a citation is rewritten with explicit instruction to re-attribute claims to surviving papers or delete uncitable claims; stripping is the backstop regardless.

This pipeline is deterministic and terminating. It does not reduce hallucination — it makes hallucination of nonexistent identifiers structurally impossible in the output. The evidentiary basis is 314 identifiers verified across six fresh deep runs on diverse topics, all confirmed present in the corpus; this is cited as a verification count, not as a "low hallucination rate." A system that produces 314 valid references without any invalid ones is not exhibiting a low rate of hallucination; it is exhibiting a pipeline design that forecloses the failure mode. The distinction matters for reproducibility: the guarantee is checkable from the code, not from a benchmark.

The LaTeX output adds a second structural tripwire: `latex_report.py` generates a proper `refs.bib` from `paper_meta.authors` and rewrites all inline `arXiv:<id>` references to `\citep{<id>}` keys. Any identifier that fails this rewrite becomes a LaTeX compile error — a free second pass at detection. BibTeX author strings from the Kaggle metadata carry TeX-encoded diacritics (e.g., `G\^arbacea`) and are passed through verbatim; stripping backslashes in bib fields would corrupt author names.

### 1.4 Contributions

We make three contributions:

1. **An open resource**: a 173M-edge intent-and-polarity-labeled arXiv citation graph, 3.07M nomic-embedding vectors (768-dimensional, HNSW-indexed in Postgres+pgvector), a density-aware topic tree of 3,582 leaves over 2.92M papers, and full corpus metadata including author strings — released as a 23 GB Postgres dump under the GNU GPLv3.

2. **A citation-graph-native endpoint**: a six-phase pipeline (phases 1–5 build the resource; phase 6 is the live endpoint) that retrieves by fusing vector similarity, lexical signals, an induced citation subgraph ranked by Personalized PageRank with topic-adaptive recency, and a leaf-independent frontier pull; composes grounded reviews via a judge-driven deep loop with full-PDF critique; and applies a mechanical grounding guard. The endpoint runs on one consumer GPU, end-to-end in under nine minutes cold-cache.

3. **A measured experiment suite**: twelve experiments (four stages: preprocessing, retrieval, generation, flagship) each isolating one design lever and reporting a metric vector. The suite includes positive results, null results (critique depth beyond approximately 4 adds cost without quality gain, experiment 03-09), and a diagnosed and fixed failure mode (generic-hub dominance, experiment 03-11). The flagship result — 8/0/0 win/tie/loss on all four judge axes across eight topics, confirmed by three disjoint-family judges — is reported alongside the measurement-instrument story of how an earlier 5/2/1 verdict was an artifact of a 16k-character truncation cap.

---

## §2 — The Resource

### 2.1 Corpus scope and metadata

The arXiv corpus, as processed, spans all papers in the Kaggle/arXiv metadata dump through approximately 2026-06, covering computer science, mathematics, physics, statistics, quantitative biology, quantitative finance, economics, and electrical engineering. The processed metadata — title, abstract, categories, submission date, author strings — is stored in the `paper_meta` table of the project-local Postgres database (`arxivkg`), mirrored from the SQLite `arxiv.db` built in phase 1. The `paper` table provides the canonical integer-id-to-arXiv-id mapping used throughout; 3.07M papers have dense embeddings (the "embedded corpus"), and 2.92M of those are covered by the phase-5 topic tree (the earlier nomic embeddings were computed before the most recent corpus additions). The 2026 delta papers — those added to the corpus after the topic tree training — are handled at retrieval time by the frontier pull (§3.2).

The `paper_meta.authors` column was backfilled in the 2026-07 release cycle, bringing the author-string count to 3.07M rows matching the embedding corpus. Author strings from the Kaggle source carry TeX-encoded special characters and are stored verbatim; `latex_report.py` passes them through without normalization.

### 2.2 Citation graph: parsing

Phase 3 parse constructs the citation graph. For each paper with acquired HTML (phase 2, ar5iv), a selectolax/lexbor parser extracts all cited references with their surrounding context sentences. Each extracted reference is resolved to an arXiv identifier through a five-layer resolver:

- **L0 (link)**: ar5iv inter-paper HTML links resolve directly.
- **L1 (regex)**: arXiv-format identifier patterns in the reference text.
- **L2 (DOI)**: DOI-to-arXiv mappings via a pre-built index.
- **L3 (jref)**: journal reference strings matched against the metadata.
- **L4 (exact title)**: case-normalized exact title match.
- **L5 (fuzzy title)**: edit-distance fuzzy title match for typographic variants.

The resolver operates over a fork-pool of 10 workers sharing a copy-on-write ~6 GB resolver index, processing approximately 60–220 papers per second depending on HTML complexity, with a full-corpus ingest time of approximately 7–12 hours. The `citation` table's primary key is `(citing_id, ordinal)` — the occurrence is the identity — making ingest idempotent on re-run. Unresolved citations are stored with a NULL `cited_id`, preserving the outbound reference count for statistics without contaminating the resolved graph. The 173M-edge count refers to resolved citations.

### 2.3 Citation intent and polarity: teacher–student distillation

Phase 3 label and bert classify every resolved citation's intent and polarity using a two-stage teacher–student pipeline.

**Teacher (Gemma-4-26B)**: A stratified reservoir sampler selects a training set across 96 strata (category × section-bucket combinations), producing a `sample.txt` of high-diversity examples. The Gemma teacher labels each example in parallel batches (P=4, BS=50), writing results to `labels.db` idempotently. The result is approximately 100,000 pseudo-labeled citations covering six intent classes (background, uses, extends, compares, critiques, motivates) and a polarity label. The teacher process includes automatic llama-router recovery (`/router/restart` + `/v1/models` health probes), averaging approximately 8 citations per second.

**Student (DistilBERT)**: A `IntentStudent` model with separate intent and polarity classification heads is trained on the pseudo-labels using multi-task learning, stratified 80/10/10 splits, and class-weighted cross-entropy to handle the severe class imbalance (background citations dominate). The student is then run inference-side over the full corpus via a server-side cursor with batch upload through a `label_staging` table into the `citation` table via `UPDATE FROM`, resumable by a `WHERE intent IS NULL` predicate. Inference throughput is approximately 2,550 citations per second end-to-end, labeling the 64.9M citations with resolved `cited_id` in approximately 7 hours on the RTX 3090.

The resulting `citation` table — 173M edges with intent, polarity, intent score, and the source context sentence — is the primary novelty of the resource. Experiment 01-02 (labeling quality) characterizes the per-head confusion matrix, precision, and recall of the student against the teacher and against held-out human judgments.

### 2.4 Dense embeddings

The 3.07M dense embeddings are 768-dimensional vectors produced by the nomic asymmetric text embedding model (`nomic-embed-text-v1`), covering the full corpus including the 2026 delta. Phase 4 attaches these to the Postgres store as the `paper_embedding` column (768-dimensional `vector` type) with an HNSW index (`paper_embedding` index). Query-time encoding uses the asymmetric query encoder (the HyDE variant proved redundant given asymmetric encoding; experiment 03-03). The embeddings are stored in UMAP-50 reduced form for topic tree construction (phase 5) and in full 768-d form for retrieval.

An earlier HNSW index, `paper_embedding_asym`, built on asymmetric encodings, is included in the 23 GB dump released with GraphIV. The Jun-22 dump lacks this index and the authors column and is superseded by the 2026-07-03 dump.

### 2.5 Topic tree

Phase 5 builds a density-aware topic tree by recursively bisecting the UMAP-50 nomic vectors using a coherence early-stop criterion. The result is 3,582 leaf nodes covering 2.92M papers — every paper receives a leaf assignment (there is no noise bucket). The `paper_topic` table maps paper ids to leaf ids; the `leaf` table stores leaf metadata including coherence scores and optional community summaries (generated by a Gemma map call, default off). The tree is stored in SQLite (`topic_tree_nomic.db`) and in the Postgres tables.

The topic tree was trained before the most recent corpus additions; papers in the 2026 delta therefore lack leaf assignments. The frontier pull (§3.2) compensates at retrieval time by querying the embedding index directly with a recency filter, independent of the topic tree.

### 2.6 The single Postgres+pgvector store and the 23 GB dump

All data is consolidated into one project-local Postgres+pgvector database (`arxivkg`), launched from the project's `flake.nix` (`pg-init` / `pg-start`) over a project-local socket (`.pg/`, port 5433, peer authentication). The eight tables in the released dump are: `paper`, `paper_meta` (with authors), `citation` (173M rows with intent/polarity), `paper_embedding` (HNSW), `paper_embedding_asym` (HNSW), `paper_topic`, `leaf`, and `gold_label`. The dump is `data/release/graphiv-2026-07-03.dump`, 23 GB. Restore is a single `pg_restore` call documented in `docs/restore.md`.

The served path is fully under `./data`; PDFs and HTML reside on external mounts accessed as symlinks and are not required to run the phase-6 endpoint (full-text is fetched per-paper on demand using the lazy fetch mechanism, §3.3). The served path has a target footprint under 100 GB including the restored Postgres datadir, model weights, and full-text caches; the store alone (restored from dump) is substantially smaller.

---

## §3 — The Method Proof-of-Concept

### 3.1 Architecture overview

Phase 6 is the live research endpoint. Its contract is: receive a natural-language question, produce a grounded, cited, chronological literature review as `report.md` (Markdown) and `report.tex` / `refs.bib` (LaTeX+BibTeX), with an optional figure gallery. The pipeline has four major stages — retrieve, rank, extract, compose — with an optional judge-driven deep loop wrapping the retrieve–compose cycle.

The single `run.py` entry point accepts an `--set-effort` dial from 0 (instant, single-pass, no loop) to 5 (exhaustive). At effort ≥ 3, the pipeline enters the deep loop (described in §3.4). All design choices are parameterized and togglable; the `experiments/` suite exploits this to flip individual flags without editing code.

### 3.2 Retrieve

Retrieval fuses six signals:

**Vector pool**: the question is encoded with the asymmetric query encoder and queried against the `paper_embedding` HNSW index. The initial pool is larger than needed; ranking and filtering follow.

**Lexical fusion**: BM25-style lexical overlap reranks the pool to surface papers that share rare technical terms with the query, compensating for the semantic compression of dense embeddings.

**Topic-tree anchor**: the query is assigned a leaf in the topic tree; papers in that leaf and its neighbors are boosted. This favors on-topic papers from the tree's training distribution.

**Citation subgraph**: starting from the vector-pool seeds, a bounded induced subgraph is built by following citation edges (both outbound and inbound) up to a configurable hop depth. The subgraph expansion is the core citation-graph-native step; it surfaces papers that are never the direct top-k semantic match but are foundational landmarks in the local citation neighborhood. Experiment 02-01 measures the value of this step: the committed recipe recovers 0.74 of canonical landmarks and 0.92 of the foundational spine (the highest-cited papers in the gold set), against a pool ceiling of approximately 0.85.

**Ancestor augmentation**: for each seed paper, the most-cited ancestors (papers it cites that themselves have high in-degree within the induced subgraph) are considered for inclusion. A cosine floor of 0.35 — the max-precision edge of a validated recall plateau — filters ancestors by semantic relevance before injection (§4.2).

**Frontier pull**: a leaf-independent pull that queries the embedding index with a recency filter, surfacing papers added after the topic tree's training distribution. This is the only mechanism through which the 2026 corpus delta enters retrieval. Experiment 03-05 quantifies the gain: 1.9 verified 2026 papers per topic compared to 0 without the pull. Without this step, the deep reports on our panel would contain no 2026 papers.

The full retrieve step is HyDE-shaped at the query level (`pipeline.hyde_query`): a hypothetical abstract is generated for the question and used as the embedding query, but experiment 03-03 shows that with asymmetric encoding, HyDE's benefit largely disappears — asymmetric raw encoding ships as the default.

### 3.3 Rank

Retrieved papers are ranked by Personalized PageRank (PPR) seeded by query-cosine similarity. PPR propagates authority through the citation graph; papers that are heavily cited by other query-relevant papers receive high scores even if they are not direct semantic matches. The rank function offers three modes: `ppr` (default), `frontier` (recency-weighted), and `indegree` (raw citation count). Topic-adaptive recency is applied on top of PPR: `recency.detect_frontier` examines the year histogram of the retrieved set relative to the query and identifies the topic's empirical frontier year; `frontier_select` then reserves a fixed fraction of the top-K slots for papers from the newest cohort, preventing older foundational papers from monopolizing the ranked list.

Age-normalized scoring (`age_norm_score`) divides raw citation count by years since publication, converting raw popularity into impact rate. This helps young frontier papers compete with older foundational works on a meaningful basis.

### 3.4 Extract and grounding guard mechanics

Each ranked landmark paper is associated with its full text, obtained through a lazy fetch mechanism: the system first checks local `data/pdf/<YYMM>/` and `data/html/<YYMM>/` directories, then falls back to rate-limited arXiv / ar5iv fetch (approximately one request per three seconds with a real User-Agent header), writing through into the local cache. The lazy fetch fixed a latent bug: `fulltext.py`'s `HTML_DIR` previously pointed at a nonexistent `phases/data` directory, causing extraction to silently degrade to abstract-only on every cache miss.

Per-paper schema fields — main contribution, methodology, key results, limitations — are extracted by a Gemma-Code model and cached to `data/extract_cache.db` by arXiv ID and schema hash. A subsequent rerun with the same schema is a cache hit.

**Grounding guard**: applied unconditionally after every compose call. The four steps are detailed in §1.3. The crucial structural point is that fuzzy-correction targets only identifiers within edit distance 1–2 of a member of the retrieval pool — it corrects typos in identifiers the model has seen, not fabrications toward arbitrary strings. Corpus verification is a query against the `paper` table (indexed lookup). Stripping is unconditional for survivors. The bounded repair pass rewrites only the affected sections, not the full report, keeping latency bounded. The guard runs on the output of every compose call in the pipeline, not only at the final assembly step.

Evidence: 314 arXiv identifiers across 6 fresh deep runs on diverse topics, all verified present in the `paper` table. This is reported as a verification count, not as a "hallucination rate."

### 3.5 Deep loop: judge-driven rounds

When effort ≥ 3, a thinking Gemma-4-26B-Code model (the "judge") reads the current draft report and the retrieved landmark set and emits two outputs: (a) a quality assessment on four axes (grounding, coverage, lineage, coherence) and (b) a structured gap list — topics and papers that are under-represented or missing. The judge owns the termination decision; `max_rounds` (set by `--set-max-rounds`) is only a cap. In practice, the judge self-stops after 1–3 rounds on well-connected topics (the dogfood run saturated after one round; experiment 03-08 shows the judge self-stopping before the cap).

Each gap triggers a retrieval expansion: the gap description is embedded, and the retrieval pipeline runs again with the gap as a secondary query, finding papers that fill the identified hole. These additional papers are scored, extracted, and incorporated into the landmark set before the next compose call.

Full-PDF critique (`critique_k` papers per round) augments the gap signal: for each of the top-K landmark papers, the full text is fed to a Gemma-Code critic that extracts claims the paper makes that are not yet reflected in the current draft. These claims become additional grounding targets for the compose pass. Critique caches are stored in `data/critique_cache.db`.

Experiment 03-08 (judge loop, measured under the old 16k truncation cap — a conservative measurement) reports a pairwise win of 0.75 deep vs. single-pass, with the judge self-terminating. Experiment 03-09 (critique depth) is a documented near-null result: depth beyond approximately 4 papers adds cost without detectable quality gain, informing the default setting.

### 3.6 Long-form composition and figure gallery

Single-pass compose produces a single-section review. The deep loop enables `long_compose`: the judge emits a structured outline (section titles, scope, key papers per section), then each section is composed separately with its own grounding context, and an introduction and close are composed from the assembled draft. This is the only mechanism that produces a truly long review (the dogfood run's report is approximately 30k characters); single-pass reviews are shorter and less organized.

The figure gallery (`figures_for`) runs Gemma-4-26B-Vision over PDF figure pages of landmark papers, extracting figures with their captions and assessing caption faithfulness. A caption-faithfulness tripwire (experiment 03-10) validates that the captions in the generated gallery match the source figures; the measured faithful fraction is 0.93. Figures are included in the Markdown report as base64-embedded images.

LaTeX output (`latex_report.py`) assembles `report.tex` and `refs.bib` from the Markdown draft, rewriting inline `arXiv:<id>` citations to proper `\citep{<id>}` keys and building real BibTeX entries from `paper_meta.authors`. Compile errors surface any unresolvable key as a second structural tripwire.

---

## §4 — Evaluation

### 4.1 Evaluation philosophy: metric vectors over single numbers

The experiment suite is organized around the principle that **any single metric is gameable**. Experiment 03-02 (component ablation) is the clearest demonstration: removing the citation graph from the pipeline *maximizes* the "frontier count" surface metric — the model, unconstrained by the graph, fabricates or retrieves a larger number of recent-sounding papers — while simultaneously zeroing the citation-edge count, zeroing graph-recall, and producing the lowest judge score on coverage and lineage. A system evaluated only on frontier count would appear to *improve* when the graph is removed. This motivates the metric vector approach: every experiment reports frontier count, 2025 and 2026 verified paper counts, edge count, grounded-versus-off-digest citation fraction, word count, numerical density (specificity), judge scores on all four axes, round count, and figure count, simultaneously.

The experiment suite covers four stages:

- **01-preprocessing** (5 experiments): characterizes the substrate via SQL over the store, with no LLM calls. Covers resolver quality (5-layer citation resolution rate by method, category, era), labeling quality (teacher prompt evolution, per-head confusion matrix), graph structure (degree distributions, intent and polarity mix, top hubs), clustering comparison, and topic tree properties.

- **02-retrieval** (4 experiments): measures retrieval quality against gold canonical sets without running the full pipeline. The gold set consists of curated canonical landmark papers and a "spine" (the highest-priority subset) for three topics: diffusion models, transformers, and test-time compute.

- **03-generation** (11 experiments): runs the full pipeline and measures downstream quality. Covers judge validity, component ablation, embedding format, recency dial, frontier pull, landmark selection, graph representation format, the judge-driven deep loop, critique depth, vision figures, and hub suppression.

- **deep-research** (the flagship): the full deployed pipeline before and after, judged untruncated by three judges.

### 4.2 Retrieval: the 0.35 ancestor cosine floor

Experiment 02-01 establishes the baseline retrieval quality of the committed PPR recipe: recall of 0.74 against the gold canonical set and 0.92 against the spine, against a pool ceiling of approximately 0.85. The gap between pool ceiling and canon recall reflects the difficulty of reaching all foundational papers through the initial vector query.

Experiment 02-02 measures off-topic noise using an independent role-judge: approximately 78% of retrieved landmarks are judged on-topic; the remaining approximately 22% are off-topic papers that nevertheless carry high in-degree (globally influential papers that PPR floats to the top). This is the retrieval-stage manifestation of generic-hub dominance.

Experiment 02-03 sweeps the cosine floor on the ancestor augmentation injection from 0.25 to 0.45 in steps of 0.05, measuring recall (3 gold topics) and precision (27 topics) simultaneously:

| floor | canonical recall | spine recall | relative precision |
|-------|-----------------|--------------|-------------------|
| 0.25  | 0.808           | 1.0          | baseline          |
| 0.30  | 0.808           | 1.0          | +                 |
| 0.35  | 0.808           | 1.0          | ++                |
| 0.40  | (cliff begins)  | —            | +++               |
| 0.45  | 0.522           | —            | ++++              |

The critical finding is that recall is *flat* from 0.25 to 0.35 (canonical recall exactly 0.808, spine recall exactly 1.0) while precision rises monotonically. At 0.40, canonical recall begins to drop (the cliff); at 0.45, it collapses to 0.522, cutting genuine low-cosine foundational papers. The shipped default of 0.35 is therefore the **max-precision edge of a recall plateau**, not a tuned peak. This is an important framing distinction: a tuned peak would be fragile to distribution shift; a plateau edge is robust (any value between 0.25 and 0.35 gives identical recall, and 0.35 happens to give the highest precision within that range). The shipped value is `augment_with_ancestors(min_cosine=0.35)` in `pipeline.py` and the harness recipe.

The ancestor gate is a Pareto win: it improves precision while leaving recall unchanged. The honest caveat (§5) is that the recall measurement is over n=3 gold topics; generalization to other topic distributions is untested.

### 4.3 The flagship pairwise and the truncation-artifact story

The flagship experiment compares the full deployed pipeline (effort 4: judge-driven deep loop, full-PDF critique, long compose, figure gallery) against a single-pass baseline (same retrieval, no deep loop, no long compose). The question to be answered is: does the judge-driven deep loop produce a meaningfully better literature review?

**The earlier result (5/2/1) and the truncation artifact.** The pairwise judge reads both reports and votes for the better one on four axes: grounding, coverage, lineage, and overall. Early runs of this comparison yielded 5/2/1 (5 after-deep wins, 2 ties, 1 before-2023 win), a result that was directionally positive but statistically uncompelling (n=8, p≈0.22 under a two-sided sign test) and methodologically suspect because we knew the deep reports were long.

The deep loop at effort 4 produces reports of approximately 30,000–37,000 characters. The earlier judge configuration applied a 16k-character hard cap before feeding reports to the pairwise judge — which meant the judge was reading only the first half of each deep report and making a comparative judgment about the rest it had not seen. This is a measurement-instrument failure, not a finding about report quality. The instrument was giving the baseline an advantage by truncating the part of the deep report that makes it valuable: the later sections, figure references, and deep-sourced additions.

Fixing the cap — raising it to match the actual report lengths, after verifying that the router context window could accommodate both reports simultaneously — produced the corrected result.

**The corrected result (8/0/0, three judges).** With untruncated reports:

| judge | family | grounding | coverage | lineage | overall |
|-------|--------|-----------|----------|---------|---------|
| Gemma-4-26B | same as generator | 8/0/0 | 8/0/0 | 8/0/0 | 8/0/0 |
| GLM-4.7-Flash | disjoint | 8/0/0 | 6/2/0 | 8/0/0 | 8/0/0 |
| GPT-OSS-20B | disjoint | 7/1/0 | 7/1/0 | 8/0/0 | 8/0/0 |

*After-deep wins / ties / before-2023 wins; n=8 topics, untruncated reports, order-debiased. Zero baseline wins in 96 axis-verdicts; overall 8/0/0; two-sided sign test p≈0.008 per judge.*

The Gemma-4-26B judge shares a model family with the generator; we treat it as the primary judge but note the potential for family-level bias. The GLM-4.7-Flash and GPT-OSS-20B judges are from fully disjoint model families and both confirm the 8/0/0 overall verdict unanimously. The only disagreements within the panel are on coverage (GLM: 6/2/0, GPT-OSS: 7/1/0) and grounding (GPT-OSS: 7/1/0), and these are ties, not baseline wins. Zero baseline wins in 96 axis-verdicts (8 topics × 4 axes × 3 judges) is the headline; the sign test at p≈0.008 quantifies the probability of this outcome under the null of no difference.

The truncation-artifact story is reported explicitly because it is a methodologically important finding in its own right: a 16k-character cap silently invalidated a judgment of long documents, and the resulting 5/2/1 verdict was cited in intermediate reports as a directional result. Fixing the instrument changed the result from "probably better, not conclusive" to "unanimously preferred, statistically significant." The lesson is that evaluation infrastructure must be designed to handle the outputs it is evaluating, and that any apparent softening of a quality result should prompt inspection of the evaluation instrument rather than acceptance of the softer number.

**Note on experiment 03-08**: the judge-loop experiment (pairwise 0.75 deep vs. single-pass; win/tie/loss 6/0/2) was measured under the old truncated cap. This is therefore a conservative measurement — the truncation disadvantaged the deep reports there too. We report it as measured, with this caveat. The correct number for the deep-pipeline advantage is the flagship 8/0/0, not the 6/0/2 from 03-08.

### 4.4 Head-to-head exhibit

We ran five topics through GraphIV (effort 4, single RTX 3090) using a standard instruction template and verified every cited identifier with `h2h_verify.py` (corpus check plus live arxiv.org fallback for any identifier not in the local store).

| topic | wall time | ids cited | verified | fabricated | ≥2025 | 2026 |
|-------|-----------|----------:|----------:|-----------:|------:|-----:|
| neural audio codecs | 6:03* | 45 | 45 | 0 | 18 | 11 |
| test-time compute & reasoning | 2:46* | 56 | 56 | 0 | 28 | 5 |
| state-space models | 7:38* | 51 | 51 | 0 | 14 | 7 |
| RL for theorem proving | 5:14* | 60 | 60 | 0 | 23 | 12 |
| QEC neural decoders | 5:09 | 55 | 55 | 0 | 14 | 5 |
| **total** | | **267** | **267** | **0** | **97** | **40** |

*\* warm-cache re-run times (a slug-collision bug — since fixed — overwrote the first pass; cold first-pass times were 4:58–11:00; cold-cache reference: 8:38 on audio codecs from an earlier run).*

The GraphIV column is complete. The commercial columns — Claude deep research and Gemini deep research, run with identical instruction strings with refinement declined ("proceed with the question as stated") and verified by the identical `h2h_verify.py` — are **\todo pending** (user-side runs required; outputs saved for batch verification). The comparison is honest in both directions: our corpus delta ends approximately 2026-06, and commercial tools that browse live arXiv have a structural advantage for papers from 2026-07 onward. For the pre-cutoff window, the 267/267 verified / 0 fabricated / 40 from 2026 result reflects the grounding guard and frontier pull operating together.

The instruction template is the same string for all systems: "Write a literature review tracing the development of {topic}: the foundational work, the key methodological advances, and the current research frontier including the most recent papers. Cite specific papers throughout." Refinement is declined to prevent the commercial tools from reformulating to their strengths. The topics were selected to span a range of technical specificity: broad methodology (test-time compute), audio signal processing (neural audio codecs), architectural family (state-space models), formal reasoning (RL for theorem proving), and physics-adjacent ML (QEC neural decoders).

### 4.5 Cold-cache timing

The cold-cache reference time is **8 minutes 38 seconds** for the neural audio codecs topic at effort 4 (3 judge rounds, up to 200 landmarks, per-paper PDF critique, figure gallery, Markdown + LaTeX + BibTeX output). This is a first-user-experience number: no extract cache, no critique cache, no full-text cache. Warm-cache times on the head-to-head topics ranged from 2:46 to 7:38.

The timing is for the complete end-to-end pipeline on a single RTX 3090 (24 GB VRAM), including all LLM inference (retrieval embedding, schema extraction, compose, judge, critique, figures), all database queries, all full-text fetches, and all post-processing (grounding guard, LaTeX assembly, BibTeX generation).

### 4.6 Generic-hub dominance and the compose-side fix

Reading real deep-research outputs — not metrics, actual reports — revealed a dominant quality failure: globally ubiquitous papers appearing in niche reviews where they add no specificity. "Attention Is All You Need" appears in **27 of 27** deep reports on our topic battery, regardless of topic. BERT appears in 17, GPT-3 in 16, and the Adam optimizer in 11. A report on theorem-proving with reinforcement learning devotes an entire section to the attention mechanism, BERT pre-training, and GPT-3, and cites Adam as "foundational to theorem proving." These are not citation errors in the grounding-guard sense — the papers exist and are genuinely cited within the retrieved neighborhood — but they are specificity failures: the review is dominated by papers that are cited everywhere and add no discriminating information for this particular topic.

The mechanism is structural. These papers accrue high in-degree within nearly every topic's local subgraph (mathematicians cite Adam; bioinformaticians cite BERT), so PPR floats them to the top of the landmark ranking. Retrieval-side demotions were swept over five signal types in experiment 03-11: global IDF, topic-lift (*P*(cited|topic)/*P*(cited)), citation-intent background-ratio, a personalized-PR/global-popularity penalty, and a topic-conditioned "demote iff popular AND background-cited-here" hybrid. The result is a genuine recall–specificity frontier: the topic-conditioned penalty holds gold recall perfectly but is gentle; topic-blind penalties move the LLM oracle most but drop papers that are canonical for hub-y topics. No purely structural signal removes a hub that is genuinely *used* in a niche — theorem-proving papers really do use transformers — so "generic for this topic" is partly a *narrative* judgment that requires knowing what the review is supposed to be about.

The shipped fix is therefore at the compose stage: a one-line instruction forbidding a generic-foundations section unless the foundations are directly load-bearing for the specific topic. A deep A/B on three niche topics removes the boilerplate section entirely and drops Attention / BERT / GPT-3 / Adam from 3 / 1 / 3 / 1 mentions to **0 / 0 / 0 / 0** mentions while preserving all topic-specific coverage. The fix is validated against gold recall (no regression) and an independent LLM topic-conditioned oracle. A recall-safe retrieval-side lever for the milder generic-*method* residue (methods that appear in many topics but are not universal hubs) is available but not enabled by default, pending measurement on a wider topic battery.

### 4.7 Dogfood: GraphIV surveying its own design space

One effort-4 run (5 minutes 9 seconds, 2026-07-03) was submitted with the question: *"citation-graph-based retrieval-augmented generation for scientific literature review: retrieval over citation networks, grounded long-form synthesis, and evaluation of generated reviews."* The judge saturated after **one round** — the question maps onto a dense, well-connected subgraph of the citation graph, producing 120 landmarks with 56 at the 2024+ frontier and 43 grounded citations with 0 off-digest. The full review (`experiments/deep-research/results/dogfood/report.md`, with `.tex` and `.bib`) is the working exhibit.

This is the system used as a research instrument pointed at its own field, not "self-awareness." The survey's findings confirm independently-discovered design choices in GraphIV and surface honest gaps; the note (`experiments/deep-research/results/dogfood/note.md`) maps survey findings to design decisions:

- The G-Retriever / GRAG / CG-RAG line (arXiv:2402.07630, 2405.16506, 2501.15067) runs citation-graph-native retrieval over vector-only RAG, parallel to GraphIV's PPR-ranked induced subgraph.
- LitFM (arXiv:2409.12177) annotates citing-sentence edges, parallel to GraphIV's intent-labeled citation contexts.
- CiteFix (arXiv:2504.15629) applies post-hoc citation correction, analogous to GraphIV's fuzzy-correct → corpus-verify → strip guard — with the difference that GraphIV's guard verifies against the full 3.07M-paper corpus, not just the retrieved set.

Gaps surfaced and acknowledged: human expert validation of generated reviews (named a critical gap by arXiv:2606.09105, true of GraphIV); interleaved claim-level attribution (arXiv:2407.01796, a candidate lever unmeasured and left on the table deliberately); stance-typed claim networks (arXiv:2605.30966, our intent+polarity edges are a corpus-scale version); graph-driven idea generation (Graph2Idea, arXiv:2606.09105; citation-evolution DAGs, arXiv:2605.14790, the natural next application of the store).

---

## §5 — Limitations and Honest Framing

This section collects the limitations that belong in the paper, stated plainly. The author should decide which belong in the limitations section proper versus which should be woven into the relevant results sections.

**Small gold topic set.** Curated canonical landmark sets (used for recall measurements in experiments 02-01, 02-03, and 02-04) exist for three topics: diffusion models, transformers, and test-time compute. All recall numbers in this paper — including the 0.808 canonical recall at the 0.35 ancestor floor and the 0.92 spine recall — are measured over n=3. These three topics are not a representative sample of arXiv's coverage; they are CS-heavy and all have well-known landmark papers. Generalization of recall numbers to other topic distributions (e.g., physics, quantitative biology, niche compositional queries) is unvalidated.

**Self-baseline in the flagship pairwise.** The flagship pairwise compares the full deep pipeline against an *ablated* version of GraphIV (single-pass, no deep loop, no long compose). This is not a comparison against an external system. The ablated baseline is a meaningful comparator — it isolates the value of the deep loop — but it is not the same as comparing against a competing literature-review system. The head-to-head (§4.4) addresses this partially, but the commercial columns are pending.

**LLM judge limitations.** The primary pairwise judge (Gemma-4-26B) shares a model family with the generator (also Gemma-4-26B-Code). We mitigate this with the two disjoint-family confirmations (GLM-4.7-Flash, GPT-OSS-20B), but family-level bias cannot be fully excluded. All three judges score on a compressed absolute scale; we rely on order-debiased pairwise verdicts rather than absolute scores for the headline result. The judge has been validated for known-fact accuracy and position/verbosity bias (experiment 03-01), but lineage is its weak axis — its lineage scores are the least reliable, though even on lineage, the 8/0/0 verdict holds across all three judges.

**Ancestor gate precision–recall tradeoff.** The 0.35 cosine floor improves precision while holding recall flat at 0.25–0.35. At 0.40, the cliff begins: some genuine low-cosine foundational papers — papers that are semantically distant from the query but historically important — are excluded. The shipped default (0.35) avoids the cliff while maximizing precision within the plateau, but the tradeoff exists and any user who raises the floor should be aware that 0.40+ will cut real papers. The gold recall number (0.808 canonical) reflects the committed 0.35 floor, not the theoretical ceiling; the pool ceiling is approximately 0.85, meaning roughly 9 percentage points of canonical recall are unrecoverable through retrieval even at a permissive floor.

**Corpus cutoff vs. commercial tools.** The GraphIV corpus delta ends approximately 2026-06. Commercial deep-research tools that browse live arXiv have a structural advantage for papers from 2026-07 onward. The head-to-head comparison states this explicitly, and the verified 2026 counts reflect only the pre-cutoff window. This is a deployment-mode limitation, not a design failure, but it affects the "up-to-date" pitch: GraphIV is up-to-date within its corpus, which is approximately six months behind live arXiv at time of writing.

**No expert validation.** The generated literature reviews have not been evaluated by domain experts. The LLM judge + objective metric vector (citation verification counts, recall against gold, frontier counts) is the affordable proxy. Expert study — asking domain specialists to rate the reviews for accuracy, completeness, and specificity — is cited in the dogfood survey as "a critical gap" in the field (arXiv:2606.09105) and remains future work for GraphIV.

**Experiment 03-08 (judge loop) measured under old truncated cap.** The 0.75 pairwise score and 6/0/2 verdict from experiment 03-08 were measured with the old 16k-character truncation cap. This is a conservative measurement — the truncation disadvantaged the deep reports. The corrected flagship result (8/0/0) supersedes the 03-08 number for the question of deep-vs.-single-pass quality, but 03-08 was measuring a slightly different condition (it swept loop rounds rather than comparing final products) and its numbers are reported as measured, with this caveat.

**Hub fix is narrative, not structural.** The compose-guard fix for generic-hub dominance (§4.6) is a soft instruction at the compose stage. It is not enforced by retrieval-side exclusion, so hubs can still appear in the landmark set and influence the compose context. If the compose model ignores the instruction (which it does occasionally for topics where the hub genuinely is load-bearing), the hub will appear. The instruction approach was chosen because structural retrieval demotions all hit the recall–specificity frontier; the narrative guard was the only option that achieved 3/1/3/1 → 0/0/0/0 hub mentions at zero recall cost. It is validated but not infallible.

---

## §6 — Related Work

### 6.1 Citation-graph-native retrieval: G-Retriever, GRAG, CG-RAG

A line of work (surfaced in the dogfood survey) applies graph-structured retrieval over citation networks to improve the relevance and coherence of retrieved context for question answering and synthesis. G-Retriever (arXiv:2402.07630) retrieves subgraphs relevant to a question from a knowledge graph and conditions generation on the retrieved subgraph. GRAG (arXiv:2405.16506) extends this to larger citation graphs. CG-RAG (arXiv:2501.15067) applies citation-graph retrieval directly to scientific literature. GraphIV is in this lineage: the PPR-ranked induced citation subgraph is the core of the retrieve step, and it is complemented by topic-adaptive recency and the ancestor augmentation (the corpus-scale additions not present in the smaller-graph G-Retriever setting). The key distinction is scale: GraphIV operates over 173M edges and 3.07M papers, whereas prior work in this line typically operates over smaller, curated graphs. The 173M-edge intent-labeled graph, distributed as an open resource, is intended to enable future work in this space.

### 6.2 Long-form synthesis with structural grounding: LitFM

LitFM (arXiv:2409.12177) is a fine-tuned model for literature review generation that uses citing-sentence annotations on edges — exactly the information GraphIV stores as intent-labeled citation contexts in the `citation` table. LitFM's approach is to incorporate the citing-sentence signal at generation time via fine-tuning; GraphIV's approach is to use it at retrieval time (intent-based filtering and weighting) and at compose time (the context sentences inform the composition model's grounding). The parallel is instructive: both systems recognize that the *reason* a paper cites another paper is more informative than the bare citation link, and both operationalize this at a corpus scale. LitFM's generated reviews are evaluated with human annotators; GraphIV's with an LLM judge + objective metrics. A cross-system comparison would require running both on the same gold topics with the same verifier, which remains future work.

### 6.3 Post-hoc citation correction: CiteFix

CiteFix (arXiv:2504.15629) detects and corrects citation hallucinations in LLM-generated text post-hoc, applying verification and correction after generation. GraphIV's grounding guard is in this spirit but goes further in two directions: (a) the corpus-verification step checks against the full 3.07M-paper corpus, not only the retrieved set, catching identifiers that are syntactically plausible arXiv IDs but refer to nonexistent papers; and (b) the fuzzy-correction step is applied *before* corpus verification, so that typo'd identifiers that the model almost got right are corrected rather than stripped. The result is a pipeline that is structurally closed: no fabricated identifier can survive to the final output without being a typo of a real retrieved paper that also exists in the corpus. CiteFix and the GraphIV guard are complementary tools; a deployment that generates citations via a system without a retrieval pool (e.g., a freestanding LLM) would need CiteFix's approach.

### 6.4 Commercial deep research

Commercial deep-research systems (e.g., Gemini Deep Research, Claude Research) produce long-form reports from web search results, including arXiv. They have the advantage of browsing live arXiv (no corpus cutoff) and drawing on broader web context. Their disadvantage, from GraphIV's perspective, is that they are not citation-graph-native — they retrieve by web search rather than by inducing a subgraph over the citation graph — and their grounding guarantees are at the search-engine level, not at the corpus-level. The head-to-head (§4.4) is designed to measure a concrete dimension of this difference: the verified arXiv identifier count, with fabrication rates, for the same instruction across both systems. The commercial columns are pending (user-side runs required); we report the GraphIV column with full transparency and will update the table when the commercial runs are completed.

### 6.5 GraphRAG lineage

GraphIV is downstream of the broader GraphRAG family (Microsoft GraphRAG, among others), which applies graph-structured retrieval over knowledge graphs built from document corpora. The distinguishing features of GraphIV relative to the general GraphRAG paradigm are: (a) the graph is the actual citation graph of the corpus (not an LLM-extracted knowledge graph), giving it ground-truth structure; (b) every edge carries a machine-classified intent and polarity, providing a richer relational signal; and (c) the retrieval step combines graph-native PPR ranking with dense vector retrieval and topic-tree anchoring, rather than relying solely on graph traversal. The combination of a real citation graph at scale with a dense embedding index in Postgres+pgvector is, to our knowledge, not previously demonstrated at the 3.07M-paper / 173M-edge scale as a releasable open resource.

---

## §7 — Cut List

*Things included that are likely too much detail for the final paper, flagged for the author to veto efficiently.*

**Cut candidates — probably too detailed for main text, suitable for appendix or supplementary:**

1. **Phase-by-phase build pipeline detail** (§2, resolver layers L0–L5, fork-pool CoW details, cursor-based bulk COPY mechanism). Reviewers of a paper about the resource and endpoint probably don't need L3 jref and L4 exact-title in the abstract; a "five-layer resolver" with a citation to the codebase may suffice.

2. **Teacher labeling throughput numbers** (~8 citations/second, llama-router recovery). These are implementation details; the interesting fact is the 100k pseudo-labels and the distillation result.

3. **Student throughput numbers** (2,550 citations/second, ~7 hours for 64.9M citations). Same as above — interesting engineering, probably not main-text material.

4. **The lazy fetch bug fix story** (HTML_DIR pointing at nonexistent `phases/data`). Interesting for a systems paper; probably a footnote or supplementary note, not main-text.

5. **The slug-collision bug in the h2h warm-cache timing note**. The asterisked footnote is necessary for honesty but very detailed; it may be shortened to "warm-cache re-run times; cold-cache reference: 8:38."

6. **Full topic list for the h2h** (the five topics are named, which is good; the instruction template quoted in full is probably supplementary material).

7. **The bibtex / TeX-accent / backslash GOTCHA**. Fascinating implementation detail; probably a code comment rather than paper text.

8. **The UMAP-50 detail in §2.4**. The topic tree uses UMAP-50 reduced vectors; the retrieval index uses full 768-d vectors. This distinction matters for reproducibility but may be too granular for main-text.

9. **The four-step grounding guard at full verbosity in §1.3 AND §3.4** — the guard is described twice (once in the Introduction as a thesis statement and once in the method section). One of these should be cut or one should be a pointer to the other.

10. **The full experiment taxonomy table** (01-01 through 03-11 with one-line conclusions). This is valuable for an arxiv paper or supplementary; it may be too long for the main text of a conference paper. Consider replacing with a summary row table (4 rows: preprocessing / retrieval / generation / flagship) with a pointer to `experiments/README.md`.

11. **The note that GLM-4.7-Flash is "disjoint" from Gemma-4-26B**. The disjoint-family confirmation is a key result; the specific model family names may be sufficient without the word "disjoint" needing its own explanation in the main text.

12. **The §4.3 "truncation-artifact story" subsection is long** — approximately 500 words. The author indicated they like this story and want it as its own subsection; I have written it that way. If it needs to be shortened, the methodological lesson ("evaluation infrastructure must handle the outputs it is evaluating") can be cut to one sentence.

13. **The dogfood exhibit framing** ("not self-awareness, but a research instrument pointed at itself") — the phrasing is from the author's instruction and is retained; it may read oddly to some reviewers and could be softened to "used to survey its own design space."

14. **The honest caveats at full verbosity in §5** — all eight points are in the limitations section. A conference paper might carry only four of these; the others could be condensed to a sentence each.

15. **The related-work paragraph on GraphRAG lineage (§6.5)** — if this paper is submitted to a venue where reviewers know GraphRAG well, this paragraph is unnecessary. If submitted somewhere broader, it provides useful context.

**Things that should NOT be cut:**
- The truncation-artifact story (§4.3 subsection). The author explicitly flagged this as a story they like, and it is methodologically important.
- The hub dominance section (§4.6). This is the system's primary identified failure mode and its fix; removing it would leave the paper without a diagnosis of its own limitations at the generation level.
- The \todo placeholders in the h2h table (§4.4). These are required per the author's framing rules.
- The "mechanical, not empirical" framing of the grounding guarantee (§1.3). This is the thesis of the verifiability argument.
- The pitch order (local + verifiable → up-to-date → fast). This is a binding instruction.
