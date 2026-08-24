# 06 — prompt refinement

**What:** the APE loop that writes the teacher's labeling policy — label, judge the mistakes,
redraft, repeat. Eight generations against the 1,002-occurrence gold set, split 601 dev / 401
held-out per class. The judge only ever reads dev mistakes, so held-out scores a policy it never
shaped. Reads the frozen `refine/` artifacts; no LLM.

**Conclusion:** held-out accuracy **0.536 → 0.751** (+21.5 points) at generation 5, every class
improved, and `critiques` went **0.32 → 0.806**. The loop **cut before it grew**: generation 1
collapsed 107 lines to 66 and generation 2 dropped five worked examples, and that shrinking phase
bought most of the gain. Growth past the winner bought nothing — generations 6 and 7 added three
examples for 7,231 chars and lost a point. The six decision rules survived every rewrite untouched;
what changed was boundary wording and which examples earn their place.

**The shape that matters:** the relational classes came out high-precision, moderate-recall
(`critiques` P **0.96** / R 0.70, `motivates` P **0.96** / R 0.78), and every miss falls into
`background`, whose precision is therefore only 0.50. On a corpus that is 78% `background` this is
the safe direction: relational edges are under-produced but clean, which is what the tensions and
adjacency machinery needs.

**What the target is.** 944 of the 1,002 gold occurrences were pre-filled by student-v1 and
accepted without a hand edit, so the loop was optimizing toward a student-v1-anchored target rather
than toward independent human annotation. The loop mechanics still hold, since dev and held-out are
disjoint and the judge never reads held-out, but read the 0.751 as agreement with that target. See
[`../01-07-student-classifier`](../01-07-student-classifier) for the provenance split.

**Read the curve carefully:** generation 7 is not an eighth measurement. The drafter returned an
empty response and its failure path returns the seed unchanged, so generation 7 ran generation 6's
file verbatim. `code/refinement.py` detects this by digest and prints it as `(repeat)`.

Numbers: [`results/metrics.md`](results/metrics.md) · figures in [`results/`](results/).
Run: `uv run python run.py`. Re-run the loop itself with
`uv run python scripts/citations.py --set-stage label --set-step refine`.
