# leyline-tune

Ranking the three-channel candidate set of one survey down to 1,000, with the final budget
being the only constraint.

## Configuration

| item | value |
| --- | --- |
| case | `2504.21853`, Interactive Generative Video, 2025-04-30 |
| answer key | 136 resolved stage-4 references dated before the survey |
| universe | 35,611 candidates, cosine seed to depth 2,000 plus one citation hop each way |
| edges among candidates | 994,355 |
| ceiling | 0.956, 130 of 136 |

## Ranking

| stage | R@1000 |
| --- | --- |
| cosine only | 0.257 |
| leyline flow, row-normalized transition matrix | 0.449 |
| leyline flow, tuned anchors | 0.529 |
| plus peer channel, propagation directions mislabeled | 0.588 |
| plus directions fixed | 0.625 |
| plus peer frontier tuned to top-500 | 0.647 |

## Single features, seed 200

| feature | R@1000 |
| --- | --- |
| peer, what the recent frontier of the seed cites | 0.574 |
| anc, what the seed cites | 0.441 |
| fro, what cites the seed | 0.375 |
| cocite | 0.331 |
| cos | 0.228 |
| rec | 0.044 |

## Depth curve of the tuned ranking

| k | recall | references | precision |
| --- | --- | --- | --- |
| 200 | 0.213 | 29 | 0.1450 |
| 500 | 0.404 | 55 | 0.1100 |
| 1000 | 0.647 | 88 | 0.0880 |
| 2000 | 0.699 | 95 | 0.0475 |
| 3000 | 0.743 | 101 | 0.0337 |
| 5000 | 0.831 | 113 | 0.0226 |
| 10000 | 0.934 | 127 | 0.0127 |
| 20000 | 0.941 | 128 | 0.0064 |

## Propagation direction, measured not assumed

| operator | mean age of its top 300 |
| --- | --- |
| `A @ seed` | 4.33 yr |
| `A.T @ seed` | 0.94 yr |
| seed itself | 1.97 yr |

## Rankers that did not work

| approach | R@1000 |
| --- | --- |
| re-seed the anchors from the ranking, 1 iteration | 0.478 |
| re-seed, 2 iterations | 0.346 |
| centroid of the graph top-M, cosine to it | 0.213 |
| kNN vote against the graph top-M | 0.213 |
| fused with the graph ranking | 0.581 |
| boosted trees, out-of-fold | 0.419 |
| logistic, in-sample | 0.603 |
| boosted trees, in-sample | 0.897 |

The in-sample tree fit is memorization: 130 positives in 35,611 rows, AUC 0.975 in-sample
against 0.759 out of fold.

## Feature importance, AUC drop when shuffled

| feature | drop |
| --- | --- |
| anc | 0.1497 |
| rec | 0.1241 |
| age | 0.1034 |
| cocite | 0.0472 |
| indeg | 0.0425 |
| peer_norm | 0.0391 |
| fro2 | 0.0349 |
| fro | 0.0299 |
| peer | 0.0093 |
| cos | 0.0031 |
| outdeg | 0.0028 |
| anc2 | -0.0045 |

## Files

```
build.py       the candidate set, hops and edges for one survey
rank.py        first ranker comparison
sweep.py       anchor sets and walk decay
diag.py        feature separation and the link threshold curve
tune.py        feature combination search
tune2.py       seed depth and anchor re-seeding
final.py       centroid and kNN reranking
final2.py      the same with propagation directions named correctly
peer.py        the peer channel construction
best.py        the tuned ranking and its depth curve
ceilingfit.py  learned rankers, in-sample and out-of-fold
embfetch.py    candidate embeddings
case.json      the case, 35,611 candidates and 994,355 edges
emb.npy        candidate embeddings
```
