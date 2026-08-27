# Experiment audit — plain-language guide (2026-07-15, updated 2026-07-17)

One entry per experiment: what it actually does, what it found, and what a rerun would
(or wouldn't) tell you now. Rerun cost classes: **SQL** (minutes, no GPU), **battery**
(27-topic single-pass, ~25 min), **deep** (8-topic deep-panel, GPU hours).

Context that dates some results: since the suite last ran we shipped (a) the ef_search
fix + floor 0.30 + m=60 package (02-07), (b) reader fusion default (02-05), (c) asym as
the only prod embedding space, and (d) 07-15: +27k papers / +1.7M citations / 595k newly
parsed papers in the corpus. Experiments marked ⚠ measured a config that no longer exists.

**07-17 additions:** embedding now served by the llama-embed endpoint (parity cosine >0.999,
KNN identical — no experiment invalidated); the trajectory sampler is prod selection in the
MCP serve path; and there is a NEW section 04: the survey-mined silver-qrels benchmark
(external evaluation instrument) with its first four studies.

---

## 01 — preprocessing (all SQL-cheap, all descriptive: they characterize, don't decide)

**01-01 resolver quality.** When we parse a paper's bibliography, each citation goes
through a ladder of matchers: first "is there a literal arxiv link", then regex, DOI,
journal-ref, exact title, and only last fuzzy title match. This experiment counts which
rung of the ladder resolved each of the 177M citations, split by field and era. Found:
40.2% of citations resolve to an arXiv paper at all (the rest cite journals/books we
don't have), ~80% of resolutions come from the trustworthy exact rungs, only ~11% lean
on fuzzy matching. Translation: the citation graph isn't built on guesses.
*Rerun now:* corpus grew by 595k parsed papers today → numbers will drift slightly;
cheap and worth refreshing for any public table.

**01-02 labeling quality.** Every citation edge gets tagged with WHY the paper cites
(extends/uses/compares/background/critiques/motivates) and a sentiment. A big LLM
teacher labeled 100k examples, a small fast model (DistilBERT) learned to imitate it,
then labeled all 65M+ edges. This measures how well the student learned: sentiment is
basically solved (0.95 accuracy), intent is good overall (0.84) but the rare
"critiques" tag is weakest (0.58). Translation: the edge types phase-6 relies on are
mostly trustworthy, except fine-grained criticism detection.
*Rerun now:* nothing changed in the models; a rerun reproduces the same frozen
artifacts. Only worth it after retraining the student.

**01-03 graph structure.** A census of the citation graph itself: 36.7M distinct
edges over 3.07M papers, degree distributions, growth over time, top-cited list. The
sanity check is that ranking papers by incoming citations recovers exactly the famous
ones (ResNet, BERT, Transformer) — if it didn't, the graph would be broken. Also
documents WHY phase-6 works inside topical pools: a few mega-hubs dominate globally.
*Rerun now:* +1.7M edges today; drift is small but the census is cheap to refresh.

**01-04 clustering comparison.** We organize all papers into a topic tree by
repeatedly splitting the embedding cloud in two ("bisecting"), stopping when a cluster
is coherent. This pits that tree against the textbook alternatives (k-means, DBSCAN,
HDBSCAN) on the same sample. The killer stat: HDBSCAN throws 59% of papers into a
"noise" bucket (unusable — every paper must live somewhere), DBSCAN collapses into one
giant blob; our tree places 100% of papers.
*Rerun now:* tree is frozen by design; conclusions are about algorithm choice, not
data. No reason to rerun.

**01-05 topic tree.** The follow-up census of the shipped tree: 3,582 leaves over
2.92M papers, how big/deep leaves are, coherence vs size. Confirms the density
early-stop does its job (tight leaves, adaptive grain, no noise bucket).
*Rerun now:* ⚠ in one sense — the tree still ends at the pre-2026 corpus (27k+150k
newer papers have no leaf; that's why frontier_pull exists). A rerun only re-describes
the frozen tree. The interesting decision is "rebuild the tree with the delta", which
is a phase-5 --include-force job, not this experiment.

---

## 02 — retrieval (how we pick the ~40-200 papers a review is built from)

**02-01 subgraph retrieval.** The core retrieval recipe: embed the question, pull a
few hundred candidate papers (vector + keyword search), add their most-cited ancestors,
keep only citation edges among the pool ("induce"), then run PageRank-from-the-query
(PPR) to pick landmarks. This tests that recipe against fancier subgraph selectors
(PCST, similarity-BFS) on: does it recover the papers a human expert would call
canonical? Result: 0.742 of canonical landmarks, 0.917 of the foundational spine —
better than the alternatives on every recall axis.
*Rerun now:* ⚠ ran pre-ef_search-fix (pools were silently capped at 40 vector hits!)
and pre-fusion. The recipe won under a handicap; a rerun on the fixed stack would
likely score HIGHER. Worth rerunning if this number goes in the paper.

**02-02 relevance judge.** Recall can't see junk — this adds precision: an LLM reads
every selected landmark and labels its role (foundational/core/frontier/peripheral/
unrelated) across 27 topics. Found ~78% on-topic, and the crucial diagnosis: the 22%
junk is famous cross-field hubs riding in on citation fame — invisible to PPR because
they genuinely have high in-degree.
*Rerun now:* ⚠ historical. The 0.78 era predates the ancestor floor + fusion; 02-05
measured the same thing at 0.945→1.0 after the fixes. Keep as the "before" picture.

**02-03 ancestor gate.** The junk from 02-02 enters through one door: "add the
most-cited ancestors of pool papers." This sweeps a cosine-similarity floor on that
door (0.25→0.45): how similar to the question must an ancestor be to enter? Found a
flat recall plateau 0.25–0.35, precision rising monotonically → shipped 0.35 as the
edge of the plateau. Also showed 0.40+ starts cutting genuinely foundational papers.
*Rerun now:* ⚠⚠ superseded — 02-07 later moved the floor to 0.30 (with the reader
doing the junk-filtering job) and the sweep ran under the ef_search=40 bug. The
methodology is still right; the shipped number came from 02-07.

**02-04 selection flags.** Given a pool, how do you pick the final set: fixed top-50,
cosine-gated 50, LLM-filtered 50, or LLM-filtered-and-bigger? Scored per-paper (an LLM
grades each landmark −2..+2 against the question). Found: filtering is what matters
(+40% mean quality), count is a separate dial, and quality-per-paper saturates at the
same point where review quality saturates. Ship the free cosine gate; LLM filter for
precision-max; keep the set small.
*Rerun now:* conclusions absorbed into the fusion design (02-05); mostly historical.

**02-05 reader fusion.** The measure-gate for a shipped default. The "reader" grades
every candidate (role + relevance −2..2, cached), and ranking becomes
cosine × (relevance+2)/4, with −2 papers excluded from landmarks but kept as graph
connectors. Three arms: cosine-only, production formula, mild variant. The gate was:
gold recall must not regress (it's grader-independent). Result: recall identical
(0.808/spine 1.0), unrelated landmarks 5.7%→0%, freed slots went to core+frontier —
Pareto win, shipped as `fuse: true`.
*Rerun now:* current-stack, still-live default. Rerun only to refresh numbers on the
grown corpus.

**02-06 selection objective.** Put PPR itself on trial (motivated by real misses:
SimPO/KTO never became landmarks for an RL question). Six selection objectives over an
identical front-end: PPR vs facility-location, MMR, cluster-proportional, fused-topk,
hybrid — i.e., "is citation-centrality the wrong way to pick landmarks vs set-coverage
math?" Verdict: PPR vindicated decisively — gold recall 0.753/0.917 vs 0.30–0.44 for
every set-coverage arm. The "rich get richer" bias IS the mechanism that recovers
foundational lineage (old canonical papers are low-cosine — semantics-only methods drop
them). Bonus: an autopsy of every real miss → three causes (pool-miss, lukewarm grade
on question-named entities, budget pressure), none fixable by changing the objective.
*Rerun now:* re-checked on uncapped pools already (verdict strengthened); current.
Do not relitigate vs set-coverage. NOTE 07-17: this verdict is about PPR vs set-coverage
*objectives*; the magnet-walk trajectory hybrid (a different successor, PPR scaffold +
8 consensus-walk slots) now beats pure PPR 6/6 on the external survey benchmark (04-04)
and is prod selection in the MCP path.

**02-07 retrieval breadth (the big bug + the coupled package).** Found that pgvector's
HNSW index returns at most `ef_search` rows no matter what LIMIT you ask for — and it
was never set, so EVERY vector search since the PG consolidation returned ≤40 rows.
"Pools of 400/600" were fiction; keyword search was silently carrying retrieval. Fixed
(ef_search=1000), then showed the three knobs are coupled and must ship together:
bigger pools need a bigger landmark budget (m 40→60), and the ancestor floor can drop
0.35→0.30 (rescuing vocabulary-shift papers like BYOL that are embedding-invisible)
only because the reader now handles junk. Gold gate held; litmus pool-hit 0.857→1.0.
*Rerun now:* THE current retrieval baseline. Rerun after any retrieval change (it is
the regression harness), or to refresh on the +27k corpus.

---

## 03 — generation (turning the subgraph into a review) + the flagship

**03-01 judge validity.** Before trusting the LLM judge that scores reviews, test the
instrument itself: feed it reviews with known planted defects and check it catches
them; check it has no position bias (A-vs-B order) or verbosity bias. Result: sound —
100% on known facts, catches coverage/grounding degradation, no biases; the "lineage"
axis is its weakest sense. Downstream rule: trust big effects and grounding/coverage,
asterisk tiny lineage margins.
*Rerun now:* still the foundation for every judged number. Rerun only if the judge
model changes (it did get retrieval-context + dated preambles in July — a light
re-validation pass wouldn't be crazy).

**03-02 component ablation.** The classic knockout: remove one component at a time
(graph, clustering, full-text, PPR→in-degree) and run the 27-topic battery. The lesson
that named the suite's philosophy: read the metric VECTOR, never one number — removing
the graph maximizes "frontier count" while zeroing edges, recall, and judge score
(a surface metric improving while the review's chronology collapses).
*Rerun now:* ⚠ ran on the old stack (pre-fusion, pre-ef-fix, sym-era). If you want a
paper-grade ablation table, this is the one to rerun on the current stack.

**03-03 embedding format.** Which query encoding retrieves best: symmetric vs
asymmetric nomic prompts × HyDE-rewritten vs raw question. Found `asym_raw` ties for
best recall at no extra cost (HyDE only rescues the symmetric space) → shipped.
*Rerun now:* it decided today's "asym is prod" policy; conclusion is load-bearing but
settled. A rerun is only interesting post-LoRA (the v3 training explicitly targets
both spaces and will be gated on this comparison anyway).

**03-04 recency knob.** Sweep the lineage↔frontier dial 0.0→0.8. Found it's a true
control surface: frontier landmarks climb monotonically 3.7→30.8 at constant
grounding, no universal optimum → correctly a per-query knob.
*Rerun now:* behavior is structural; no reason unless the ranking math changes.

**03-05 frontier pull.** The topic tree ends before 2026, so tree-anchored retrieval
can never surface 2026 papers. This toggles the tree-independent year-filtered vector
pull. Found: without it, literally zero 2026 papers appear; with it, ~1.9/topic at no
cost → shipped as a correctness fix.
*Rerun now:* ⚠ MORE important after today: the un-treed delta is now 27k bigger and
this channel is what surfaces it. A quick confirm-run on the new corpus is cheap and
directly relevant.

**03-06 landmark selection.** Older sibling of 02-04 (same question asked on the
generation side, 40-paper scale): fixed-40 vs cosine-gate vs LLM-filter vs bigger.
Same conclusion: the filter is the win, not the count.
*Rerun now:* redundant with 02-04/02-05; historical.

**03-07 graph representation.** How to serialize the subgraph into the prompt: flat
list? adjacency list? DOT? JSON? matrix? Then layer on role tags, extracted content,
short aliases. Winner: adjacency list + extracted content + roles + aliasing — best on
every judge axis at the fewest tokens (extracted content is the single biggest lever).
This IS the production digest format.
*Rerun now:* current and load-bearing for the writer; rerun only if the digest changes.

**03-08 judge loop.** Is test-time compute worth it? Cap the judge-driven
gap-expansion rounds at 1/2/4/6 and compare. Yes: rounds double landmarks and frontier
coverage, gold recall 0.81→0.96, pairwise 6/0/2 for rounds-6 vs rounds-1. The judge
self-stops (~3.4 rounds at cap 6), so the cap is a ceiling not a target → effort tiers.
*Rerun now:* current deep-path behavior; expensive (deep). Rerun only for the paper.

**03-09 critique depth.** The documented null result: reading MORE full PDFs per round
(critique_k 0→4→8) doesn't help — k=4 nudges recall up, k=8 gives it back and
faithfulness slips monotonically. Depth is not the deep loop's win; the rounds are.
Kept k=4.
*Rerun now:* a null that saved us from a cost sink; no reason to disturb it.

**03-10 vision figures.** Toggle the figure gallery (vision model reads PDFs, picks
architecture diagrams/result plots, captions verified against the image). Found: text
judge can't see images so text scores don't move; the gallery adds ~13 verified figures
at 0.91 caption-faithfulness. An additive enrichment, shipped as an option.
*Rerun now:* current (figures are role-gated in prod now — slightly different config
than the experiment measured, if you want strictness).

**03-11 hub suppression.** Keep Attention/BERT/Adam from colonizing every niche
review (Attention appeared in 27/27). Swept four data-derived "genericness" signals —
none is a silver bullet, because a hub genuinely used in a niche can't be structurally
removed without recall cost; "generic HERE" is partly a narrative judgment. Shipped fix
is in the WRITER (a compose guard): validated A/B, generic-hub mentions 3/1/3/1→0/0/0/0
on the test topic with coverage preserved.
*Rerun now:* the compose guard is current prod; the sweep half is research context.

**deep-research (flagship).** Not an ablation — the whole before/after: old single-pass
default vs the full deep pipeline on 8 topics, judged pairwise on FULL untruncated
reports by three disjoint judge families. 8/0/0 on overall+grounding, unanimous across
judges (an earlier "5/2/1" was a truncation artifact — the judge saw half the report).
Objectively: 9.0 2026-papers/topic vs 0, 2.4× frontier, 1.5× grounded citations, 13
verified figures. This is the deployment argument.
*Rerun now:* the "after" side already re-ran on the current stack (h2h work); the
"before" side is frozen by definition. Refresh only for headline numbers on the
grown corpus.

---

## 04 — external evaluation: the survey-qrels benchmark (NEW 2026-07-17)

Motivation (user call: "hand-curated gold is unscientific"): the 27-topic battery has only
19 canonical + 13 spine ids TOTAL — fine as a regression gate, indefensible as a
precision/recall claim. The field's answer (probed with GraphIV itself: LitSearch, PaSa,
"citation lists are not ground truth") is reference-list silver gold + LLM adjudication.
Scripts currently in the session scratchpad (`survey_qrels.py`, `score_survey.py`,
`recall_at_freq.py`, `compare_ablate.py`, `traj_vs_ppr.py`); the retrieval cap flag is in
the repo (`--set-max-date` / `--set-exclude`).

**04-01 survey-qrels pilot.** A survey paper is a human expert who already did our task:
read a topic, picked the papers that matter. So: take a survey's resolved reference list
from our own citation table as the answer key (80–250 in-corpus ids each), derive a question
from the survey, hide the survey, ask GraphIV, and count how many refs come back in the
pool. Weight by how often the survey *mentions* each ref (the mention rows are already in
the citation table): one-off cites are background noise; ≥3-mention refs are what the
survey is about. Report the whole recall-vs-mention-frequency CURVE, not one number.
Pilot (3× Jan-2024 CS surveys, fast tier): all curves rise monotonically and hit 1.0 at
N≥5–8 mentions; misses live almost entirely in the 1-mention tail. Two design lessons:
questions must be derived from the survey ABSTRACT (title-only under-scopes — the 3DGS
misses were avatars/SLAM subtopics my narrow question never asked for), and survey
selection should use citation count as a FLOOR (~15–20) + subfield×year stratification,
never top-cited ranking (age/mega-topic/hub bias).
*Status:* pilot done; the 20-survey stratified battery is the next build.

**04-02 time-capped retrieval (the "no newer than the survey" rule).** User-mandated:
the corpus AND the clock are frozen at the survey's publication month
(`--set-max-date YYMM`, filter at the Store level across all six pool channels +
deep-loop gap injection; `now` is anchored so per-topic frontier detection time-travels),
and the survey itself is blocklisted (`--set-exclude` — otherwise citation drill walks the
survey's own reference edges = copying the answer key; it leaked into the pool in every
uncapped pilot run). Validation on diffusion-SR: leak gone, 0 postdating landmarks, and
core recall 0.842 capped vs 0.895 uncapped — the delta is two *pre-cap* papers that were
only reachable via post-cap intermediaries, i.e. exactly the contamination the cap removes.
Nobody in the comparable literature (LitSearch/PaSa/2605.29234) does an explicit cap;
this is a claimable methodological novelty.
*Status:* shipped in the repo, both run paths, lint-clean.

**04-03 does the benchmark discriminate?** A benchmark is only an instrument if it
separates configs we understand. Ran the ablation levers through the capped diffusion-SR
survey: `no_graph` leaves pool metrics byte-identical (correct null — it can't touch the
pool) while landmark-core drops 0.263→0.158 (graph ranking is ~40% of core selection);
`no_frontier_pull` drops tail recall 0.518→0.473 (detected); `no_cluster` *raised* R@2/R@3
(0.65→0.775 / 0.842→0.895) on a smaller pool — the topic-tree refinement may be evicting
mid-importance refs. That last one is a 1-topic surprise, not a conclusion; the battery
decides. Pool metrics are deterministic (no LLM in pool assembly), so pool deltas are real.
*Status:* instrument validated on 1 topic; the no_cluster flag is an open question for
the battery.

**04-04 trajectory vs PPR on the external instrument.** The first real client of the
benchmark: does the magnet-walk sampler beat PPR on qrels neither was tuned against?
First attempt was INVALID and taught the tier rule: fast tier skips reader grading →
the sampler's rel≥2 magnet set is empty → it degrades silently to a blind walk (it swapped
out Score-SDE/ADM/DDIM for 2016 CNN papers — that's the degraded selector, not the
algorithm). Selection A/Bs must run standard/deep; fast is pool-metrics-only. Suggested
code guard (not yet written): warn + fall back to ppr when rank=trajectory sees no grades.
Corrected run (standard, m=80, grades cached so both arms see identical pools+grades):
trajectory wins landmark core-ref recall 6/6 cells across the three surveys —
lm@3 0.526/0.421, 0.304/0.261, 0.381/0.333; lm@1 a wash; rep@3 tied except a 3DGS dip
(0.130 vs 0.261, compose-stage, watch in the battery). Independent-instrument validation
of the sampler on top of the internal-battery Pareto.
*Status:* done; the +1/+2-paper margins need the 20-survey battery for intervals.

**04-05 (planned) the full battery + adjudication + human calibration.** (a) ~20 surveys,
citation-floor + stratified, abstract-derived questions via the map LLM, all capped,
both ranks, standard tier (~2 overnights). (b) LLM adjudication of uncited landmarks with
a judge DISJOINT from the pipeline's reader (GLM/GPT-OSS, not Gemma — no grading your own
homework); per 2605.29234 only ~51% of human citations clear a neutral relevance bar, so
"not in refs" ≠ wrong. (c) Doomscroll labeler: ~100–200 (question, paper) pairs labeled by
the user once; if judge-vs-user agreement matches human-human agreement (the Bing
protocol), the judge scales to the rest and the paper gets an inter-annotator number.

---

## Rerun shortlist (my read, for your audit)

| priority | experiment | why |
|---|---|---|
| high | 04-05 battery | turns 04-01/04-04's +1/+2-paper margins into intervals; the paper's eval section |
| high | 02-07 | it IS the regression harness; refresh on +27k corpus |
| high | 03-05 | directly validates that the delta is retrievable end-to-end |
| medium | 03-02 | the paper-grade ablation, on a dead stack — consider rerunning THROUGH 04 (capped surveys) instead of the internal battery |
| medium | 02-01 | headline recall number, measured under the ef_search handicap |
| medium | 01-01/01-03 | cheap SQL censuses, numbers drifted with the 07-15 ingest |
| low | 03-01 | light re-validation after the judge's July prompt changes |
| skip | 02-02/02-03/02-04/03-06 | superseded; keep as history |
| skip | 01-02/01-04/01-05/03-04/03-09 | frozen artifacts / structural nulls |
