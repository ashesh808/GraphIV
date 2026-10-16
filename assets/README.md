# Assets

This directory contains the code to regenerate figures and visualizations used in the HF cards.

```
run.py                draws every figure into figures/, or only the ones specified
move.py               copies dataset*.png into cards/data, citation-label*.png into cards/citation_labeler and survey-label*.png into cards/survey_labeler
code/
  style.py            the shared look: theme colors, static font cuts, the run-by-run title
  generate_<name>.py  <name>.png, one script per figure, written to the path run.py gives it
  release_counts.py   the counts behind dataset*.png and the intent counts of citation-labeler.png
  labeler_scores.py   the scores behind citation-labeler.png and citation-labeling-pipeline.png
  survey_scores.py    the scores behind survey-labeler.png and survey-labeling-pipeline.png
  external_types.py   what Semantic Scholar and OpenAlex call each held-out paper, for survey-labeler.png
data/
  fonts/              stores the four weights style.py cuts from themes/fonts on its first run
  *.json              stores the numbers each figure draws, derived/cached from the data/logs
figures/              every figure, before move.py copies it
```

To generate (run at root directory):

```sh
direnv exec . uv run python assets/run.py # run all figure generation scripts
direnv exec . uv run python assets/move.py # copies the figures to their supposed location
```

| figure | source for its numbers |
| --- | --- |
| `cards/data/dataset*.png` | `scripts/export/stage1_export_parquet.py` outputs |
| `cards/citation_labeler/citation-labeler.png` | scored on `best.pt` on the test split, rebuilt from `teacher_labeled.csv` on the stage's own seed, and on `ground_truth.csv`, plus `dataset.json`'s intent counts |
| `cards/citation_labeler/citation-labeling-pipeline.png` | the stage0 run's accuracy per generation, `teacher_labeled.csv`, and `logs/student.log` |
| `cards/survey_labeler/survey-labeler.png` | the database's `survey_probability` for the held-out papers of `is_survey.csv`, plus Semantic Scholar's and OpenAlex's types for them |
| `cards/survey_labeler/survey-labeling-pipeline.png` | the same, plus the three-family labeling check of 2026-09-15 |

`cards/` is shortened for `scripts/export/cards/` so the card preview contains the figures.

The accuracy per generation, the teacher's matrix on the ground truth and the three-family counts were only ever printed or drawn, so they are set in their script as constants.
