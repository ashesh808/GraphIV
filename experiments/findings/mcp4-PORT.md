# What to port out of .legacy/graphiv

10,321 lines read on 2026-09-25. One row per module.

## Port

| module | what | why |
| --- | --- | --- |
| `generate/narrate.py` | `ground_report` | every arxiv id in the output is corpus-verified, typos inside edit distance 2 are corrected, fabrications are stripped |
| `generate/story.py` | `connectors` | non-retrieved pool papers on a path between two retrieved ones, 1 or 2 intermediates |
| `retrieve/joint.py` | `rank_landmarks_joint` | measured best in legacy, 341 of 441 against frontier 320 and ppr 277, junk 9% against 14 and 16 |
| `retrieve/recency.py` | `detect_frontier`, `age_norm_score` | the era cutoff read off the pool's own year histogram |
| `retrieve/grade.py` | the -2 rule | a paper graded -2 leaves the answer but stays in the graph as a connector |
| `serve/mcp_server.py` | `refine_question` | candidates plus mode plus at most one clarifying question, grounded in a corpus title probe |
| `retrieve/subgraph.py` | `main_path` | a deterministic longest chronological chain, which the random walk stops reproducing past k=60 |
| `core/models.py` | `Edge`, `Landmark` | the typed contracts, into `src/core/schema.py` |
| `download/fetch.py` | on-demand full text | the reader currently fails on any paper whose html never landed |
| `core/router.py` | the health probe | `/v1/models`, never a chat completion |

## Already have

| module | replaced by |
| --- | --- |
| `retrieve/api.py`, `build.py`, `pools.py` | `src/retrieve/recipe.py` |
| `retrieve/subgraph.py` pool and induce | `src/retrieve/cosine.py`, `expand.py` |
| `retrieve/grade.py` prompt | `scratchpad/frontier-system/roles.py` |
| `retrieve/trajectory.py` | `scratchpad/leyline/magnet.py` |
| `retrieve/subgraph.py` `tensions` | the critique filter |
| `generate/fulltext.py` | `scratchpad/leyline/paper_text.py`, which also reads tables |
| `generate/extract.py`, `schema.py` | `scratchpad/leyline/methods.py` |
| `core/llm.py`, `embed.py`, `labels.py` | `src/core/` |
| `core/config.py`, `cli.py`, `settings.py` | `config.toml` plus argparse |

## Do not port

| module | why |
| --- | --- |
| `retrieve/landmarks.py` | its own docstring says experiment 02-06 measured these and none shipped |
| `retrieve/pagerank.py` | the six-term score is tuned on 300 cases and reaches 0.812 |
| `retrieve/hybrid.py` | reciprocal rank fusion loses at every budget |
| `retrieve/frontier.py` | reserving slots for recent work measured worse than spending every slot on the blend |
| `retrieve/select.py` | the assembler is the recipe now, and its leyline quota contributed nothing once relevance was in the score |
| `retrieve/refined.py`, `topic_anchor.py` | the tree anchor belongs to the eval, not the serving path |
| `generate/loop.py` | the calling agent owns the loop |
| `generate/judge.py` saturation | a model-side stop, which is the thing measured unreliable |
| `generate/pipeline.py` | the single-pass driver is what the tool surface replaces |
| `generate/compose.py`, `long_compose.py`, `latex.py` | the client writes |
| `generate/critique.py` | the read tool covers it |
| `core/store.py`, `plot.py`, `download/_common.py` | infrastructure the new layout already settles |

## Undecided, product calls rather than code calls

| module | the question |
| --- | --- |
| `generate/figures.py`, `pdf_figures.py` | a cropped figure with a vision caption is a capability the new path drops |
| `generate/graph_viz.py` | the deterministic layout, month on x and cosine to the query on y |
| `serve/webui/*` | the dashboard, 1,536 lines, currently unreachable from the new code |
| `serve/mcp_server.py` `similar_reports`, `ask_research` | run reuse, already shipped once |

## Three measured findings recovered from the reading

1) Reserving slots for recent papers measured worse than blending citations-per-year with the
   reader's relevance, so the fix for old work burying new work is the age normalization and not a
   quota.
2) The magnet walk shipped as a quota of 8 slots on top of the ranking and contributed nothing once
   relevance was in the score, so its output is narrative and not ranking.
3) The digest that won the 03-07 pairwise comparison was a node table plus an adjacency list grouped
   by citation intent, against flat alternatives.
