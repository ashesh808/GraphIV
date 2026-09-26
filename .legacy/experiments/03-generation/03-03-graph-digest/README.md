# 03-03-graph-digest

**What:** whether putting the citation graph in the writer's prompt changes how well the report
is sourced. The same five questions run twice, once normally and once with `--include-no-graph`,
which keeps the pool and the landmark budget identical and withholds only the adjacency digest.
Verified on the runs: pool 569 either way, budget 260 either way, edges 10227 against 0.

**Conclusion:** **the graph does not make a report more reliable, and may slightly hurt.**
Support is 0.707 with the digest and 0.754 without, and the no-graph side led in 8 of 10
matched pairs (mean +0.037). Coverage is 0.605 against 0.586, and the checker catches
broken citations at the same rate either way, 0.703 against 0.704.

The likely mechanism is that the adjacency list states relationships the papers' own text does
not. A digest saying paper A cites paper B invites a sentence like "A builds on B", which is
true of the graph and unsupported by either document, so the checker rejects it. That is a
hypothesis this experiment does not test.

This is a finding about reliability only. The graph's value was established in `02-retrieval`,
where it decides which papers reach the pool at all, and nothing here contradicts that.

Full write-up: `results/metrics.md`. Run: `uv run python run.py`.

## What is compared

Both numbers from 03-01 and 03-02, plus the coverage count from 03-04, so a change in one can
be read against the others. A digest that raises the support rate while lowering coverage is
trading citations for confidence, and the table has to show both for that to be visible.
