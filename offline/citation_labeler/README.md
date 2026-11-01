# citation_labeler

Trains the student that labels citation intent, `data/citation_labeler/best.pt`.
It writes no table and runs on its own schedule, and everything else only reads the checkpoint it leaves.

```
stage0_ape_prompt.py     evolves the teacher prompt against the hand-labeled set
stage1_teacher_label.py  labels a sample of real citations with the winning prompt
stage2_train_student.py  distills those labels into a DistilBERT classifier
labels.py                the intent taxonomy, and a parser for either answer shape
plot.py                  the plot theme from research/themes/theme.json
```

`labels.py` and `plot.py` are imported as siblings, never from outside this directory.

## The Artifact Chain

Each stage reads the file the last one wrote, all under `data/citation_labeler/`.

```
ground_truth.csv       hand-labeled, never written by anything here
prompts/prompt_XX.txt  one per generation, 00 is the seed
best.txt               the winning prompt
teacher_labeled.csv    the student's training set
ckpts/iteration_XX.pt  one per epoch
best.pt                the winning student
logs/                  teacher_matrix.png, student_matrix.png, class_distribution.png, student.log
```

The `XX` in `prompts/` counts generations and the `XX` in `ckpts/` counts epochs. They are unrelated, do not make the same stupid mistake as Claude.

## The Six Intents

`uses`, `extends`, `compares`, `motivates`, `background`, `critiques`.
Their order is fixed, since a checkpoint stores class indices and not their labels.

## Running It

```sh
uv run python offline/citation_labeler/stage0_ape_prompt.py
uv run python offline/citation_labeler/stage1_teacher_label.py
uv run python offline/citation_labeler/stage2_train_student.py
uv run python offline/citation_labeler/stage2_train_student.py --benchmark 20000
```

`--benchmark` times the forward pass and prints what the full corpus would cost, which is a cheap way to check a backbone before a run that takes hours.

DistilBERT at 256 tokens runs 1,762 rows/s on one 3090, so the 73.0M resolved citations take 11.5 hours.
ModernBERT-base ran at 871 rows/s, 23.3 hours, and its longer context buys nothing here: the longest citation sentence in a 1,962-row sample was 205 tokens.

## What ground_truth.csv Actually Is

Its 985 rows are hand labeled, carrying the sentence, its section and its intent. That file is the ground truth for this task, and both a prompt and a student are scored on all of it.
