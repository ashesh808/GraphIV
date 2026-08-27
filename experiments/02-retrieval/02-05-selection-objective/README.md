# 02-05-selection-objective

**What:** every selection objective ever proposed for this pipeline on one table.
60 survey pools, 80 slots each, answer key is the survey's own references at three or more
mentions.
Run after the pool score fix from 02-03, so no graph arm is handicapped by a broken input.

**Conclusion:** the family ordering is clean.
Fusion beats the graph alone, the graph alone beats text, and text beats set coverage.
The old verdict that PPR beats the set-coverage objectives holds on external gold.
The new one is that PPR loses to almost everything else.

Run: `uv run python run.py` (reads `cache/selectors.json`, a few seconds).

## The table

Gold in pool: dev 419, test 441.

| selector | family | dev | test | before the score fix | moved |
| --- | --- | --- | --- | --- | --- |
| oracle (every in-pool gold) | bound | 412 | 436 | 436 | +0 |
| **joint (shipped)** | fused | **336** | **341** | 341 | +0 |
| citations per year alone | graph | 305 | 310 | 310 | +0 |
| LeyLine on frontier | fused | 295 | 315 | 318 | -3 |
| RRF(ppr, frontier) | fused | 293 | 298 | 290 | +8 |
| frontier | graph | 288 | 322 | 320 | +2 |
| trajectory (LeyLine on ppr) | fused | 279 | 302 | 290 | +11 |
| ppr, no reservation | graph | 266 | 270 | | |
| ppr | graph | 265 | 293 | 277 | +16 |
| in-degree | graph | 261 | 261 | 260 | +1 |
| cosine x grade, top-k | text | 208 | 236 | | |
| mmr | set coverage | 196 | 213 | | |
| cluster proportional | set coverage | 184 | 209 | | |
| facility location | set coverage | 166 | 176 | | |

## Best of each family

| family | best arm | dev |
| --- | --- | --- |
| fused | joint | 336 |
| graph | citations per year alone | 305 |
| text | cosine x grade, top-k | 208 |
| set coverage | mmr | 196 |

The gap from set coverage to fusion is 140 papers.
Nothing else in the whole retrieval stage moves a number that size.

## What the score fix changed

Every arm that reads the pool score gained, and every arm that ignores it did not.

ppr gained 16 papers, trajectory 11, RRF 8.

Trajectory reads 279/302 rather than 301 on test because the selector refactor replaced its
bespoke backfill, which recomputed PageRank over the unpicked remainder, with the shared one.
101 of 4800 ids differ and the count moves +5 dev and +1 test.
joint, citations per year and the oracle are unchanged, because none of them touches the score.

That matters for reading the older write-ups.
The `02-06-selection-objective` result that PPR is vindicated was measured while a fifth of every
pool sat a hundred times too low on the score PPR seeds from.
The verdict survives the correction against set coverage and does not survive against fusion.

## Set coverage is genuinely bad here, and the reason is the task

Facility location picks 166 papers where joint picks 336.
Those objectives spread slots to cover the pool's embedding space, and a survey's reference list is
not spread out.
It is concentrated on a lineage, with foundations that are similar to each other and get treated as
redundant by any coverage rule.

That is the same effect as 02-01's LitSearch inversion seen from the other side.
The shape of the answer decides which objective is right, and this answer is a cluster rather than
a spread.

## What is left

The oracle is 412 on dev and joint reaches 336.
76 papers per split sit in the pool and are not selected.
02-04 showed no combining rule closes that, so the remaining loss is in what the signals can see,
not in how they are mixed.
