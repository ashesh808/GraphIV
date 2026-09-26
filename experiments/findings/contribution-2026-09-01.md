# Where the contribution actually is

Written 2026-09-01 at the end of a long session, for the next run to pick up from.
Everything here is measured or sourced, nothing is a plan.

## The one-line answer

Scale, openness and the evaluation regime. Not the walk algorithm.

## The design the user settled on

```
pool     cosine top-k over abstract embeddings
rerank   norm(llm_score) * cosine
anchors  magnets = recent high scorers    sources = most cited in the pool
walk     source -> magnet on the FULL citation graph, not a pool-induced subgraph
output   the walk result becomes the new pool
```

Both endpoints come from the pool, the path is free to leave it.

## What the literature says, four agents

### LeyLine keeps its name. The family it belongs to is RSP.

The name is LeyLine, a Fate reference, and it stays. Never call it "RSP group betweenness" in
user-facing text or in the paper title. RSP is the family cited in related work, not the name.

The algorithm is genuinely one-sided, which is the delta to state:

| | formula |
| --- | --- |
| RSP edge flow, Kivimaki eq 15 | `(z_si/z_st - z_ti/z_tt) * w_ij * z_jt` |
| **LeyLine** | **`w_ij * z_jt` only** |

RSP multiplies forward reachability from the source by backward reachability to the target.
LeyLine scores with the target factor alone and lets the source side enter through the
`argmax r` start. A different estimator, not a reparameterization.

Three deltas, most defensible first:

1. **Sequential target suppression.** After each lineage the reached magnets are multiplied by
   gamma and `r` is recomputed, so the next walk bends to an uncovered lineage. RSP has no
   adaptive re-weighting. No scientometrics precedent found. It is MMR-shaped in retrieval terms,
   so the claim is "first application to lineage extraction", not "new idea".
2. **Set to set.** Subelj et al. name multi-source and multi-target as future work.
3. **Derived anchors.** Every prior method takes user-supplied endpoints.

One-line definition for the paper: *LeyLine is a one-sided, adaptively-suppressed path-flow
sampler over derived anchor sets.*

### The family, for related work


| ours | theirs |
| --- | --- |
| `p(j\|i)` proportional to reachable magnet mass | RSP edge flow, Kivimaki `1509.03147` eq 15 |
| `beta^hops` | `e^{-beta*c}` with unit edge costs |
| frequency vote over seeds | Monte Carlo estimator of group betweenness |
| two anchor SETS | bag-of-paths group betweenness, Lebichot `1210.4276` |

`beta -> 0` of RSP betweenness **is degree centrality**, `beta -> inf` is shortest-path betweenness.
We ship `beta = 1.0`, the degree end, which is why a degree count matched the walk in `run_ablate.py`.
Closed form is O(n^3) time and O(n^2) space, impossible at 3.1M, so Monte Carlo is the only
feasible version and that is already what we built. The plumbing is right, the temperature is wrong.

### Prior owners, stage by stage

| stage | owner |
| --- | --- |
| dense pool over abstract embeddings | SPECTER `2004.07180`, SciNCL `2202.06671` |
| LLM ordinal grade plus role label | Beyond Yes and No `2310.14122`, Undermind, SurveyG |
| `cosine * (rel+2)/4` | SurveyForge temporal reranker `2503.04629` |
| citation drill off a graded pool | Undermind, Ai2 Paper Finder, DeepSurvey `2605.29522` |
| most-cited ancestor augmentation | co-citation seed expansion `2403.09295` |
| PPR ranker | HippoRAG `2405.14831` |
| **source to magnet** | **Intermediacy `1812.08259`**, J. Informetrics 2020 |
| direction knob old vs recent | DaRWR lambda, `1205.1143`, 2012 |
| decay so later walks explore elsewhere | GRASSHOPPER 2007, DivRank 2010 |
| connect set A to set B | **Group-Gateway**, Information Retrieval 15:391-411, 2012 |
| Foundation / Development / Frontier layering | SurveyG `2510.07733` |
| judge-owned termination | Undermind convergence curve |
| corpus-verified ids | PaSaMaster `2605.14306`, hallucination 32.66 to 0 |

Not main path analysis: MPA counts **paths**, our BFS `seen` set counts each magnet once, so we sit
on intermediacy's side of the 2020 MPA-vs-intermediacy argument. Price and Evans `2512.12355` find
no advantage of MPA over a plain longest path across 22 networks, so nothing is lost by that.

### Hub suppression, 20 years of results

| mechanism | outcome |
| --- | --- |
| absorbing states, GRASSHOPPER | loses on diversity, slowest |
| vertex reinforcement, DivRank | destroys direction awareness |
| sparsification, GSPARSE | worse than plain local maxima |
| submodular coverage, DRAGON | returns almost the same set as top-k |
| `w_ij / (d_j)^alpha` on the transition matrix, CePS 2006 | works |
| IDF on the seed vector, HippoRAG | +2.7 R@2, +2.0 R@5 |
| age / direction bias, CiteRank and DaRWR | works, shipped in both |

DRAGON reproducing top-k independently corroborates our facility-location result.
We already have the third mechanism (magnets = recent). We have neither of the first two.

### Scale

| system | nodes / edges | time |
| --- | --- | --- |
| Faloutsos connection subgraph, KDD 2004 | 15M / 96M | under 3 s |
| FAST-PPR, KDD 2014 | 41.7M / 1.5B | under 3 s |
| **GraphIV** | **3.1M / 72.8M** | |
| theadvisor DaRWR, TIST 2014 | 1M / 6M | real time |
| HippoRAG, NeurIPS 2024 | 92K / 337K | |
| G-Retriever, NeurIPS 2024 | ~1K | |

34x the largest published graph-RAG graph, 5x smaller than a 2004 KDD paper.
Claim scale against the LLM-era line only, and cite FAST-PPR first.

### The standing threat

Kucuktunc `1205.1143` ran the closest system on 295K papers, recovering hidden references:

| scenario | PaperRank (plain PPR) | DaRWR (direction aware) |
| --- | --- | --- |
| hide-random | **51.31** | 40.62 |
| hide-recent | 37.41 | **40.57** |
| hide-earlier | 55.17 | **60.72** |
| future prediction | **51.48** | 39.08 |

Direction awareness wins only when the target is explicitly skewed old or new.
Their TIST 2014 follow-up found every elaborate walk modification loses to one PPR run plus a
cheap selection rule. Our own ablation agrees. The beta sweep is the only thing that can answer it.

## What we measured this session

All in `scratchpad/lexical-arm/REPORT.md` and `scratchpad/leyline-tabular/REPORT.md`.

### Lexical arm is dead, three instruments agree

Prod's `lexical_pool` used `plainto_tsquery` over titles, which ANDs its terms.

| arm, AND semantics | median rows | surveys with zero hits |
| --- | --- | --- |
| title | 0 | 26 / 40 |
| title + abstract | 14 | 8 / 40 |

Rebuilt with OR semantics over a 4.3 GB tsvector table, 40 surveys:

| arm | alone | best fused | weight | delta | p |
| --- | --- | --- | --- | --- | --- |
| cosine only | | 0.2227 | | | |
| ts_rank title | 0.0811 | 0.2245 | 0.10 | +0.0018 | 0.581 |
| ts_rank title+abstract | 0.1402 | 0.2254 | 0.05 | +0.0027 | **0.039** |
| ts_rank_cd | 0.0675 | 0.2240 | 0.05 | +0.0013 | 0.375 |
| Okapi BM25 | 0.1545 | 0.2261 | 0.20 | +0.0033 | 0.307 |

Confirmed on the 60-survey bench at four mention thresholds, all deltas under +0.008, and on the
niche band alone where lexical is 4x worse than cosine. Cut `bm25.py` and `hybrid.py`.

### Compound queries, the biggest measured effect

20 controlled pairs, two unrelated surveys joined into one question, recall per half:

| condition | recall | vs ceiling |
| --- | --- | --- |
| each topic alone | 0.2082 | ceiling |
| compound query, 400 pool | 0.1233 | **-41%** |
| split + RRF, shared 400 pool | 0.1553 | -25% |
| **split + RRF, 400 per clause** | **0.2092** | **+0.0010** |

`2606.08577` finds decomposition at first-stage retrieval HURTS (NDCG@10 down 1.6-4.3) because
they fuse sub-queries into one top-K. The reconciler is budget. State the claim as
"budget allocation, not decomposition, is the operative variable" or it reads as refuted.

### Pool depth dominates everything

Survey `2505.05530`, exact cosine rank of all 146 references over 3,103,758 papers:
p50 = 1,152, p90 = 9,209.

| pool k | recall |
| --- | --- |
| 400 | 0.205 |
| 1,000 | 0.452 |
| 5,000 | 0.836 |
| 20,000 | 0.918 |

`hnsw.ef_search` caps at 1000 in pgvector, so anything past cosine rank 1000 is unreachable by
index. Exact scans in these experiments ran in seconds, untimed under concurrency.

### Niche is a key failure, not a retrieval failure

Stratified by corpus-wide citers, 40 surveys, recall over the reachable denominator:

| band | refs | cosine | ancestors | leyline | degree | pool-share ratio |
| --- | --- | --- | --- | --- | --- | --- |
| niche <10 | 598 | **0.2614** | 0.0000 | 0.0071 | 0.0221 | 0.0232 |
| low 10-49 | 1,062 | 0.2985 | 0.0156 | 0.0314 | 0.0488 | **0.0744** |
| mid 50-199 | 853 | **0.2372** | 0.0928 | 0.0726 | 0.1038 | 0.0602 |
| hub 200+ | 1,167 | 0.1213 | 0.3174 | 0.1804 | **0.3308** | 0.0085 |

Cosine is the niche finder. Ancestors at `min_citers >= 3` scores exactly 0.0000 on niche,
mechanically: three citers of a paper with under 10 total cannot land in one 400-pool.

On `2505.05530` the survey cites 15 niche papers, the pool holds 234, the overlap is 1, and
**65 of 75 judged niche papers we retrieved and the survey ignored are core on topic**.
Two independent thin samples of a large tail.

"Niche" by raw count is largely an age proxy: median age 1.2 yr for the niche band against 4.2 for
hubs. Normalizing by age makes the filter worse, not better.

Graph distance from a 400-pool, undirected BFS, 20 surveys:

| distance | papers at exactly this distance | share of corpus |
| --- | --- | --- |
| 0 | 400 | 0.013% |
| 1 | 9,888 | 0.331% |
| 2 | 327,520 | **10.884%** |

| class | in pool | 1 hop | 2 hops | further |
| --- | --- | --- | --- | --- |
| niche | 0.285 | 0.298 | **0.336** | 0.081 |
| hub | 0.102 | **0.795** | 0.102 | 0.000 |

Hubs are a one-hop phenomenon, which is why ancestors works on them and only them.
Two hops costs 33x the candidates for the same yield.

Of niche references outside the pool, forward beats backward 117 to 25: a niche paper mostly CITES
our pool. `AncestorReranker` walks backward only. Their reach is 0 not because the path is missing
but because it runs the wrong way.

### A separate niche pull does not beat a deeper pool

400 pool plus a 400 second pull, deduplicated, scored over all references:

| second pull | recall | added |
| --- | --- | --- |
| cosine alone k=400 | 0.205 | |
| **just go deeper, cosine k=800** | **0.418** | **+31** |
| count [10,50) | 0.418 | +31 |
| cites/yr [1,10) | 0.288 | +12 |

`cos/log(2+n)` collapses completely: 937,845 papers (30.2%) have zero citations, so at n=0 the
divisor is 0.69 and every uncited paper outranks every cited one. Any `cos/f(n)` finite at n=0
fails this way. A hard cap works, a divisor does not.

### Leyline as shipped picks nothing

`m=120` over a 185-paper pool leaves 49 magnets, all inside the 112-slot fused head, so `w0` is
empty and `consensus_picks` returns `[]` before the walk starts. Prod also induces its graph on the
pool, so it cannot pick a paper it did not already have.

Beta sweep, 20 surveys, leyline beyond ancestors: 1.0 +0.0206, 0.7 +0.0214, 0.5 +0.0286,
0.3 +0.0336. Monotone down to 0.3, optimum not bracketed.

## What to do next, ranked by measured leverage

1. **Pool depth.** 0.205 to 0.836 going k=400 to 5,000. Blocked by `ef_search <= 1000`.
   Options are IVFFlat, a higher-m HNSW rebuild, or exact scan.
2. **Beta sweep past 0.3**, plus the two hub fixes never measured on a citation graph this size:
   `w_ij / (d_j)^alpha` on the transition matrix, and IDF on the magnet seeds.
   If a cold walk with a degree penalty still loses to degree, that is a publishable negative.
3. **Query decomposition with per-clause budgets**, as a retriever. Largest measured effect.
4. **Forward expansion at `min_citers = 1`** for the 29.8% of niche refs one hop out.
5. **Stage reorder** so embedding depends only on the abstract. 36,606 papers have an abstract and
   no vector, 40% of last month, because the cascade is pdf -> html -> embed.

## Two things to fix in how we measure

1. **The LLM judge is under test as much as the qrels.** Sjogarde `2403.09295` found our 90%
   by hand in 2024 on 3,000 medical reviews. Sahu `2605.29234` scores AI-retrieved papers at
   86-88% and human-cited at 51% with one judge, and humans are 2.5x likelier to cite a
   collaborator. Run the `03-02` broken control on the `03-04` question: judge adjacent-leaf and
   random papers, report the separation. If it calls 90% of ours core and 60% of adjacent-leaf
   core, the number measures the judge.
2. **Judge the union pool across arms, never each arm's residual.** Abbasiantaeb `2405.05600`:
   filling only the holes favors whichever system produced them.
3. Report **bpref** and **infAP** alongside recall. Standard IR answers to incomplete qrels,
   essentially unused in citation recommendation, free to add.

## Benchmarks we could run on without product access

| benchmark | size | anchor |
| --- | --- | --- |
| SurGE `2508.15658` | 205 surveys, 1.09M corpus | dense recall@1000 68.05%, best generated coverage 6.30% |
| RollingEval-Jun25 `2605.29234` | 250 CS papers, post-cutoff | DR variants over 80% at K=10^4 |
| SurveyBench `2503.04629` | 100 surveys | SurveyForge 0.40-0.42, human 0.63 |
| LitSearch `2407.18940` | 597 queries, 64K papers | GritLM 70.8 R@20, GPT-4 rerank +4.4% |

RollingEval maps onto `--set-max-date` and `--set-exclude` almost exactly.

## Correction to a claim we have been making

`2606.00898` shows a corpus-verification grounding metric reports the coverage of the graph it
queries, not the model: identical 400 responses score 0.791-0.855 against a sparse citation graph
and 0.989-0.999 against a dense one. Our guard constrains generation rather than scoring it, which
is stronger, but the defensible claim is "the id is in our corpus", not "the reference is real".

On attribution, `2607.20527` shows identical agent outputs measure 3% to 18% unsupported purely on
verifier strictness, with negative-specific agreement 0.27-0.30. So our 0.714 / 0.744 must never be
lined up against OpenAI Deep Research's 78.87%. The headline is our 90.6% two-judge agreement at
kappa 0.762 and the 0.55 discriminative gap, because almost nobody runs a negative control.

## Housekeeping

- `scratch_fts` (5.3 GB) and `scratch_indeg` (165 MB) are still in the database. Drop when done.
- `graphiv-mcp.service` crash-loops on exit 2 because `scripts/serve.py` moved to `.legacy/`.
  Postgres was started standalone with `nix run .#pg-start`.
- Experiment code is in `scratchpad/lexical-arm/`, `scratchpad/leyline-tabular/`,
  `scratchpad/litgap/search.py` (corpus search helper for agents).
- `rewrite_spec.md` holds the agreed retriever and reranker interfaces. `leyline.py` in it is
  written but predates everything above.

## Terminology the user has corrected

Say "one hop away", never "shell". Never "battery" for a set of test questions.
American English only. Never the word "gold", say ground truth or reference set.
