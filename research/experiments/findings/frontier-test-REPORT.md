# frontier-test

The same query run with no date cap, to see what the ranker surfaces that the survey could not
have cited. SurveyMatch cannot score this, since a survey published at date D never cites
anything after D.

## Configuration

| item | value |
| --- | --- |
| query | Interactive Generative Video, from survey `2504.21853` |
| survey date | 2025-04-30 |
| date cap | none, corpus runs to 2026 |
| candidates | 12,997, cosine seed 5,000 plus one citation hop each way off the top 200 |
| edges among candidates | 325,235 |
| importance | corpus-wide citations accrued by 2026-09 |

## Top 1000, split at the survey date

| ranker | new papers | survey references found | mean cosine of the new | p50 citations of the new |
| --- | --- | --- | --- | --- |
| graph ranker | 114 | 102 of 136 | 0.437 | 45 |
| cosine only | 429 | 24 of 136 | 0.512 | 1 |
| whole candidate set | 4,443 | | 0.399 | 1 |

## The ten most-cited post-survey papers each ranker surfaces

Graph ranker

| id | date | citations | title |
| --- | --- | --- | --- |
| 2505.09388 | 2025-05-14 | 8692 | Qwen3 Technical Report |
| 2507.06261 | 2025-07-07 | 3099 | Gemini 2.5 |
| 2511.21631 | 2025-11-26 | 2072 | Qwen3-VL Technical Report |
| 2508.10104 | 2025-08-13 | 1035 | DINOv3 |
| 2506.15742 | 2025-06-17 | 774 | FLUX.1 Kontext |
| 2508.02324 | 2025-08-04 | 753 | Qwen-Image Technical Report |
| 2511.16719 | 2025-11-20 | 585 | SAM 3 |
| 2505.14683 | 2025-05-20 | 537 | Emerging Properties in Unified Multimodal Pretraining |
| 2506.09985 | 2025-06-11 | 496 | V-JEPA 2 |
| 2509.17765 | 2025-09-22 | 397 | Qwen3-Omni Technical Report |

Cosine only

| id | date | citations | title |
| --- | --- | --- | --- |
| 2505.13211 | 2025-05-19 | 169 | MAGI-1: Autoregressive Video Generation at Scale |
| 2506.09113 | 2025-06-10 | 144 | Seedance 1.0 |
| 2509.22622 | 2025-09-26 | 138 | LongLive: Real-time Interactive Long Video Generation |
| 2511.18870 | 2025-11-24 | 113 | HunyuanVideo 1.5 Technical Report |
| 2508.13009 | 2025-08-18 | 90 | Matrix-game 2.0 |
| 2507.11539 | 2025-07-15 | 89 | Streaming 4D Visual Geometry Transformer |
| 2506.03141 | 2025-06-03 | 87 | Context as Memory |
| 2507.16869 | 2025-07-22 | 64 | Controllable Video Generation: A Survey |
| 2512.13507 | 2025-12-15 | 56 | Seedance 1.5 pro |
| 2506.17201 | 2025-06-20 | 52 | Hunyuan-GameCraft |

## Hub suppression, graph score divided by (1 + global citations)^alpha

| alpha | new in top 1000 | mean cosine of the new | p50 citations of the new | survey references at 1000 |
| --- | --- | --- | --- | --- |
| 0.00 | 114 | 0.437 | 45 | 102 |
| 0.15 | 123 | 0.435 | 41 | 100 |
| 0.30 | 135 | 0.436 | 38 | 96 |
| 0.50 | 148 | 0.441 | 31 | 96 |
| 0.70 | 167 | 0.439 | 23 | 92 |
| 1.00 | 186 | 0.436 | 19 | 85 |

## Post-survey papers at alpha 0.30, top ten by score

| id | date | citations | cosine | title |
| --- | --- | --- | --- | --- |
| 2505.13211 | 2025-05-19 | 169 | 0.507 | MAGI-1: Autoregressive Video Generation at Scale |
| 2506.08009 | 2025-06-09 | 316 | 0.399 | Self Forcing: Bridging the Train-Test Gap |
| 2509.22622 | 2025-09-26 | 138 | 0.516 | LongLive: Real-time Interactive Long Video Generation |
| 2506.03141 | 2025-06-03 | 87 | 0.513 | Context as Memory |
| 2509.25161 | 2025-09-29 | 120 | 0.446 | Rolling Forcing: Autoregressive Long Video Diffusion |
| 2604.14148 | 2026-04-15 | 92 | 0.472 | Seedance 2.0 |
| 2510.02283 | 2025-10-02 | 101 | 0.449 | Self-Forcing++ |
| 2508.21058 | 2025-08-28 | 50 | 0.406 | Mixture of Contexts for Long Video Generation |
| 2509.20328 | 2025-09-24 | 137 | 0.480 | Video models are zero-shot learners and reasoners |
| 2505.19386 | 2025-05-26 | 38 | 0.504 | Force Prompting |

## Files

```
main.py     retrieval with no date cap, ranking, and the post-survey split
hub.py      the hub suppression sweep
ranked.json candidates, scores, dates, corpus-wide citation counts
```
