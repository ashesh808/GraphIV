# 02-04-fusion-rule

**What:** 02-03 found two signals of equal strength that disagree about a fifth of the gold each.
This asks how to spend one budget of 80 slots across both.
Fifteen combining rules, same pool, same slots, no frontier reservation and no LeyLine quota, so
only the rule varies.
Selection reads dev; test is printed once.

**Conclusion:** the combining rule barely matters and the choice of input matters enormously.
Every smooth rule lands within 18 papers of every other.
Swapping cosine for citations per year inside the same multiplication is worth 39.

Run: `uv run python run.py` (reads `cache/fusion.json`, a few seconds).

## The bounds

| | dev | test |
| --- | --- | --- |
| gold in pool | 419 | 441 |
| oracle at the same budget | 419 | 441 |
| best single signal | 287 | 310 |

Every in-pool gold paper fits inside 80 slots, so the oracle is the whole in-pool set and the
headroom above one signal is 132 papers on dev.

## The rules

| rule | family | dev | test | headroom taken |
| --- | --- | --- | --- | --- |
| **blend 0.5 graph** | smooth | **333** | **341** | **35%** |
| blend 0.65 graph (shipped) | smooth | 332 | 335 | 34% |
| multiply, graph x grade | smooth | 331 | 338 | 33% |
| blend 0.35 graph | smooth | 330 | 343 | 33% |
| grade first, graph breaks ties | smooth | 324 | 338 | 28% |
| blend 0.8 graph | smooth | 318 | 322 | 23% |
| rrf, graph + reader | smooth | 317 | 344 | 23% |
| rrf, all three | smooth | 315 | 345 | 21% |
| quota 60 graph / 20 reader | hard split | 299 | 334 | 9% |
| quota 40 graph / 40 reader | hard split | 298 | 339 | 8% |
| quota 20 graph / 60 reader | hard split | 294 | 335 | 5% |
| multiply, cosine x grade | weak input | 292 | 303 | 4% |
| graph only | single | 287 | 310 | 0% |
| reader only | single | 284 | 312 | -2% |
| cosine only | single | 190 | 209 | -73% |

## Three findings

**The rule is not the lever.**

| family | rules | best | worst | spread |
| --- | --- | --- | --- | --- |
| smooth blend | 8 | 333 | 315 | 18 |
| hard split | 3 | 299 | 294 | 5 |
| single signal | 3 | 287 | 190 | **97** |

Eight different ways of smoothly combining two signals land within 18 papers of each other.
Picking a different signal moves 97.
Multiplication, weighted blending, reciprocal rank fusion and grade-first sorting are the same
answer written four ways.

**The input was the problem, not the arithmetic.**
The same multiplication scores 292 with cosine and 331 with citations per year, a gap of 39 papers
on dev and 35 on test.
So a fusion of a retrieval signal with the reader's grade was the right shape all along; cosine was
just the wrong retrieval signal, which 02-03 measured directly at 1.9x lift against the graph's
2.9x.

**Hard splits lose.**
Reserving n slots for one signal and the rest for the other tops out at 299, below every smooth
rule.
Interleaving matters: a paper that is second-best on both signals should outrank a paper that is
best on one and absent from the other, and a quota cannot express that.

## What is still on the table

The best rule takes 35 percent of the headroom.
86 dev papers sit in the pool, are visible to at least one signal, and are not selected by any rule
here.
Closing that is a selection problem rather than a fusion problem, which is 02-05.

## A note on dev and test

`rrf, all three` ranks eighth on dev and first on test.
Arms were chosen on dev, so `blend 0.5` ships; the reversal is a reminder that the per-arm gaps
inside the smooth family are smaller than the split-to-split noise.
