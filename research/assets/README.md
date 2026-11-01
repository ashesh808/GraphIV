# Assets

This directory contains the code to regenerate figures and visualizations used in the HF cards and the root README.

```
run.py                draws every figure into figures/, or only the ones specified
move.py               copies dataset*.png into cards/data, benchmarks*.png into cards/benchmarks, citation-label*.png into cards/citation_labeler and survey-label*.png into cards/survey_labeler, leaving the README's figures in figures/
code/
  style.py            the shared look: theme colors, static font cuts, the run-by-run title
  generate_<name>.py  <name>.png, one script per figure, written to the path run.py gives it
  release_counts.py   the counts behind dataset*.png and the intent counts of citation-labeler.png
  labeler_scores.py   the scores behind citation-labeler.png and citation-labeling-pipeline.png
  survey_scores.py    the scores behind survey-labeler.png and survey-labeling-pipeline.png
  external_types.py   what Semantic Scholar and OpenAlex call each held-out paper, for survey-labeler.png
  field_map.py        a 2-d layout of 250k papers and their fields' disciplines, for poster.png
  example_run.py      the temporal knowledge graph run and BoundedField rerun on it, for poster.png, leyline.png and research-pipeline.png
  benchmark_scores.py the retrieval benchmarks' scores, ceilings and ablation, and the recipes' exponents, for poster.png and bounded-field.png
  leyline_scores.py   the Unseen Newcomers of frontier-system-REPORT.md, for leyline.png
  lineage_chart.py    a run's lineages as subway lanes, drawn on poster.png and leyline.png
  benchmark_counts.py the exported benchmarks and one worked case each, for benchmarks*.png
  case_diagram.py     a worked case's references on one timeline, drawn on benchmarks-*.png
  overview.py         the steps, formulas and toy graph that open bounded-field.png and leyline.png
data/
  fonts/              stores the four weights style.py cuts from research/themes/fonts on its first run
  *.json              stores the numbers each figure draws, derived/cached from the data/logs
  field_map.npz       stores the 2-d layout, which takes about 5 minutes on one core to fit
figures/              every figure, before move.py copies it
```

To generate (run at root directory):

```sh
direnv exec . uv run python research/assets/run.py # run all figure generation scripts
direnv exec . uv run python research/assets/move.py # copies the figures to their supposed location
```

| figure | source for its numbers |
| --- | --- |
| `cards/data/dataset*.png` | `offline/export/stage1_export_parquet.py` outputs |
| `cards/benchmarks/benchmarks*.png` | `graphiv-benchmarks-<cutoff>/` under `EXPORT_PATH`, and the store for each worked case's references |
| `cards/citation_labeler/citation-labeler.png` | scored on `best.pt` on the test split, rebuilt from `teacher_labeled.csv` on the stage's own seed, and on `ground_truth.csv`, plus `dataset.json`'s intent counts |
| `cards/citation_labeler/citation-labeling-pipeline.png` | the stage0 run's accuracy per generation, `teacher_labeled.csv`, and `logs/student.log` |
| `cards/survey_labeler/survey-labeler.png` | the database's `survey_probability` for the held-out papers of `is_survey.csv`, plus Semantic Scholar's and OpenAlex's types for them |
| `cards/survey_labeler/survey-labeling-pipeline.png` | the same, plus the three-family labeling check of 2026-09-15 |
| `figures/poster.png` | `topic_tree.embed_umap` of a 250k sample, `dataset.json`, the run directory of 2026-09-28, BoundedField rerun at that run's date, and `research/experiments/retrieve` |
| `figures/bounded-field.png` | `research/experiments/retrieve`, the recipes, each term set to 0 in `frontier-terms-REPORT.md`, and the two-review agreement in `survey-agreement-REPORT.md` |
| `figures/leyline.png` | the recipe's `[miner]` block, the Unseen Newcomers in `frontier-system-REPORT.md` and the run directory of 2026-09-28 |
| `figures/research-pipeline.png` | the run directory of 2026-09-28 and BoundedField rerun at that run's date |

`cards/` is shortened for `offline/export/cards/` so the card preview contains the figures.

The accuracy per generation, the teacher's matrix on the ground truth and the three-family counts were only ever printed or drawn, so they are set in their script as constants.
