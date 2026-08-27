# 02-02-pool-construction

**What:** before anything gets ranked, is the right paper even in the pool.
Four levers, one moved at a time, 60 surveys, 1617 gold papers.
No reader and no LLM: this measures the pool only, which makes it the ceiling for everything after
it.

**Conclusion:** two findings.
Half the answer key never reaches the pool and no setting recovers it.
And of the four levers, only the citation-graph one changes the answer at all.

Run: `uv run python run.py` (reads `cache/pool_recall.json`, a few seconds).

## The ceiling

| | papers |
| --- | --- |
| gold papers across 60 surveys | 1617 |
| reach the pool | 860 |
| never arrive | 757 |
| share reached | 53% |

Every selection experiment after this one is competing over the 53 percent that got in.
When 02-05 reports 341 gold found, the honest denominator is the in-pool half, not the answer key.

## The sweep

| lever | stage | gold in pool | vs shipped | avg pool |
| --- | --- | --- | --- | --- |
| n_pool 200 | vector | 868 | +8 | 313 |
| ancestor floor 0.25 | graph | 866 | +6 | 336 |
| lexical off | lexical | 863 | +3 | 333 |
| **shipped** | | **860** | | 333 |
| n_pool 600 | vector | 857 | -3 | 346 |
| n_pool 800 | vector | 855 | -5 | 361 |
| ancestor floor 0.35 | graph | 852 | -8 | 326 |
| lexical OR (bug fixed) | lexical | 849 | -11 | 335 |
| ef_search 40 (old default) | vector | 848 | -12 | 250 |
| ancestor floor 0.40 | graph | 823 | -37 | 313 |
| ancestor floor 0.45 | graph | 770 | -90 | 292 |

## Only one stage matters

| stage | levers | best | worst | spread |
| --- | --- | --- | --- | --- |
| vector channel | 4 | +8 | -12 | 20 |
| lexical channel | 2 | +3 | -11 | 14 |
| citation graph | 4 | +6 | -90 | **96** |

Every knob on the text side moves fewer than 20 papers out of 1617, which is noise.
The graph knob moves 96.
The front end is robust to how you search the text and sensitive only to how much graph you let in.

Three of the four levers are inert, and each for its own reason.

**The vector channel repairs itself.**
`ef_search` was silently capped at 40 for months, which truncated every vector KNN.
It costs 12 papers.
The pool shrinks from 333 to 250, then the topic drill and ancestor augmentation refill it out of
the citation graph, and the loss never reaches the output.
A broken vector channel was survivable because the graph covered for it.

**Pool width does nothing.**
200 candidates beats 800.
`refined_pool` drills to a fixed target of 280 whatever it is handed, so the vector channel's width
is normalised away one stage later.

**The lexical channel is dead and repairing it makes things worse.**
`plainto_tsquery` ANDs every term, so no title matches a twenty-word question and the channel
returns zero rows for all 60 surveys.
Turning it off scores +3, confirming it contributes nothing.
Replacing it with an OR query scores -11, and splits the wrong way across dev and test, so the fix
is a wash at best.
The bug is real and it costs nothing.

**The graph floor is the only live knob, and it is already correct.**
0.25, 0.30 and 0.35 land within 14 papers of each other.
0.40 costs 37 and 0.45 costs 90.
Shipped is 0.30, on the plateau, with the cliff one step away.
This reproduces the old 3-topic plateau finding on 60 external surveys.

Note: `02-03-ancestor-gate/README.md` still says 0.35 is shipped.
The shipped value is 0.30, hardcoded in `retrieve_rank`.

## What was not tested

The two knobs that set how much graph gets in were held fixed: the drill target (280) and the
ancestor cap (120).
Since graph admission is the only stage that moved the answer, those are the two most likely places
to find the missing 757 papers, and neither has been swept.

That is the named next experiment, not a caveat.

## For the arc

The pool is at its tuned optimum and the remaining loss is structural rather than a tuning failure.
So the interesting question is no longer how to build a better pool with these knobs.
It is what to do with the one you have, which is 02-03 onward.
