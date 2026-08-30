# citation_labeler

Produces `data/citation_labeler/best.pt`, the student that labels citation intent. Nothing here writes to a table, and it runs on its own schedule: everything else only ever reads the checkpoint it leaves behind.

```
stage0_ape_prompt.py     evolve the teacher prompt against the hand-labeled set
stage1_teacher_label.py  apply the winning prompt to a sample of real citations
stage2_train_student.py  distill those labels into a DistilBERT classifier
labels.py                the intent taxonomy and a parser for either answer shape
plot.py                  the theme.json plot theme the three figures are drawn in
```

`labels.py` and `plot.py` are imported as siblings, never from outside this directory.

## The artifact chain

Each stage reads the previous file and writes the next, all under `data/citation_labeler/`.

```
ground_truth.csv     hand-labeled, never written by anything here
prompts/prompt_XX.txt  one per generation, 00 is the seed
best.txt             the winning prompt
teacher_labeled.csv  the student's training set
ckpts/iteration_XX.pt  one per epoch
best.pt              the winning student
logs/                teacher_matrix.png, student_matrix.png, class_distribution.png, student.log
```

The `XX` in `prompts/` counts generations and the `XX` in `ckpts/` counts epochs. They are unrelated, do not make the same stupid mistake as Claude.

## The six intents

`uses`, `extends`, `compares`, `motivates`, `background`, `critiques`.
Their order is fixed, since a checkpoint stores class indices and not names.

## Running it

```sh
uv run python scripts/citation_labeler/stage0_ape_prompt.py
uv run python scripts/citation_labeler/stage1_teacher_label.py
uv run python scripts/citation_labeler/stage2_train_student.py
uv run python scripts/citation_labeler/stage2_train_student.py --benchmark 20000
```

`--benchmark` times the forward pass and prints what the full corpus would cost, which is the cheap
way to check a backbone before starting a run measured in hours.

DistilBERT at 256 tokens runs 1,762 rows/s on one 3090, so the 73.0M resolved citations take 11.5
hours. ModernBERT-base was measured at 871 rows/s for 23.3 hours, and its longer context buys
nothing here: the longest citation sentence in a 1,962-row sample was 205 tokens.

## What ground_truth.csv actually is

Of its 1,002 rows only 58 carry `labeler = human`. The other 944 are `labeler = accepted`, meaning the previous student's own prediction was taken when no hand label existed. A prompt scored against the whole file is therefore measured mostly on agreement with the old model, so `report()` prints the accuracy on the 58 human rows separately.
