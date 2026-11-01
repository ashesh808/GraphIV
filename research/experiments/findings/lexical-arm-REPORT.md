# Lexical arm, expansion, and compound queries

## Instrument

| item | value |
| --- | --- |
| battery | 40 arXiv surveys, 2025-01 to 2026-05, drawn at random |
| query | the survey title with the survey boilerplate stripped |
| qrels | the survey's own resolved references, stage 4, dated before the survey |
| median qrels | 86 |
| leakage guard | the survey itself excluded, every candidate filtered to `date < survey date` |
| metric | reference recall at pool size 400 |
| store | `scratch_fts`, title plus abstract tsvector over 3,103,758 stage-4 papers, 4.3 GB, two GIN indexes. `papers` was not modified |

![lexical and decomposition](figures/lexical_and_decomp.png)

## The old lexical arm returned nothing

`store.lexical_pool` used `plainto_tsquery` over titles only. `plainto_tsquery` ANDs its terms.

| arm, AND semantics | median rows returned | surveys with zero hits |
| --- | --- | --- |
| title | 0 | 26 / 40 |
| title + abstract | 14 | 8 / 40 |

The production lexical arm was not weak, it was empty for two thirds of queries.

## Lexical arms under OR semantics

| arm | recall alone | best fused | at weight | delta vs cosine |
| --- | --- | --- | --- | --- |
| cosine only | 0.2227 | - | - | - |
| ts_rank, title | 0.0811 | 0.2245 | 0.10 | +0.0018 |
| ts_rank, title+abstract | 0.1402 | 0.2254 | 0.05 | +0.0027 |
| ts_rank_cd, title+abstract | 0.0675 | 0.2240 | 0.05 | +0.0013 |
| Okapi BM25, k1=1.2 b=0.75 | 0.1545 | 0.2261 | 0.20 | +0.0033 |

Paired bootstrap, 20,000 resamples, and a two-sided sign test over the 40 surveys:

| arm | weight | mean delta | wins | losses | ties | 95% CI | p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ts_rank title | 0.10 | +0.0018 | 8 | 5 | 27 | [-0.0008, +0.0047] | 0.581 |
| ts_rank title+abstract | 0.05 | +0.0027 | 10 | 2 | 28 | [+0.0008, +0.0049] | **0.039** |
| ts_rank_cd | 0.05 | +0.0013 | 4 | 1 | 35 | [-0.0002, +0.0031] | 0.375 |
| BM25 | 0.20 | +0.0033 | 15 | 9 | 16 | [-0.0011, +0.0079] | 0.307 |

By difficulty tercile, each arm at its own best weight:

| band | n | cosine | ts_title | ts_full | ts_cd | bm25 |
| --- | --- | --- | --- | --- | --- | --- |
| hard | 13 | 0.0501 | -0.0021 | +0.0019 | +0.0019 | +0.0004 |
| mid | 13 | 0.2015 | +0.0023 | +0.0030 | +0.0007 | +0.0050 |
| easy | 14 | 0.4028 | +0.0048 | +0.0033 | +0.0013 | +0.0045 |

Pool size, BM25 at w=0.2:

| k | cosine | + bm25 | delta |
| --- | --- | --- | --- |
| 100 | 0.1098 | 0.1124 | +0.0026 |
| 200 | 0.1622 | 0.1667 | +0.0045 |
| 400 | 0.2227 | 0.2261 | +0.0033 |
| 600 | 0.2567 | 0.2614 | +0.0047 |
| 1000 | 0.2774 | 0.3033 | +0.0259 |

The k=1000 row is not a semantic gain. `hnsw.ef_search` caps at 1000 and the date filter removes
part of that, so the cosine arm returns 668 to 947 rows and the lexical arm fills empty slots.

## Compound queries, 20 controlled topic pairs

Each pair is two unrelated surveys. The compound query is `"<title A> and <title B>"`. Recall is
measured per half against that half's own qrels.

| condition | per-half recall | vs ceiling |
| --- | --- | --- |
| each topic asked alone | 0.2082 | ceiling |
| compound query, 400 pool | 0.1233 | **-41%** |
| split, RRF, shared 400 pool | 0.1553 | -25% |
| split, 400 per clause | 0.2092 | **+0.0010** |

Split beats compound on 14 of 20 pairs. Sharing one pool between two clauses recovers 38% of the
loss; giving each clause its own pool recovers all of it.

## Ancestor expansion against leyline

Pool 400, ancestors gated at `min_citers >= 3` and cosine >= 0.30 capped at 120, leyline over a
wider graph (every 1-hop neighbour both directions at `min_citers >= 2`, no cosine floor, mean
2,641 nodes) also capped at 120. Magnets are the pool's top 40 by cosine, a grader-free proxy.

| beta | leyline adds | union adds | leyline beyond ancestors | jaccard | picks outside the ancestor set |
| --- | --- | --- | --- | --- | --- |
| 1.0 (shipped) | 0.0427 | 0.1828 | +0.0206 | 0.060 | 0.863 |
| 0.7 | 0.0510 | 0.1836 | +0.0214 | 0.075 | 0.819 |
| 0.5 | 0.0746 | 0.1907 | +0.0286 | 0.116 | 0.781 |
| 0.3 | 0.0921 | 0.1957 | **+0.0336** | 0.127 | 0.722 |

Baselines: pool hit at 400 is 0.2390, ancestors alone add 0.1622.

A first run scored leyline at +0.0000 beyond ancestors on all 20 surveys. That run built leyline's
graph from `pool + ancestors`, which makes its picks a subset of the ancestor set by construction.
The table above is the corrected run.

## Files

| file | what |
| --- | --- |
| `build_battery.py` | the 40-survey battery |
| `lexarms.py` | the five lexical arms, OR tsquery, Okapi BM25 over tsvector positions |
| `dump_pools.py` | one pass saving every arm's ranked list |
| `run_bakeoff.py` | fused recall per arm |
| `sweep_fusion.py` | weight sweep, difficulty terciles, pool-size sensitivity |
| `sig_test.py` | paired bootstrap and sign test |
| `run_decomp.py` | the compound-query pairs |
| `run_expand.py` | ancestors against leyline, beta swept |
| `figure.py` | `figures/lexical_and_decomp.png` |

---

## Cross-validation against the established 60-survey bench

`experiments/02-retrieval/02-01-benchmarks/cache/{battery60,qrels}.json`. That instrument differs
from the one above in three ways: 60 surveys from 2022 to 2024 rather than 40 from 2025 to 2026,
the query is the raw survey title, and the answer key is filtered by how many times the survey
mentions each reference.

| answer key | median qrels | cosine @400 | + ts_title (w 0.1) | + ts_full (w 0.05) | + bm25 (w 0.2) |
| --- | --- | --- | --- | --- | --- |
| mentions >= 1 | 113 | 0.2258 | +0.0014 | +0.0032 | +0.0047 |
| mentions >= 2 | 48 | 0.3173 | +0.0013 | +0.0024 | +0.0051 |
| mentions >= 3 | 23 | 0.3676 | +0.0010 | +0.0014 | +0.0040 |
| mentions >= 5 | 6 | 0.4510 | +0.0007 | +0.0018 | +0.0073 |

Paired bootstrap and sign test on the same 60:

| key | arm | mean | wins | losses | ties | 95% CI | p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| >= 1 | ts_full | +0.0032 | 7 | 0 | 53 | [+0.0007, +0.0065] | **0.016** |
| >= 1 | bm25 | +0.0047 | 16 | 8 | 36 | [+0.0013, +0.0085] | 0.152 |
| >= 3 | ts_full | +0.0014 | 1 | 0 | 59 | [+0.0000, +0.0041] | 1.000 |
| >= 3 | bm25 | +0.0040 | 7 | 2 | 51 | [+0.0001, +0.0085] | 0.180 |

Cosine at mentions >= 1 is 0.2258 here against 0.2227 on the 40-survey battery, so the two
instruments agree on the baseline despite a three-year gap in survey era. Every lexical delta is
under +0.008 on both.

Recall rises with the mention threshold, 0.2258 to 0.4510. A reference the survey actually
discusses is twice as retrievable as one it cites once.

## Files added

| file | what |
| --- | --- |
| `run_bench60.py` | the same arms against the frozen 60-survey battery and its mention-count qrels |

---

## Reachability ceiling of text retrieval

60-survey bench, every arm capped at 400.

| answer key | cosine | union of all four text arms | headroom | share of the key no text method reaches |
| --- | --- | --- | --- | --- |
| mentions >= 1 | 0.2258 | 0.3012 | +0.0754 | **0.746** |
| mentions >= 2 | 0.3173 | 0.4022 | +0.0849 | - |
| mentions >= 3 | 0.3676 | 0.4509 | +0.0833 | **0.570** |
| mentions >= 5 | 0.4510 | 0.5177 | +0.0666 | - |

Three quarters of what a survey cites is unreachable by cosine, ts_rank over titles, ts_rank over
abstracts and BM25 combined. Anything above 0.30 has to come from somewhere other than text.

## The walk is not what makes leyline work

Control: the same wide graph, the same magnets, no walk. Score each non-pool node by how many
magnets cite it or are cited by it, take the top 120. One `Counter` pass over the edge list.

| arm | recall added | with ancestors |
| --- | --- | --- |
| ancestors alone | 0.1618 | - |
| leyline, beta 0.3, walk + gamma + 10-seed vote | 0.0905 | 0.1933 (+0.0315) |
| **control, magnet-weighted degree, no walk** | **0.1599** | **0.2046 (+0.0428)** |

| | value |
| --- | --- |
| walk minus degree, on top of ancestors | **-0.0112** |
| jaccard(leyline picks, control picks) | 0.147 |

The two pick almost disjoint sets and the simpler one is better. The gain attributed to the
trajectory walk comes from widening the graph, not from walking it.

Caveat: magnets here are the pool's top 40 by cosine, not reader grades. Leyline is designed
around graded magnets and may behave differently with them. The control uses the same proxy, so
the comparison between them is fair, but neither is the shipped configuration.

---

# Part 2: the fair comparison

Two corrections to the section above. Recall is now taken over the **reachable** denominator, and
targets are **stratified by how niche they are**, since ancestors is built for core foundational
papers and leyline for niche ones, and an undifferentiated recall over a survey's reference list
is a hub-finding benchmark.

## Denominator

| | references | share |
| --- | --- | --- |
| has an embedding | 3,680 | 1.000 |
| has a citation edge to a pool paper | 2,669 | 0.725 |
| reachable by either | 3,680 | 1.000 |

The battery was built requiring `stage = 4` on every reference, so the denominator was already
reachable-only and the earlier numbers were not deflated by unreachable targets. On the 60-survey
bench, which has no such filter, this correction still needs applying.

## Recall over reachable references, by target nicheness

![by nicheness](figures/by_nicheness.png)

| band | refs | cosine pool | ancestors | leyline | magnet degree | pool-share ratio | pool + ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| niche, <10 citers | 598 | **0.2614** | 0.0000 | 0.0071 | 0.0221 | 0.0232 | 0.2846 |
| low, 10-49 | 1,062 | 0.2985 | 0.0156 | 0.0314 | 0.0488 | **0.0744** | 0.3729 |
| mid, 50-199 | 853 | **0.2372** | 0.0928 | 0.0726 | 0.1038 | 0.0602 | 0.2975 |
| hub, 200+ | 1,167 | 0.1213 | 0.3174 | 0.1804 | **0.3308** | 0.0085 | 0.1298 |
| all | 3,680 | 0.2227 | 0.1356 | 0.0891 | 0.1510 | 0.0404 | **0.2631** |

Arms, all off the same 400-paper cosine pool, all capped at 120 additions:

| arm | rule |
| --- | --- |
| ancestors | targets with >= 3 distinct pool citers and cosine >= 0.30, ranked by citer count |
| leyline | distance-decayed walk, beta 0.3, magnets are the pool's top 40 by cosine |
| magnet degree | same wide graph as leyline, scored by how many magnets link to the node |
| pool-share ratio | targets with >= 2 pool citers, ranked by pool citers over total citers |

## What the strata show

1. Cosine is the niche finder, not the graph. It recalls 0.2614 of targets with under 10 citers
   and only 0.1213 of targets with 200 or more.
2. Ancestors is the hub finder, and it is exactly that. 0.3174 on hubs, **0.0000** on niche. The
   `min_citers >= 3` gate cannot admit a paper with under 10 citers in the whole corpus, since
   three of them would have to sit in one 400-paper pool.
3. Every count-based graph arm inherits that bias, leyline included. Leyline recalls 0.0071 of the
   niche band, which is the band it was designed for, against cosine's 0.2614.
4. The pool-share ratio is the mirror image of ancestors: 0.0744 on the low band, 0.0085 on hubs.
   It is the only graph arm that is not a hub finder.
5. Leyline is dominated in every band. Cosine beats it on niche, low and mid; magnet degree beats
   it on mid and hub; ratio beats it on niche and low.

Caveat carried forward: magnets are the pool's top 40 by cosine, not reader grades.

## Files added

| file | what |
| --- | --- |
| `run_ablate.py` | the walk against plain magnet degree |
| `run_fair.py` | reachability denominator, nicheness strata, the ratio arm |
| `figure2.py` | `figures/by_nicheness.png` |

## Are the niche references reachable, and by what path

598 niche references (under 10 corpus citers) over 40 surveys. 149 enter the cosine pool, 449 do
not. How those 449 connect to the 400-paper pool:

| path | n | share |
| --- | --- | --- |
| no path within 2 hops | 241 | **0.537** |
| cites a pool paper (forward) | 117 | 0.261 |
| both directions | 44 | 0.098 |
| cited by a pool paper (backward) | 25 | 0.056 |
| 2 hops away | 22 | 0.049 |

Forward edges outnumber backward ones 117 to 25. `AncestorReranker` walks backward only, so it
cannot see the larger half whatever its gate is set to.

Of the 186 reachable in one hop, how many distinct pool papers link them:

| pool papers linking it | n | share | cumulative |
| --- | --- | --- | --- |
| 1 | 68 | 0.366 | 0.366 |
| 2 | 34 | 0.183 | 0.548 |
| 3 | 28 | 0.151 | 0.699 |
| 4 | 24 | 0.129 | 0.828 |
| 5 | 9 | 0.048 | 0.876 |
| 6 or more | 23 | 0.124 | 1.000 |

`min_citers >= 2` discards 36.6% of them, `min_citers >= 3` discards 54.8%.

Where the bridging pool paper sits in the 400, and what a smaller pool would cost:

| | rank |
| --- | --- |
| p25 | 13 |
| p50 | 46 |
| p75 | 116 |
| p90 | 266 |
| max | 393 |

| pool size | 1-hop niche references still reachable |
| --- | --- |
| 50 | 98 (0.527) |
| 100 | 125 (0.672) |
| 200 | 155 (0.833) |
| 400 | 186 (1.000) |

## Cost of the expansion that would reach them

Mean candidates per query off a 400-paper pool.

| min_citers | forward | backward | total |
| --- | --- | --- | --- |
| 1 | 5,892 | 4,740 | 10,633 |
| 2 | 1,381 | 1,433 | 2,814 |
| 3 | 591 | 773 | 1,364 |

The shipped ancestor step is the bottom-right cell, 773 candidates. Reaching the niche band needs
the top-left one, 5,892, a 10x candidate set.

## Ceiling

Admitting and correctly ranking all 186 one-hop niche references would move niche recall from
0.2614 to 0.572. That is the prize, and 241 references (0.537 of the niche misses) stay out of
reach of any graph method at any gate.

## Files added

| file | what |
| --- | --- |
| `run_paths.py` | path analysis and expansion cost for the niche band |

## Graph distance from the pool to a reference

Undirected breadth-first expansion from the 400-paper cosine pool, 20 surveys.

| distance | papers at exactly this distance | cumulative | share of the corpus |
| --- | --- | --- | --- |
| 0 | 400 | 400 | 0.013% |
| 1 | 9,888 | 10,288 | 0.331% |
| 2 | 327,520 | 337,808 | **10.884%** |

Share of a survey's references sitting at each distance:

| class | n | d=0 | d=1 | d=2 | >2 |
| --- | --- | --- | --- | --- | --- |
| niche, <10 citers | 235 | 0.285 | 0.298 | **0.336** | 0.081 |
| hub, 200+ citers | 645 | 0.102 | **0.795** | 0.102 | 0.000 |
| all | 1,825 | 0.221 | 0.564 | 0.195 | 0.020 |

Hubs are one hop away and nothing else: 79.5% at exactly d=1, none past d=2. Niche references are
spread, with the largest single group at d=2 and 8.1% past it.

Cost per niche reference caught:

| tier | candidates added | niche references reached | candidates per reference |
| --- | --- | --- | --- |
| d=1 | 9,888 | 0.298 | ~141 |
| d=2 | 327,520 | 0.336 | ~4,140 |

The second hop costs 33x the candidates for the same yield, and enumerating it means holding a
tenth of the corpus.

## Files added

| file | what |
| --- | --- |
| `run_distance.py` | undirected BFS distance from pool to reference, by target class |
