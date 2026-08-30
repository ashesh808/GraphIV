# How GraphIV works

Four parts, in order.
Each step gets one plain line for what it does, and one for how we know it was the right call.
The knobs nobody ever measured are listed at the end, so they are not mistaken for results.

---

## 1. Build the store

Moved out of this page.
`docs/preprocess.md` is the runbook: what to supply, what to run in what order, what each stage
costs and how to check it landed. The short version is that a metadata dump becomes three tables,
`papers`, `citations` and `topics`, and nothing downstream ever writes to them.

The decisions behind it, with the numbers that settled each one, are in `docs/decisions.md` and
the experiments under `experiments/01-preprocessing/`.

## 2. Retrieve: turn a question into the papers that matter

**embed the question** the same way the abstracts were embedded, so they live in one space.
We feed it the raw question, because dressing it up as a fake abstract first helps the other
embedding space and does nothing for this one
(removed with the 03 rebuild).

**hybrid pool** runs two searches, one by meaning and one by title keywords, and merges the two
rankings into a few hundred candidates.
This is where the worst bug lived: the database was quietly returning 40 papers no matter what we
asked for, and fixing it took our hit rate on known-important papers from 86% to 100%
(`experiments/02-retrieval/02-07-retrieval-breadth`).

**frontier detection** looks at what years the candidates come from and decides where "recent"
starts for this particular topic.
A fixed cutoff cannot work, because how fast a field moves is exactly what varies between fields
(removed with the 03 rebuild).

**refined pool** works out which topic the question belongs to, throws out candidates from other
topics, then follows citations inside that topic to find more.
This one is genuinely unsettled: the ablation says keep it, but one survey test recalled more with
it off, so the bigger battery has to decide
(the removed 03 suite against section 04-03 of
`docs/audits/EXPERIMENTS_AUDIT.md`).

**frontier pull** separately searches for the newest papers and adds them, ignoring the topic tree.
It has to exist because the tree was built before the newest papers arrived, so without this step
no 2026 paper ever appears in any report (removed with the 03 rebuild).

**ancestors** adds the older papers that many of our candidates cite, which is how foundational
work gets in even when it never uses today's vocabulary.
The test case is BYOL in a review about JEPA: it is invisible to a text search and reachable only
through citations, and our old cutoff was rejecting it by one hundredth of a point
(`experiments/02-retrieval/02-03-ancestor-gate` and `02-07-retrieval-breadth`).

**induce subgraph** keeps every citation arrow whose two ends are both papers we kept, which is
what turns a list into a graph.
Turn it off and the report still looks fine by the surface numbers while the chronology falls
apart, which is why we never read one number alone.
It does not, however, make the writing more trustworthy: reports written without the adjacency
digest have their citations hold up slightly better, not worse
(`experiments/03-generation/03-03-graph-digest`).

**reader grade** has a model read each candidate's abstract and say what role it plays and how
relevant it is, from -2 to +2.
Ranking on relevance times similarity costs nothing in recall and removes every off-topic paper
from the final set (`experiments/02-retrieval/02-05-reader-fusion`).

**rank landmarks** picks the 30 to 200 papers the review is built from, and how it picks depends
on what the question wants.
A **survey** question wants the lineage a field is built on, so papers are scored by
citations-per-year fused with the reader's relevance and no slots are held back.
A **frontier** question wants what is happening now, so papers are scored by PageRank seeded on
the question and slots are reserved for recent work.
The mode is decided when the question is refined, not defaulted
(`experiments/02-retrieval/02-05-selection-objective`).

**LeyLine quota** walks the citation graph forward in time from the best-rated papers and gives 8
of the slots to whatever the walks keep landing on.
It runs in both modes, so it is unconditional rather than a mode of its own, and it beat plain
PageRank on survey reference lists neither method had seen
(`experiments/02-retrieval/02-06-leyline`).

**story** sorts the chosen papers into eras, finds the longest chain of one paper building on
another, and collects the places where papers disagree.
The disagreements come from the citation labels, which is what phase 2 was for.

## 3. Generate: write the review

**schema** asks the model what fields are worth knowing about every paper, given this specific
question, instead of using one fixed template.

**extract** fills in those fields for each chosen paper, from its full text.
Feeding the writer this extracted content, rather than just titles and abstracts, is the single
biggest quality lever we measured (removed with the 03 rebuild).

**digest** is the text the writing model actually sees: the papers, their extracted fields, and
the citation arrows between them written as a list.
We tried six ways of writing a graph into a prompt and this one won on every axis while using the
fewest tokens (same experiment).

**compose** writes the review.
It is explicitly forbidden from spending a section on famous-but-generic papers, which took
Attention, BERT, GPT-3 and Adam down to zero mentions in a niche review without losing any of the
niche coverage (removed with the 03 rebuild).

**the deep loop**, at higher effort, writes a draft, has a judge read it, asks it what is missing,
goes back and retrieves those things, and repeats.
Six rounds beat one round with no losses on any axis, roughly doubling the papers covered and
taking recall from 0.81 to 0.96 (removed with the 03 rebuild).
The judge itself was tested first, on reports we deliberately damaged, and it caught every kind of
damage without being fooled by length or ordering (removed with the 03 rebuild).
Inside the loop it also reads a few full PDFs per round, four and no more, because reading eight
gave back everything four gained (removed with the 03 rebuild).

**ground** checks every arXiv id in the finished text against the database, repairs typos, and
deletes anything invented.
It is a plain lookup rather than a model checking itself, and it has verified every citation in
every run we have inspected (`experiments/deep-research/results/h2h`).

**render** writes the report out as markdown, LaTeX, a bibliography and a graph picture.

## 4. Serve: hand it to a person

The MCP server exposes the whole thing as tools an assistant can call, and the same process serves
the dashboard where reports are read.
A public copy runs with everything that writes or spends GPU time switched off.

---

## Does the whole thing work

Three questions, three answers.

**Does it find the right papers?** Against survey reference lists: hide a survey, freeze the
corpus to the month it came out, ask the same question, count how many of its references come
back. Sixty surveys, in `experiments/02-retrieval`. What decides the outcome is which papers
enter the pool, not how they are ranked afterward.

**Is what it writes true?** Seven in ten of the sentences that cite a paper are supported by that
paper, agreed on by two judge families that match on 90.6% of individual sentences. The checker
behind that number was first shown able to reject: it approves 15-20% of citations we broke on
purpose against 71-74% of real ones. Sixty percent of all sentences carry a citation at all.
That is `experiments/03-generation`.

**Is it better than what came before?** Against a 2023-era baseline it wins on every axis, 8
topics to 0, under three judges from two unrelated model families
(`experiments/deep-research/results/multi_judge.md`). The comparison against a hosted commercial
tool has not been run.

## Knobs nobody measured

Not every number in the code came from an experiment.
These did not, and should not be quoted as if they did.

| knob | where |
| --- | --- |
| how many candidates each effort level pulls | `pipeline.TIERS` |
| the survey landmark budgets of 50/100/150/200 | `pipeline.SURVEY_M` |
| the 1.3x relative ceiling the loop may grow a budget to | `generate/loop.py` |
| how many title matches to fuse in | `retrieve/hybrid.py` |
| the constant 60 in the rank fusion, taken from the paper that introduced it | `retrieve/hybrid.py` |
| how many top papers vote on the topic | `retrieve/topic_anchor.py` |
| the cap of 120 ancestors and the minimum of 3 citers | `pipeline.retrieve_rank` |
| how wide the newest-paper search probes | `retrieve/refined.py` |
| PageRank's damping and iteration count | `retrieve/pagerank.py` |
| the walk's decay and how many walks | `retrieve/trajectory.py` |
| how much of each section the extractor is shown | `generate/fulltext.py` |
| the judge's input and output limits, set by a crash rather than a sweep | `generate/judge.py` |
| how many figures to pull | `pipeline.pick_figure_items` |

Two experiments are out of date rather than missing.
The two corpus censuses counted 3.07M papers and we now hold 3.10M, and the headline retrieval
number of 0.742 was measured while that 40-paper database bug was still active, so the real figure
is higher.
