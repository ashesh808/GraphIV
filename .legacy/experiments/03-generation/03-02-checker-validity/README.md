# 03-02-checker-validity

**What:** whether the checker behind 03-01 can return a negative. One citation per citing
sentence is replaced with the most similar paper the same report cites, so the wrong paper is
on the same topic. Both judges then score the broken citations exactly as they scored the real
ones.

**Conclusion:** **the checker rejects what it should.** Over 818 broken citations it approves
0.153 under Gemma and 0.198 under Qwen, against 0.714 and 0.744 for the real ones the same
judges saw. The gap of roughly 0.55 is reproduced by both model families.

Full write-up: `results/metrics.md`. Run: `uv run python run.py`.

## Why this has to exist

03-01 reports that seven in ten cited sentences are supported. Without this, that number
cannot be told apart from a checker that agrees with whatever it is shown. The catch rate here
is what licenses reading 03-01 at all.

## Why the swap is the nearest paper

An earlier version swapped in a random paper the report cited. Counting shared words alone
reached 0.823 balanced accuracy against the judge's 0.838 on that version, which showed the
test was measuring vocabulary drift rather than attribution. Swapping to the nearest cited
paper drops every cheap baseline by 8 to 12 points and is the version reported here.
