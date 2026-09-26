# 07 — the student classifier

**What:** student-v4, the DistilBERT distilled from the APE-refined teacher, scored three ways:
against its own teacher's held-out split, against the 1,002-occurrence gold set, and against the
71,564,387 edges it labeled into `citation_intent_v2`. Compared throughout to student-v1, which
wrote the `citation.intent` the graph currently runs on.

**Conclusion:** macro-F1 **0.723 → 0.771** against student-v3 on the teacher-held-out split, with
`critiques` **0.583 → 0.708** and `motivates` **0.703 → 0.820**, the two classes that carry the
tensions list. Accuracy falls **0.844 → 0.826**, which is the same trade v3 already took: accuracy
is dominated by `background` at three quarters of the data. Every class improves except
`background`, which gives up two points.

**The comparison does not survive contact with the gold set.** 944 of its 1,002 rows were
pre-filled by student-v1 and waved through, and all 944 still carry exactly what student-v1 wrote.
Student-v1 therefore scores 0.995 on it by construction, and student-v4's 0.852 measures agreement
with student-v1, not accuracy. The 58 hand-typed rows are the only independent signal: **v4 0.862,
v1 0.914**, a gap of 3 items at n=58. Nothing here ranks the two students, and the per-student
held-out splits do not either, since each student is graded by its own teacher's labels.

**What is unambiguous** is what the relabel changed. The two students agree on **85.8%** of the
67,357,119 shared edges, and v4 labels 4,207,268 edges v1 never saw, because the 30..1000 character
sentence filter is gone. `background` falls 78% → 69% of the corpus and every relational class
grows.

**The base-rate trap.** The gold set is class-balanced at 167 per class, so precision measured on
it does not transfer to a corpus that is two thirds `background`. Inverting the observed marginal
through P(pred | gold) (condition 1.4, no clipping) puts the true `background` share at 83% and
drops `motivates` to a corrected 0.23%. The corrected precisions carry wide bootstrap intervals
because the rare-class leaks rest on single-digit counts, and they inherit the anchoring above, so
they bound departure from student-v1 rather than error.

**Not promoted.** `citation.intent` still holds student-v1. `citation_intent_v2` is a side table.

Numbers: [`results/metrics.md`](results/metrics.md) · figures in [`results/`](results/).
Run: `uv run python run.py` (`--no-cache` to re-hit the store).
Rebuild the labels with `uv run python scripts/citations.py --set-stage bert --set-step relabel`.
