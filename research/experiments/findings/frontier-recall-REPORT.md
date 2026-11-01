# frontier-recall

Recall of the frontier: given a topic as it stood at one survey's date, find the papers that
appeared afterward and that a later survey on the same topic judged worth citing.

## The answer key

No thresholds and no citation cutoffs. The key is one human's citation decision, the same
construction SurveyMatch uses, shifted forward in time.

| step | rule |
| --- | --- |
| pair | survey S2 cites survey S1, same `level_1`, at least 9 months apart, both after 2024-01 |
| query | S1's title with the survey boilerplate stripped |
| retrieval cap | `date <= S2.date`, so everything S2 could see is visible |
| answer key | S2's resolved stage-4 references dated in (S1.date, S2.date] |
| lineage key | S1's own resolved references dated on or before S1.date |
| kept | key size 25 to 250 |

| quantity | value |
| --- | --- |
| candidate pairs in the corpus | 6,239 |
| pairs used | 20 |
| answer key size, p50 | 63 |
| gap between surveys, p50 | 13 months |
| candidates per pair | cosine seed 5,000 plus one citation hop each way off the top 200 |
| answer-key papers inside the candidate set | 0.694 |

## Both keys at once, recall at 1000

| arm | frontier | lineage | new papers in top 1000 |
| --- | --- | --- | --- |
| peer recent, hub 0.7 | 0.582 | 0.376 | 634 |
| peer recent, hub 0.5 | 0.564 | 0.448 | 579 |
| peer recent, hub 0.3 | 0.509 | 0.544 | 492 |
| graph hub 0.5, rec^3 | 0.440 | 0.718 | 317 |
| graph, hub 1.5 | 0.440 | 0.619 | 318 |
| graph, hub 1.0 | 0.435 | 0.711 | 302 |
| peer, recent only | 0.421 | 0.631 | 364 |
| graph hub 0.5, rec^2 | 0.420 | 0.741 | 286 |
| graph, hub 0.7 | 0.415 | 0.751 | 271 |
| graph, hub 0.5 | 0.379 | 0.766 | 241 |
| graph, hub 0.3 | 0.328 | 0.767 | 210 |
| graph | 0.257 | 0.763 | 173 |
| frontier channel | 0.247 | 0.044 | 946 |
| cosine | 0.186 | 0.267 | 576 |
| frontier + hub 0.3 | 0.174 | 0.011 | 972 |
| citation velocity | 0.139 | 0.491 | 148 |
| cosine x recency | 0.136 | 0.000 | 1000 |
| recency only | 0.097 | 0.000 | 1000 |

`hub a` divides the score by `(1 + citations held at query time)^a`.

## Frontier recall by how known the target already was

Citations held at query time, excluding the later survey's own citation.

| | uncited | 1-4 | 5-19 | 20+ |
| --- | --- | --- | --- | --- |
| mean key papers per pair | 14.9 | 26.3 | 23.4 | 19.6 |
| share inside the candidate set | 0.585 | 0.676 | 0.725 | 0.764 |

| arm | uncited | 1-4 | 5-19 | 20+ |
| --- | --- | --- | --- | --- |
| peer recent, hub 0.7 | 0.571 | 0.561 | 0.581 | 0.601 |
| peer recent, hub 0.5 | 0.526 | 0.505 | 0.571 | 0.648 |
| graph, hub 1.0 | 0.400 | 0.395 | 0.416 | 0.508 |
| graph, hub 0.7 | 0.376 | 0.349 | 0.402 | 0.519 |
| graph, hub 0.5 | 0.226 | 0.305 | 0.393 | 0.521 |
| cosine | 0.126 | 0.188 | 0.194 | 0.215 |
| citation velocity | 0.000 | 0.013 | 0.074 | 0.496 |
| graph | 0.000 | 0.140 | 0.317 | 0.521 |

## Sanity check on the metric

| arm | frontier recall | new papers in top 1000 |
| --- | --- | --- |
| recency only | 0.097 | 1000 |
| cosine x recency | 0.136 | 1000 |

Filling the entire result with new papers scores worst, so the metric is not a recency proxy.

## Correction made during this run

The first stratification read citation counts out of `cases/*.json`, which `build.py` only
populated for papers inside the candidate set, so `cites.get(a, 0)` assigned zero to every
answer-key paper that was missing from it. The uncited band was therefore defined as the papers
we failed to retrieve, and every arm scored 0.000 on it by construction. `keycites.py` fetches
the true counts for all answer-key papers and `strata2.py` supersedes `strata.py`. The two-key
recall table above never depended on those counts and is unaffected.

## Files

```
pairs.py     builds the survey pairs and both answer keys
build.py     per-pair retrieval, hops, edges, citation counts
score.py     the arms, scored on both keys
keycites.py  true citation counts for every answer-key paper
strata2.py   recall by how known the target already was
reach.py     candidate-set coverage per band
strata.py    superseded, kept as the record of the correction
```

## Sampled walk against closed-form propagation

Same 20 pairs, same candidate sets, same anchors. Sources are the top 500 by seed-citation
count, magnets the top 500 recent frontier papers, walk runs old to new. The only variable
between the two leyline rows is gamma, the suppression applied to a magnet once a lineage has
collected it.

Budget A: 10 seeds, 60 lineages, 2 children per step, 20 pairs

| arm | frontier | lineage |
| --- | --- | --- |
| peer, full score | 0.415 | 0.751 |
| leyline, full score | 0.280 | 0.579 |
| peer + leyline | 0.250 | 0.669 |
| peer closed form | 0.228 | 0.715 |
| leyline g=1.0, no suppression | 0.030 | 0.479 |
| leyline g=0.4 | 0.029 | 0.472 |

| marginal, answer-key papers per pair | mean |
| --- | --- |
| leyline finds, peer misses | 1.25 |
| peer finds, leyline misses | 11.55 |
| union recall | 0.426 |
| top-1000 overlap between g=0.4 and g=1.0 | 0.828 |

Budget B: 20 seeds, 250 lineages, 4 children per step, 5 pairs

| arm | frontier | lineage |
| --- | --- | --- |
| peer, full score | 0.316 | 0.909 |
| peer closed form | 0.240 | 0.903 |
| peer + leyline | 0.065 | 0.781 |
| leyline, full score | 0.031 | 0.727 |
| leyline g=1.0, no suppression | 0.003 | 0.643 |
| leyline g=0.4 | 0.001 | 0.626 |

| marginal, answer-key papers per pair | mean |
| --- | --- |
| leyline finds, peer misses | 0.00 |
| peer finds, leyline misses | 30.40 |
| union recall | 0.316 |
| top-1000 overlap between g=0.4 and g=1.0 | 0.918 |

Raising the sampling budget 20x lowered the standalone score and raised the overlap between
suppressed and unsuppressed runs from 0.828 to 0.918.

## Profile of a missed answer-key paper

Best frontier arm, `peer recent, hub 0.7`, 20 pairs, 1,683 answer-key papers, 861 found.

| feature | found p10 | p50 | p90 | missed p10 | p50 | p90 |
| --- | --- | --- | --- | --- | --- | --- |
| cosine | 0.356 | 0.464 | 0.571 | 0.286 | 0.374 | 0.461 |
| corpus cosine rank | 276 | 2,715 | 36,786 | 5,119 | 33,024 | >50,000 |
| citations at query time | 0 | 5 | 41 | 0 | 4 | 41 |
| months before the later survey | 1.9 | 6.4 | 13.0 | 1.7 | 6.2 | 12.6 |
| graph hop from the 200-paper seed | 1 | 1 | 1 | 1 | 2 | 2 |

### By graph hop

| hop | papers | share of the misses | found rate |
| --- | --- | --- | --- |
| 0, in the seed | 69 | 0.1% | 98.6% |
| 1, one hop | 1,015 | 27.0% | 78.1% |
| 2, two hops | 599 | 72.9% | 0.0% |
| 3 or more | 0 | | |

### By corpus cosine rank

| rank | papers | share of the misses | found rate |
| --- | --- | --- | --- |
| 0-400 | 128 | 1.0% | 93.8% |
| 400-2,000 | 296 | 4.0% | 88.9% |
| 2,000-5,000 | 208 | 4.6% | 81.7% |
| 5,000-20,000 | 376 | 25.8% | 43.6% |
| beyond 20,000 | 675 | 64.6% | 21.3% |

### By citations held at query time

| citations | papers | share of the misses | found rate |
| --- | --- | --- | --- |
| uncited | 299 | 18.7% | 48.5% |
| 1-4 | 526 | 31.8% | 50.4% |
| 5-19 | 467 | 27.7% | 51.2% |
| 20+ | 391 | 21.8% | 54.2% |

## Entropy of the found/missed label

| conditioned on | H(found given x), bits | information gained |
| --- | --- | --- |
| nothing | 0.9996 | 0.0000 |
| graph hop | 0.4615 | 0.5381 |
| cosine rank band | 0.7198 | 0.2798 |
| cosine decile | 0.7938 | 0.2058 |
| age in months | 0.9943 | 0.0053 |
| citations at query time | 0.9982 | 0.0014 |
| graph hop and cosine rank band | 0.4339 | 0.5658 |
| those two and citations | 0.4097 | 0.5899 |

## Hop distribution of the whole answer key

| hop | papers | share | median cosine rank | median cosine |
| --- | --- | --- | --- | --- |
| 0 | 69 | 4.1% | 85 | 0.587 |
| 1 | 1,015 | 60.3% | 4,040 | 0.448 |
| 2 | 599 | 35.6% | 41,825 | 0.364 |
| 3+ | 0 | 0.0% | | |

## Coverage by candidate rule

| rule | coverage of the answer key |
| --- | --- |
| cosine top 5,000 alone | 0.376 |
| cosine top 20,000 alone | 0.599 |
| cosine top 50,000 alone | 0.777 |
| cosine top 200 plus one hop | 0.644 |
| cosine top 20,000 plus one hop | 0.739 |
| cosine top 50,000 plus one hop | 0.840 |
| two hops, any cosine | 1.000 |

## Scope of the sampled-walk null result

The walk was run on the graph induced on the candidate set, which is hop 0 and hop 1 only. The
35.6% of the answer key at hop 2 was absent from that graph, so the null result covers ranking
within a one-hop neighborhood and says nothing about whether a walk that leaves it can reach
the papers at hop 2.

## Leyline on the real two-hop graph

The walk now runs on the citation graph itself, not on the graph induced on the candidate set.
Sources are the top 500 by seed-citation count, magnets the top 500 by recency times cosine over
the whole two-hop graph, walk runs old to new.

| item | value |
| --- | --- |
| pairs | 10 |
| nodes per pair | 251,485 to 317,466 |
| edges per pair | 1.3M to 1.6M |
| walk budget | 4 seeds, 80 lineages, 3 children per step, max length 10 |

| arm | frontier | lineage | hop-2 recall |
| --- | --- | --- | --- |
| peer, two-hop graph | 0.519 | 0.581 | 0.166 |
| cosine | 0.217 | 0.296 | 0.000 |
| closed-form flow | 0.023 | 0.447 | 0.000 |
| leyline walk g=0.4 | 0.007 | 0.422 | 0.000 |
| leyline walk g=1.0 | 0.003 | 0.424 | 0.000 |
| leyline raw visits | 0.002 | 0.401 | 0.000 |

### Where the walk goes

| pair | nodes touched | share of graph | median age touched | median age graph | magnets reached of 500 | key papers touched |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1,475 | 0.51% | 5.55 yr | 2.40 yr | 1 | 0 of 27 |
| 2 | 1,506 | 0.47% | 2.64 yr | 2.35 yr | 0 | 0 of 75 |
| 3 | 1,595 | 0.63% | 2.28 yr | 2.10 yr | 1 | 1 of 134 |
| 4 | 1,703 | 0.52% | 3.05 yr | 2.30 yr | 0 | 2 of 61 |

At 8 seeds and 200 lineages the same pairs touch 2,864 and 2,848 nodes, 1.00% and 0.90% of the
graph, and still reach 1 magnet of 500. Ten times the budget does not change the outcome.

### Transform sensitivity, and one wrong table

`nz` followed by `log1p` collapses a quantity spanning many orders of magnitude to exactly zero
for almost every node, leaving the top 1,000 arbitrary among hundreds of thousands of ties. The
first two-hop table reported 0.000 for closed-form flow for that reason rather than on merit. A
percentile rank transform fixes the ties but spreads the tied zeros across the range, which cost
`peer` 0.377 frontier. The table above uses a log scaled by the median positive value, which
keeps zeros at zero and spreads the positives.
