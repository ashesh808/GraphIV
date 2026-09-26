# Design decisions

One entry per decision that shipped.
Each names what it was run against, the numbers that separated them, and what the verdict was.

Entries marked **argued** had no bake-off.
They were settled by reasoning, and that is stated rather than dressed up as a measurement.
Numbers come from `results/metrics.md` inside the named experiment unless another source is given.

---

## Store and ingest

**One Postgres with pgvector, not Postgres plus Neo4j.** Argued.
The graph algorithms were already Python-side (`pagerank.py`, `subgraph.py`), so Neo4j was serving
only as a vector index and a one-to-two-hop fetcher, both of which pgvector and SQL do.
The size argument settled it: the ~500 GB was dominated by parse scratch text over 173M rows, and
cutting that made a distributable dump plausible.
It came out at 23 GB.
Neo4j survives as an optional one-way export, off the serve path.

**LaTeXML HTML as the parse source, not PDF.** Argued.
GROBID mangles citations and running LaTeXML locally costs more than the artifact is worth, while
arXiv's own HTML carries the bibliography already marked up.
The counter-argument was store size, and it lost on measurement: HTML is 489 GB against the PDFs'
5.6 TB.

**Carry the whole store to prod, no mirror, no fetch-on-demand.** Measured against the alternatives
in `docs/release-plan.md`.
Full store plus the PG restore is ~6.3 TB against prod's 10 TB.
A 600 GB slim profile (HTML only) stays documented as the fallback if prod ever shrinks, since
extraction is HTML-driven and PDFs serve only critique, figures and the reading panel.
A public metatron mirror was rejected on licensing, not on cost.

**Embedding moved out of process to an endpoint.** Gated on parity, not on preference.
The cutover shipped only after the GGUF served by `llama-embed` reproduced the in-process
SentenceTransformer at cosine >= 0.999 in every prompt mode with an identical KNN@20.
Documents are token-truncated client-side through the server's `/tokenize` to reproduce the
original `max_seq` semantics, which is why the endpoint must be llama-server and not any
OpenAI-compatible host.

**Asymmetric is the production space, symmetric is demoted to research.** See the retrieval section
for the measurement.
Both tables are filled, asym first, because a paper missing there is invisible to retrieval
including the frontier pull.

## Preprocess

**A six-rung resolver ladder, not one matcher.** `01-01-resolver-quality`.
No single-matcher arm was ever run, so this is a characterization rather than a bake-off.
What it establishes is that the cascade is not leaning on its riskiest rung: 40.18% of 176.9M
references resolve, the exact rungs (text, title-exact, jref, link, doi) carry about 80% of those,
and fuzzy title is bounded at 11.3%.

**The teacher's policy is written by an APE loop, not by hand.** `01-06-prompt-refinement`,
2026-08-19, 1,002 gold occurrences split 601 dev / 401 held-out per class, eight generations on
`Gemma-4-26B-Batched`.
The judge only ever reads dev mistakes, so held-out scores a policy it never shaped.

| generation | chars | worked examples | dev acc | held-out acc | held-out macro-F1 |
| --- | --- | --- | --- | --- | --- |
| 0 (hand-written) | 6372 | 17 | 0.569 | 0.536 | 0.542 |
| 2 (minimum) | 5521 | 12 | 0.715 | 0.696 | 0.709 |
| 5 (shipped) | 6552 | 16 | 0.772 | 0.751 | 0.760 |
| 6 | 7231 | 19 | 0.759 | 0.743 | 0.750 |

Held-out accuracy rose 21.5 points and `critiques` went from F1 0.32 to 0.806.
The loop cut before it grew: generation 1 collapsed 107 lines to 66, generation 2 dropped five
worked examples, and that shrinking phase bought most of the gain, while the growth past generation
5 lost a point.
The six decision rules survived every rewrite untouched.
The winner is high-precision on the relational classes (`critiques` 0.96, `motivates` 0.96) with
every miss falling into `background`, whose precision is therefore 0.50, which is the safe direction
on a corpus that is 78% `background`.
Generation 7 is not an eighth measurement: the drafter returned an empty completion and its failure
path returns the seed, so it re-ran generation 6 verbatim.
The target is anchored: 944 of the 1,002 occurrences were pre-filled by student-v1 and accepted
unedited, so read the held-out number as agreement with a v1-anchored target rather than with
independent annotation.

**Student v3 shipped despite lower accuracy than v1 and v2.** `01-02-labeling-quality`.

| student | intent acc | intent macro-F1 |
| --- | --- | --- |
| v1 | 0.894 | 0.717 |
| v2 | 0.897 | 0.713 |
| v3 | 0.844 | 0.723 |

Accuracy fell five points and macro-F1 rose, which is the whole point: accuracy is dominated by the
frequent intents, and the review needs the rare relational ones.
`critiques` at F1 0.58 is still the weakest class, and it is exactly what the tensions list is built
from.

**Student v4 trained and run over every edge, but not promoted.** `01-07-student-classifier`.

| student | intent acc | intent macro-F1 | critiques F1 | motivates F1 |
| --- | --- | --- | --- | --- |
| v1 | 0.894 | 0.717 | 0.561 | 0.647 |
| v3 | 0.844 | 0.723 | 0.583 | 0.703 |
| v4 | 0.826 | 0.771 | 0.708 | 0.820 |

v4 is v3's recipe against the APE-refined teacher's labels, same 135,936-pair population and same
trainer, so the teacher's policy is the only variable.
It labeled all 71,564,387 edges into `citation_intent_v2` in 6.6 hours at 3,008 edge/s, dropping
the 30..1000 character sentence filter that had hidden 4,207,268 edges from v1.
`background` falls 78.4% to 69.5% of the corpus and every relational class grows.

It is not promoted, because nothing available ranks it against v1.
Each student's held-out split is labeled by its own teacher, and the 1,002-occurrence gold set was
pre-filled by student-v1 for 944 of its rows, all 944 accepted unedited, so v1 scores 0.995 on it by
construction.
On the 58 hand-typed rows, v4 is 0.862 and v1 is 0.914, a 3-item gap that settles nothing.
Promotion needs an independently labeled sample, blind to both students.

**Polarity was cut on 2026-08-19.** It labeled the tone of the citing sentence, three classes, and
its only consumers were a tiebreak sort inside `tensions()` and a bracketed token in the digest.
The corpus was 94.3% neutral, so the student's reported 0.947 accuracy stood 0.4 points above a
constant-neutral baseline, and the definition itself conflated praise of the cited work with the
citing paper reporting a win over it.
`critiques` already carries the signal the tensions list needs.

**Distill rather than run the teacher on the corpus.** Argued, on cost.
177M teacher calls was never on the table.

**Density-aware bisecting tree, against k-means, DBSCAN and HDBSCAN.**
`01-04-clustering-comparison`, common 30k sample, PCA-50.
The decisive axis is the noise bucket: HDBSCAN discards 59% of papers, DBSCAN collapses to a single
cluster, and the bisecting tree places every paper.
Silhouette favors the coarse arms and was rejected as the wrong lens at this grain.
Shipped shape is 3,582 leaves over 2.92M papers (`01-05-topic-tree`).

**The nomic citation-aware fine-tune is dead.** `docs/audits/nomic-lora-recipe.md`.
The motivating measurement was real and is kept: base nomic ranks a text-similar non-cited paper
above the true citation 87% of the time (triplet accuracy 0.128, cos 0.786 against 0.666), which is
a clean statement of the blind spot the graph exists to cover.
The 45k LoRA reached 0.513, the 380k run went backward to 0.462, and the cause was measured:
29% of the mined hard negatives were real citations of the anchor, putting the metric ceiling near
0.71.
A clean v2 miner fixed the contamination to 0/200, but the retrieval litmus had already collapsed
from 1.0 pool-hit to 0.19.
Verdict: do not train.
The recipe is kept for a future attempt.

## Retrieval

**Asymmetric space on the raw question, against three alternatives.** the removed 03 suite.

| format | landmark recall | spine | j_overall |
| --- | --- | --- | --- |
| sym_hyde | 0.81 | 1.0 | 4.29 |
| sym_raw | 0.48 | 0.67 | 3.17 |
| asym_hyde | 0.77 | 0.93 | 4.29 |
| asym_raw | 0.81 | 1.0 | 4.33 |

HyDE is what rescues the symmetric space (0.48 to 0.81) and does nothing for the asymmetric one.
So the decision is not "asym wins", it is "asym wins and lets you delete an LLM call from the hot
path".

**`hnsw.ef_search` set to 1000 on connect.** `02-07-retrieval-breadth`.
This was a bug, not a knob: pgvector returns at most `ef_search` rows regardless of LIMIT, the
parameter was never set, and every vector KNN had been silently truncated to 40 rows since the
June consolidation.
`n_pool=400/600` was fiction and the pools were being carried by the lexical channel, which is fine
for a short battery topic and catastrophic for a long question with a thin title match.
Fixing it takes the named-paper pool hit from 0.857 to 1.0.

**Ancestor floor 0.30, and it does not ship alone.** `02-03-ancestor-gate`, then `02-07`.
The first sweep found a flat recall plateau with precision rising monotonically across it.

| floor | relevance rate | landmark recall | spine |
| --- | --- | --- | --- |
| 0.00 | 0.781 | 0.742 | 0.917 |
| 0.25 | 0.797 | 0.808 | 1.0 |
| 0.30 | 0.819 | 0.808 | 1.0 |
| 0.35 | 0.837 | 0.808 | 1.0 |
| 0.40 | 0.870 | 0.742 | 0.917 |
| 0.45 | 0.896 | 0.522 | 0.600 |

That picked 0.35, the max-precision edge of the plateau.
`02-07` then overturned it, because two things had changed underneath: the reader now demotes the
junk hubs the floor was invented to block, and BYOL misses a JEPA cohort by one hundredth of a
cosine.
The coupling is the real finding: at m=40 the looser floor costs recall (0.711 against 0.753), and
only at m=60 does it come back clean.
So 0.30 and m>=60 ship as one package, and neither is valid alone.
`02-03`'s README still says 0.35 shipped and is stale.

**PPR, put on trial against four set-coverage objectives.** `02-06-selection-objective`.

| arm | landmark recall | spine | pool coverage | cluster recall |
| --- | --- | --- | --- | --- |
| ppr | 0.753 | 0.917 | 0.836 | 0.923 |
| facility | 0.436 | 0.467 | 0.840 | 0.920 |
| proportional | 0.325 | 0.450 | 0.828 | 0.863 |
| fused_topk | 0.314 | 0.450 | 0.822 | 0.758 |
| mmr | 0.300 | 0.367 | 0.824 | 0.778 |
| ppr_facility | 0.686 | 0.833 | 0.840 | 0.930 |

The motivation was adversarial: SimPO and KTO never became landmarks for the RL question, so the
suspicion was that item-wise centrality is the wrong objective for a review.
It is not.
The rich-get-richer bias is the mechanism that recovers foundational lineage, because canonical
ancestors are low-cosine and high-structure and every pure-semantic arm drops them.
The hybrid trades 0.067 of gold recall for 0.004 of pool coverage, which is not Pareto.
The per-paper autopsy relocated the actual failure to pool-miss, lukewarm grades and budget
pressure, which is what `02-07` then went after.

**Reader fusion, against cosine-only and a milder variant.** `02-05-reader-fusion`.

| variant | relevance rate | unrelated frac | landmark recall | spine |
| --- | --- | --- | --- | --- |
| baseline | 0.945 | 0.057 | 0.808 | 1.0 |
| fuse | 1.000 | 0.000 | 0.808 | 1.0 |
| fuse_mild | 0.950 | 0.051 | 0.808 | 1.0 |

Recall is identical to three decimals across all three arms, which is the gate, since the precision
numbers share a grader with the thing being ranked.
Freed slots went to core (0.270 to 0.307) and frontier (0.224 to 0.257).
`fuse_mild` sits strictly between the other two, so there is no reason to prefer it.

**Trajectory as a quota of 8 over PPR, not as a replacement.**
seven iterations, recorded at the time and now only in this entry.

| arm | verdict |
| --- | --- |
| pure trajectory | dead, gold 0.753 falls to 0.16-0.35, the cosine floor excludes vocabulary-shifted ancestors |
| deterministic greedy walk | dead, gold 0.66, randomness is load-bearing exploration |
| 10-seed random ensemble | honest tradeoff, rel2 +10.2 but gold -2.3 and spine -8.0 |
| consensus, quota 15 | rel2 0.650 at spine 0.850, a paid upgrade |
| consensus, quota 8 | Pareto, gold 0.767 and spine 0.933 against 0.753 and 0.917 |

The pairwise gate afterward was 1 win, 0 losses, 3 ties overall, with the wins on lineage, which
is what the sampler was designed for.
The independent check is section 04-04 of `docs/audits/EXPERIMENTS_AUDIT.md`: on survey
reference lists neither method was tuned against, trajectory wins core-reference recall in 6 of 6
cells.
That run also produced the tier rule: the fast tier skips reader grading, so the sampler's magnet
set is empty and it degrades silently into a blind walk.
Selection A/Bs must run at standard or deep.

**Recency default 0.4, from a sweep of five.** the removed 03 suite.

| recency | frontier count | 2026 papers | grounded | landmark recall |
| --- | --- | --- | --- | --- |
| 0.0 | 5.2 | 0.78 | 21.1 | 0.09 |
| 0.2 | 10.6 | 1.56 | 22.1 | 0.09 |
| 0.4 | 16.8 | 2.07 | 23.7 | 0.09 |
| 0.6 | 23.6 | 2.26 | 23.9 | 0.05 |
| 0.8 | 30.8 | 2.44 | 22.4 | 0.04 |

0.4 is the largest setting that costs no recall.
Past it the dial keeps buying frontier coverage and starts paying for it in lineage, which is why
it stays exposed per query instead of being tuned to one number.

**Frontier pull always on.** the removed 03 suite.
Every metric is a wash except the one that matters: 2.26 papers from 2026 per topic with it, 0.0
without.
It is a correctness fix for the topic tree predating the delta, not a quality lever.

**Topic anchor on, but this one is not settled.** the removed 03 suite keeps it (edges 4994
against 2092, judge 4.82 against 4.77), while section 04-03 of the experiments audit found a capped
survey recalling more with it off (R@3 0.842 to 0.895).
One topic is not a conclusion, and the 20-survey battery is what decides it.

**Mode is decided at refine time, not defaulted.** Shipped 2026-08-27.
`refine_question` tags every candidate `survey` or `frontier`, and an interest that reads both
ways gets one candidate of each rather than a clarifying question, so the user's pick settles it
in one round trip.
`survey` resolves to the `joint` selector, which scores citations-per-year fused with reader
relevance and reserves nothing; `frontier` resolves to `trajectory`, which scores PPR and reserves
slots for recent work. Both spend eight slots on LeyLine, so LeyLine is unconditional and the mode
switches only the score and the reservation.
`deep_research` classifies the question itself when the client sends no mode, and anything
unusable falls back to `survey`, since a mode never blocks a run.
Batch callers have nobody to ask, so `scripts/research.py` keeps `[stage.research] rank`.

**Survey mode carries a wider cohort, and the loop keeps it wider.** Shipped 2026-08-27.
`tier_budget(effort, rank)` gives survey 50/100/150/200 landmarks against frontier 30/60/90/120,
on the reasoning that a lineage answer needs more papers than a frontier scan.
The deep loop then grows the budget by 40 a round, and a single flat ceiling used to erase the
split: a 200-paper survey and a 120-paper frontier run both ended within 20 of each other, at 260
and 240.
`round_budget` now applies two ceilings, a relative one at 1.3x the tier budget and the absolute
260, so the ratio survives the loop:

| effort | survey | frontier |
| --- | --- | --- |
| fast | 100 -> 130 | 60 -> 78 |
| standard | 150 -> 195 | 90 -> 117 |
| deep | 200 -> 260 | 120 -> 156 |

The absolute ceiling is a context bound rather than a policy: past roughly 260 papers the digest
leaves no room to write the report, which is why survey deep stops at 260 and not at 1.3x.
The change shortens a deep frontier run from 240 landmarks to 156, and that has not been
re-measured.

## Generation

**Adjacency list, then roles plus extracted content on top.** the removed 03 suite, two
phases, 8 topics, order-debiased pairwise.
Phase one, on structure: `flat_list` and `adjacency_list` tie on absolute score at 4.531, so the
decision came from the two tiebreaks, tokens (6351 against 9380) and pairwise net (+0.25 against 0).
`dot` and `json` both lost 5 pairwise, and `json` also dropped grounded fraction to 0.871.
Phase two is the more useful result:

| variant | overall | coverage | tokens | pairwise |
| --- | --- | --- | --- | --- |
| adjacency_list | 4.531 | 3.75 | 6351 | 3/4/1 |
| adj_roles | 3.844 | 4.00 | 6844 | 1/6/1 |
| adj_extracted | 4.688 | 4.375 | 6664 | 5/3/0 |
| adj_alias | 4.344 | 3.625 | 4862 | 7/1/0 |
| adj_roles_extracted | 4.750 | 4.625 | 6798 | 7/1/0 |

Roles alone are actively harmful, dropping overall to 3.844 and losing 6 of 8 pairwise.
They only pay once there is extracted content for them to organize.
Extracted content is the single biggest lever, and aliasing is free.

**No taxonomy in the digest.** Argued, deliberately.
Faithfully serializing a graph into a linear context is an open problem (Fatemi et al., "Talk like
a Graph", ICLR 2024, where the encoding choice alone swings performance with no winner), and
GraphRAG sidesteps it by feeding a hierarchy of community summaries rather than a graph.
Both axes are already owned here: the taxonomy axis by the topic tree, the timeline axis by the
threads.
Building a novel graph-to-text encoder would be competing on someone else's turf, off-mission.

**Skeleton compose inside the loop, long compose once at the end.** Measured, informally.
A monolithic compose degenerated into repetition at pool ~1700, so the in-loop draft exists only for
the judge to read and the expensive sectioned write happens after the loop settles.

**Gemma stays the judge, against a Qwen swap.** Argued, then validated.
The bias argument does not survive the split: every experiment is a within-model A/B, where a
self-preference offset applies to both arms and cancels.
The one place it genuinely bites is the `saturated` boolean, one bit, and swapping to a
measurably-worse judge to de-bias one bit would add noise everywhere else.
the removed 03 suite then checked the instrument directly, on deliberately damaged reports: 1.0
on known facts, every truncation and citation-strip caught 3/3, position bias 0/6, verbosity bias
0/3.
The weak axis is lineage, where a corrupted chronology was caught only 1 of 3 times, so lineage
margins carry an asterisk everywhere they appear.

**The loop is plain async Python, not dspy or pydantic-ai.** Argued.
pydantic-ai is an agent framework, where the model chooses the next action; this loop's control flow
is fixed and the judge's verdict is data feeding a hard-coded branch.
Adopting it would mean either fighting the abstraction or actually letting the model drive, which
costs the bounded rounds and the per-paper provenance that make the thing ablatable.
dspy does not want the loop either, since the loop also calls the retriever, which is not an LLM
program.

**Round cap 4 and 6, from a sweep of four.** the removed 03 suite.

| cap | rounds actually run | landmarks | frontier | gold recall | j_overall |
| --- | --- | --- | --- | --- | --- |
| 1 | 1.00 | 80 | 37.4 | 0.81 | 4.92 |
| 2 | 1.75 | 110 | 48.5 | 0.92 | 4.86 |
| 4 | 2.38 | 135 | 58.6 | 0.88 | 4.89 |
| 6 | 3.38 | 170 | 74.4 | 0.96 | 4.94 |

The absolute judge is saturated and cannot separate these, which is the lesson.
The pairwise can: rounds-6 beats rounds-1 6 wins, 0 losses, 2 ties, sweeping coverage and lineage.
The judge self-stops at about 3.4 rounds even when allowed 6, so the cap is a ceiling and not a
target.

**Figures shipped as an option.** the removed 03 suite.
About 13 figures at 0.91 caption faithfulness, and the text judge is unmoved because it reads text.
The honest wobble is gold recall, 0.85 with figures against 0.92 without, on separately-generated
runs; that is unexplained and small, and it deserves a look before the number is quoted anywhere.

**Hub suppression is a compose guard, not a retrieval signal.** the removed 03 suite.
Four data-derived demotion signals were swept against a topic-conditioned oracle, with gold recall
as the tripwire:

| arm | gold recall | generic frac | specific retained |
| --- | --- | --- | --- |
| none | 0.808 | 0.608 | 0.448 |
| pop_bg7 | 0.808 | 0.584 | 0.479 |
| lift | 0.742 | 0.504 | 0.566 |
| pr_ratio | 0.686 | 0.443 | 0.659 |

Every arm that moves the oracle meaningfully costs recall, and every arm that holds recall barely
moves it.
The reason is not fixable structurally: a hub genuinely used in a niche, Attention in theorem
proving, cannot be removed without loss, because "generic here" is partly a narrative judgment.
So the fix moved into compose, where it was A/B validated: Attention, BERT, GPT-3 and Adam went
from 3/1/3/1 mentions to 0/0/0/0 on RL-for-theorem-proving, the "Rise of Transformers" section
disappeared, and the ATP-specific coverage survived.

**Grounding is mechanical, not a model checking itself.** Argued, then verified by volume.
Fuzzy-correct a typo id against the pool, corpus-verify the rest, strip the survivors.
314 of 314 ids across six fresh deep runs, and 267 of 267 in the head-to-head set, with zero
fabricated in both.
The denominators are observed totals, not thresholds; the claim is N/N for whatever N the runs
produce.

**Reliability is the metric phase 3 reports, replacing eleven lever experiments.**
`03-01-attribution`, `03-02-checker-validity`, `03-03-graph-digest`, `03-04-source-coverage`.
Ten deep reports over five questions, each written with and without the citation digest, scored by
Gemma-4-26B and by Qwen3.6-35B so the model that wrote them is not the only one judging them.

| number | value |
| --- | --- |
| cited sentences supported, Gemma | 584/818 = 0.714 |
| cited sentences supported, Qwen | 609/818 = 0.744 |
| per-sentence agreement between them | 0.906, kappa 0.762 |
| broken citations the checker approves | 0.153 Gemma, 0.198 Qwen |
| gap between real and broken | 0.561 Gemma, 0.546 Qwen |
| sentences carrying a citation | 818/1372 = 0.596 |

A claim is checked against passages retrieved from the cited paper, not against the head of the
document, and a sentence citing several papers passes when any one of them supports it.
Read `03-02` before `03-01`: a support rate is meaningless until the checker is shown able to
reject, and the gap of 0.53, reproduced to three decimals by two model families, is what
licenses the first two rows.

**The citation graph in the prompt does not improve reliability.** `03-03-graph-digest`.
Support is 0.707 with the adjacency digest and 0.754 without, and the no-graph side leads in 8
of 10 matched pairs.
Coverage (0.594 against 0.589) and the checker's catch rate (0.704 against 0.713) do not move.
The hypothesis, untested here, is that the digest states relationships the papers' own text does
not, so "A builds on B" is true of the graph and unsupported by either document.
This is a finding about reliability only; the graph's value in retrieval is settled separately in
`02-retrieval` and nothing here touches it.

**How many uncited sentences invent something is not measurable this way.** `03-04-source-coverage`.
A five-way label scheme split 37 against 67 between the two judges, and collapsing it to one
yes-or-no question made it worse: 12 against 91, kappa 0.003, which is chance agreement.
The failure is the question, not the prompt. A cited sentence has a document to check against
and an uncited one has only the reader's threshold, so "the field moved from X to Y" is a
restatement under a generous reading and a new claim under a strict one.
The shipped number is therefore the count of sentences that carry a citation at all.
Splitting the remaining 554 needs human labels.

**Acquisition resolves a local file before the network, in both directions.** Fixed 2026-08-27.
`fetch_html` returned None the moment fetching was disabled, so `--set-fetch false` produced no
HTML at all even for papers already on disk; only `local_pdf` read the store, and two callers had
each reimplemented the lookup to work around it.
`local_html` now mirrors `local_pdf`, both `fetch_html` and `fetch_pdf` check local first, and
`fulltext.html_path` drops its duplicate.
`tests/test_fetch.py` pins it with a stub that raises if the network is reached on a local hit.

## The system as a whole

**Against a pre-2023 baseline, 8/0/0.** `experiments/deep-research/results/multi_judge.md`.
Three judges, two disjoint model families, untruncated and order-debiased, zero baseline wins in 96
axis-verdicts, sign test p about 0.008.
The earlier 5/2/1 was a 16k-truncation artifact and should not be quoted.

**Time-capped evaluation against survey reference lists.** Section 04 of the experiments audit.
The corpus and the clock are both frozen at the survey's publication month and the survey itself is
blocklisted, because otherwise the citation drill walks the survey's own reference edges, which
leaked into the pool in every uncapped pilot.
Validated on diffusion-SR: leak gone, no postdating landmarks, core recall 0.842 capped against
0.895 uncapped, where the delta is two pre-cap papers reachable only through post-cap
intermediaries.
Nobody in the comparable literature does this cap.

---

## Still open

1. **Critique contradicts itself.** The July design lock cut it outright on the pairwise (k8 against
   k0 is 2/2/4, a coin flip on the only signal trusted at that level), but the shipped default is
   `critique_k = 4`, and that experiment's own table has k4 ahead of k0 on gold recall (0.92 against 0.88)
   and grounded citations (47.8 against 45.9) while faithfulness slips 0.99 to 0.95.
   Cut it or keep it, but the design doc and the config should stop disagreeing.
2. **The topic anchor.** Ablation says keep, one capped survey says drop, battery decides.
3. **The commercial head-to-head was never run.** `results/h2h/` holds the GraphIV side only, 267
   citations across 5 topics; the Claude and Gemini runs are still a user-side task, and until they
   land the flagship claim is against our own 2023-era baseline, not against a hosted tool.
4. **Three results are stale.** The two corpus censuses counted 3.07M against today's 3.10M, and
   `02-01`'s headline 0.742 was measured under the 40-row truncation, so it is a floor.
5. **Eleven constants were never swept.** They are listed at the end of `docs/pipeline.md`.
6. **Eleven phase-3 experiments are superseded.** the removed 03 suite through
   the removed 03 suite measured levers rather than reliability, and most rested on the
   27-topic battery that is no longer trusted. Their findings are recorded above and in this
   file; the directories stay until someone decides they are safe to delete.
7. **`M_SCALE = 1.3` was hand-set.** It is what keeps the two modes apart under the loop's
   growth, and nothing measured it. The frontier deep run it shortens, 240 landmarks to 156, has
   not been re-measured against the old budget.

---

## 2026-09-26, the port out of `.legacy/graphiv` and out of the scratchpad

The system above `src/retrieve` was rebuilt into `src/miner`, `src/report`, `src/mcp` and
`src/webui`, and `src/frontier`, `src/serve` and `scratchpad/` were deleted. What follows is what
was carried over and what was not, with the measurement behind each call.

### Taken

| from | what | why |
| --- | --- | --- |
| `generate/narrate.py` | the grounding guard | every arXiv id in a finished document exists by construction |
| `generate/story.py` | connectors | a paper bridging two retrieved papers is invisible otherwise |
| `retrieve/joint.py` | citations per year blended with the reader, 0.65 and 0.35 | 341 of 441 against frontier 320 and ppr 277, junk 9% against 14 and 16 |
| `retrieve/recency.py` | the era cutoff, and the newest-cohort-first fill | a fixed window buries recent work in a fast field and admits a decade of it in a slow one |
| `retrieve/grade.py` | the six roles, and that a paper graded out stays in the graph | the reader decides the answer, the graph decides the bridges |
| `serve/mcp_server.py` | `refine_question` | candidates, a mode each, one clarifying question, grounded in a title probe |
| `scratchpad/leyline` | the magnets, the walk, the method table, the reader | the whole mining layer |

### Left behind, each for a measurement

| module | why |
| --- | --- |
| `retrieve/landmarks.py` | its own docstring records that experiment 02-06 measured these and none shipped |
| `retrieve/pagerank.py` | the six-term score is tuned on 300 cases and reaches 0.812 |
| `retrieve/hybrid.py` | reciprocal rank fusion loses at every budget |
| `retrieve/frontier.py` | reserving landmark slots for recent work measured worse than the blend |
| `retrieve/select.py` | its eight reserved slots for the walk added nothing once relevance was in the score |
| `generate/loop.py`, `judge.py` | the calling agent owns the loop, and a model-side stop is not usable |
| `generate/pipeline.py`, `compose.py`, `long_compose.py`, `latex.py` | the tool surface and the caller replace the driver and the writer |

### Measured while porting

1. Splitting one question into areas and merging them back cost recall: 0.763 whole against 0.614
   split at a budget of 1000, over 3 SurveyMatch cases replayed against the stored run.
2. The union of the area pools held 0.87 and 0.89 of a survey's bibliography where the single
   pool held 0.64 and 0.69, so the split reaches more and the merge throws it away. Areas
   therefore keep separate pages and are never merged into one ranking.
3. The second search inside an area was dropped: over 12 cases the question pool alone scored
   0.632, the anchor pool alone 0.566, the two merged 0.612, and question-only won 9 of 12.
   `src/core/embed.py` puts the query prefix on everything, so the anchor was never being embedded
   as a document and the reason for a second pool was wrong.
4. The anchor stays as what the gate measures against, which was measured separately and won.
5. A genuinely new area shares 0 or 1 of its 300-paper head with an area already searched, and an
   area renamed rather than changed shared 61, which is what `new_share` reports.

### Settled by reading the output rather than by a number

The walk roots at the node with the most reachable magnet mass weighted by how argued-with that
node is itself, and the focus term enters as a power rather than a factor. Both were changed
because the first reports ran every lineage back to Adam and to graph convolution, which are
upstream of the whole field and tell a reader nothing. With both changes the three strongest
lineages of one temporal knowledge graph question came back as three genuinely different threads.

### Still open

8. **The miner block is one set of numbers for all three modes.** Nothing measured whether the
   frontier mode wants a different decay, walk prefix or successor span from the survey mode.
9. **The era cutoff lands on its six-year clamp for three fields in four.** Only a fast-growing
   field triggers the detection it was written for.
10. **`FOCUS = 4.0` is the gate's exponent reused.** It answers the same question about the same
   cosine, which is the argument for it, but it was never swept on its own.


---

## 2026-09-26, the dashboard, and what a report is

The first version of the rebuilt report was a paper list with headings, which is what an agent
wants and not what a person does. Reading it beside `.legacy/graphiv/serve/webui` settled three
things.

**A report is a review.** `src/report/compose.py` is the old `long_compose` shape: a digest of the
evidence, one outline call over it, then one call per section, because a single call self-limits to
about a thousand words however much it is given. `quick` skips it, `standard` and `deep` write it
at about 45 seconds. The outline needs 1,800 tokens: at 700 the json for five sections truncates
and parses as nothing, which silently produced a report with no prose at all.

**The page is navigated, not scrolled.** The report has six numbered sections, and where one holds
several things at one depth they share the space as a strip over one panel: one tab per claim, one
per area under active research, one per area under unanswered questions. `report.json` carries the
parts, so the page never parses the markdown back apart.

**Unanswered questions were extractable all along.** `fulltext.OPEN` matched the limitations,
future work and discussion sections and nothing read them. `compose.unanswered` now does, one call
per area over its own papers, and the questions come back with the paper that raised each one.

### Faults the reading found

| fault | fix |
| --- | --- |
| the guard only matched `arXiv:<id>` mentions, so it never inspected the markdown links the renderer writes | it matches both shapes, and strips a fabricated id's whole link |
| every graph-only paper plotted at closeness 0 | `as_papers` carries the cosine the mining pass read |
| 123 of 124 papers counted as cited, because the evidence lists link everything | cited means discussed in the prose |
| every dispute named the same paper, since they are ordered by magnet weight | at most two per target |
| the pdf route resolved `2006.10637.pdf`, and the store names files by version | it globs `<id>v*.pdf` |

### Still open

11. **A model can attach the wrong name to a right id.** One section called `2305.10613`
   TimeTraveler, which is a different paper; the id and the description were right. The guard
   checks ids and cannot catch this.
