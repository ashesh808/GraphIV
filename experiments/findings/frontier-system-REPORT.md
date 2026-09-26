# frontier-system

What the frontier of a research area is, asked at a date in the past so the future can score it.

## Configuration

| item | value |
| --- | --- |
| question date | 2025-03-01 |
| citation graph runs to | 2026-09-10, so 18 months of future |
| personas | 5, each a brief saying what they know and what they are deciding |
| answer | top 20 |
| recency window | 365 days before the question |
| reference reviews | reviews published in the 18 months after, within 0.07 cosine of the closest |
| answer key | what those reviews cite that is dated inside the window |
| retrieval | cosine seed 5,000, one citation hop each way, capped at the question date |

## The four things an answer is scored on

| name | what it asks | produced by |
| --- | --- | --- |
| percentile | where the 20 sit in the later-citation distribution of the window | `truth.judge` |
| review P@20 | share of the 20 that a later review went on to cite | `truth.precision_of` |
| breakout | share of the window's true top 10 by later citations that the 20 caught | `tune_frontier.breakout` |
| absorbed | share of the 20 some later review cites at all | `truth.judge` |

## Every system, mean over the 5 personas

Written by `report.py` out of `results/verdicts_*.json`. `effort_0` and `recent_graph_survey` are
the same thing by construction, which is the wiring check.

| system | score | P@20 | R@200 | absorbed | cites before | cites after | seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| effort_1 | 0.929 | 0.670 | 0.448 | 0.88 | 19 | 140 | 0.7 |
| recent_graph_survey | 0.931 | 0.640 | 0.463 | 0.88 | 20 | 154 | 1.2 |
| effort_0 | 0.931 | 0.640 | 0.463 | 0.88 | 20 | 154 | 0.7 |
| effort_4 | 0.882 | 0.600 | 0.429 | 0.83 | 14 | 86 | 41.8 |
| recent_graph_frontier | 0.878 | 0.570 | 0.425 | 0.81 | 8 | 88 | 1.2 |
| effort_2 | 0.917 | 0.500 | 0.454 | 0.86 | 16 | 95 | 4.8 |
| effort_3 | 0.887 | 0.460 | 0.393 | 0.82 | 22 | 91 | 5.8 |
| recent_cosine | 0.735 | 0.400 | 0.328 | 0.64 | 3 | 22 | 1.2 |
| graph_survey | 0.478 | 0.370 | 0.337 | 0.91 | 182 | 274 | 1.2 |
| cosine | 0.406 | 0.240 | 0.252 | 0.53 | 5 | 20 | 1.2 |
| newest | 0.514 | 0.030 | 0.066 | 0.36 | 0 | 4 | 1.2 |
| most_cited | 0.000 | 0.000 | 0.010 | 1.00 | 14817 | 6572 | 1.2 |

The same table under the exponents `tune_frontier.py` settled on:

| system | score | P@20 | R@200 | absorbed | cites before | cites after | seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| effort_0 | 0.943 | 0.730 | 0.442 | 0.92 | 25 | 145 | 0.7 |
| effort_1 | 0.939 | 0.720 | 0.436 | 0.92 | 23 | 141 | 0.7 |
| effort_2 | 0.928 | 0.580 | 0.440 | 0.89 | 23 | 128 | 5.4 |
| effort_4 | 0.879 | 0.570 | 0.396 | 0.84 | 15 | 97 | 40.2 |
| effort_3 | 0.929 | 0.470 | 0.378 | 0.86 | 28 | 115 | 5.9 |

1) The tuned exponents are worth +0.09 precision at 20 over the shipped ones, for no extra time.
2) Every stage that puts a language model in the retrieval path loses, and the widest one costs
   40 seconds to lose 0.16.
3) `most_cited` returns papers holding a mean 14,817 citations, which is the canon, not a frontier.

## What separates a key paper from the rest of its window

AUC of each signal over the window, produced by `analyze.py`.

| signal | tabular | mechinterp | litsearch | diffusionlm | testtime |
| --- | --- | --- | --- | --- | --- |
| graph score | 0.933 | 0.948 | 0.848 | 0.943 | 0.826 |
| anc_decay | 0.838 | 0.830 | 0.796 | 0.851 | 0.741 |
| cocite | 0.774 | 0.821 | 0.825 | 0.756 | 0.844 |
| couple | 0.896 | 0.888 | 0.675 | 0.785 | 0.684 |
| cos | 0.884 | 0.880 | 0.563 | 0.807 | 0.726 |
| anc | 0.767 | 0.794 | 0.795 | 0.760 | 0.637 |
| fro2 | 0.854 | 0.871 | 0.500 | 0.784 | 0.736 |
| fro | 0.865 | 0.892 | 0.463 | 0.795 | 0.641 |
| cited_at_t | 0.690 | 0.703 | 0.771 | 0.695 | 0.776 |
| anc2 | 0.709 | 0.715 | 0.802 | 0.691 | 0.701 |
| fro_decay | 0.742 | 0.790 | 0.501 | 0.648 | 0.498 |
| age | 0.487 | 0.582 | 0.394 | 0.559 | 0.513 |

3) Recency on its own is AUC 0.5, so which recent paper matters is not told by how recent it is.
4) The combined graph score already reaches 0.83 to 0.95, and the key is 2 to 3 percent of the
   window, which is why a top 20 cannot be much cleaner than it is.

## The tracked case

`2502.05564` TabICL, 21 days old at the question date, 0 citations before it and 193 after,
and in the answer key.

| setting | review P@20 | percentile | breakout | TabICL rank in the window |
| --- | --- | --- | --- | --- |
| shipped survey exponents | 0.640 | 0.931 | 0.080 | 35 |
| tuned on the review key | 0.730 | 0.943 | 0.080 | 54 |
| tuned on the percentile | 0.630 | 0.971 | 0.460 | 450 |
| tuned on breakout | 0.610 | 0.966 | 0.480 | 453 |

Its channels under the shipped exponents:

| cos | fro | fro2 | couple | anc | anc2 | cocite | hub |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.887 | 0.840 | 0.855 | 0.828 | 0.000 | 0.000 | 0.000 | 0.000 |

5) `anc = A @ core` asks whether the core cites the paper, so it is zero for anything too new to
   have been cited, and the shipped recipe puts its largest exponent on that channel.
6) Every objective built from citations moves TabICL down, because each of them rewards papers
   that were already being noticed at the question date.

## The cold breakouts

A cold breakout is a paper the window holds that had zero citations at the question date and
reached 20 or more in the 18 months after. Produced by `cold.py`.

| persona | window | cold breakouts | in the graph top 20 | in the successor top 20 | in the successor set | best graph rank |
| --- | --- | --- | --- | --- | --- | --- |
| tabular | 2,601 | 30 | 0 | 2 | 3 | 41 |
| mechinterp | 2,456 | 49 | 0 | 5 | 14 | 125 |
| litsearch | 2,052 | 43 | 0 | 4 | 11 | 181 |
| diffusionlm | 8,137 | 195 | 0 | 7 | 45 | 74 |
| testtime | 7,530 | 240 | 0 | 2 | 63 | 154 |

10) The graph score returns none of the 557 cold breakouts in any of the five top twenties, and
    the highest any of them reaches is rank 41.
11) The successor set, read off the `extends`, `critiques` and `compares` edges pointing at the
    answer, is the only thing that reaches them, and it needs no citations of the candidate.

## What the successor set finds, tabular

| reach | date | paper |
| --- | --- | --- |
| 6 | 2025-02-04 | `2502.02527` TabPFN Unleashed |
| 4 | 2025-02-24 | `2502.17361` A Closer Look at TabPFN v2 |
| 2 | 2024-10-23 | `2410.18164` TabDPT |
| 2 | 2024-10-31 | `2410.24210` TabM |
| 2 | 2025-02-08 | `2502.05564` TabICL |

Median citations held at the question date, over the successor top 20: 0 for every persona.
Median citations received after: 6 tabular, 34 litsearch, 20 mechinterp.

12) The two populations want different mechanics, so the answer is two sections rather than one
    ranking: what the area currently is, and what has just appeared against it.

## Why the window was the wrong reference

Top of the tabular window by citations received after the question, before any area filter:

| rank | later cites | paper |
| --- | --- | --- |
| 1 | 12,063 | `2407.21783` The Llama 3 Herd of Models |
| 2 | 1,967 | `2407.10671` Qwen2 Technical Report |
| 3 | 1,213 | `2412.05271` InternVL 2.5 |
| 4 | 876 | `2502.14786` SigLIP 2 |
| 5 | 800 | `2403.04132` Chatbot Arena |
| 14 | 193 | `2502.05564` TabICL |

7) Citation expansion reaches the general canon of machine learning from any question inside it,
   so the window is led by whatever was large that year rather than by the area.

## Holding the window to the area

| area rule | window | key kept | TabICL rank |
| --- | --- | --- | --- |
| none | 2,601 | 51 of 75 | 14 |
| topic tree level_1, 0.80 of the vote | 1,584 | 42 of 75 | 6 |
| topic tree level_2, 0.80 of the vote | 1,639 | 35 of 75 | 7 |
| cosine at or above the window median | 1,301 | 50 of 75 | 3 |
| cosine at or above the window p90 | 261 | 34 of 75 | 1 |

8) A cosine floor at the window median costs one key paper of 51 on tabular and removes the
   general canon outright, where the topic tree costs nine and does not.
9) The same floor costs litsearch 29 key papers of 63, and that is the persona whose brief spans
   several problems, which is what the sub-queries exist to split.

## Files

```
personas.toml   the five briefs
truth.py        the future as an answer key: outcomes, later reviews, recall and precision
systems.py      the baselines
topic.py        the topic tree area filter
llm.py          the Gemma client, every completion cached by the hash of its prompt
stages.py       sub-query writing and the reader
pipeline.py     the effort levels
run.py          every persona through every baseline and every level
analyze.py      which signal separates the key from its window
tune_frontier.py  the exponents under each of the three objectives
```
