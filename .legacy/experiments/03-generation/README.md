# 03-generation

Does the writer make things up. One metric across every experiment here: whether a sentence in
a finished report is backed by a paper.

## Experiments

```
03-01-attribution       are the cited sentences supported by the paper they cite
03-02-checker-validity  can the checker say no when a citation is deliberately broken
03-03-graph-digest      does the citation graph in the prompt change either number
03-04-source-coverage   how much of a report carries a citation at all
```

## Results

| # | finding |
| --- | --- |
| 03-01 | about seven in ten cited sentences are supported, 0.714 and 0.744 across two judge families, agreeing on 90.6% of individual sentences (kappa 0.762) |
| 03-02 | the checker approves 17% of broken citations against 70% of real ones, a gap of 0.53 that both judges reproduce to three decimals |
| 03-03 | the graph leaves reliability alone: support 0.707 with it against 0.754 without, no-graph ahead in 8 of 10 matched pairs, coverage and catch rate unchanged |
| 03-04 | 818 of 1372 sentences carry a citation, 0.596, counted without a model |

Read 03-02 before 03-01. A support rate only means something once the checker has been shown
able to reject.

## What is not measured, and why

How many uncited sentences invent something. Two schemes were tried and both failed. A five-way
label (filler, caption, restatement, conclusion, new fact) split 37 against 67 between the two
judges. Collapsing to one yes-or-no question made it worse, 12 against 91, kappa 0.003, which is
chance. The question has no fixed answer: a sentence like "the field moved from X to Y" is a
restatement under a generous reading and a new claim under a strict one. A cited sentence has a
document to check against and an uncited one has only the reader's threshold. Splitting those
284 sentences needs human labels, not a better prompt.

## What was removed

Eleven earlier experiments measured levers rather than reliability, and most rested on a
27-topic battery that is no longer trusted. They were deleted on 2026-08-27, recoverable from
commit `3326281`. Their findings survive as prose in `docs/decisions.md`, which is where they
were always read from.

```
03-01-judge-validity      03-06-landmark-selection
03-02-component-ablation  03-07-graph-representation
03-03-embedding-format    03-08-judge-loop
03-04-recency-knob        03-09-critique-depth
03-05-frontier-pull       03-10-vision-figures
                          03-11-hub-suppression
```
