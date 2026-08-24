# How GraphIV works

Five phases, in order.
Each step gets one plain line for what it does, and one for how we know it was the right call.
The knobs nobody ever measured are listed at the end, so they are not mistaken for results.

---

## 1. Download: get the papers

**seed** grabs arXiv's list of every paper it has ever published, with the title, authors,
abstract and date, about 3.1 million rows.
Nothing to prove here, it is plumbing.

**download_pdf** fetches the actual PDF of each paper from Google's mirror.
We keep all 5.6 TB locally instead of fetching on demand, because the whole store fits on the
production box with room to spare (`docs/release-plan.md`).

**download_html** fetches arXiv's HTML version of each paper, which is what everything downstream
actually reads.
HTML wins because the bibliography is already marked up as a list, while pulling references back
out of a PDF needs a tool that mangles them (`docs/release-plan.md`).

## 2. Preprocess: turn the papers into a graph

**parse** reads each paper's reference list and works out which arXiv paper each entry points to.
It tries six things in order, from an explicit link down to a fuzzy title match, and stops at the
first that works.
About 40% of 177 million references resolve, and the risky fuzzy match accounts for only 11% of
those, so the ladder buys reach without leaning on guesswork
(`experiments/01-preprocessing/01-01-resolver-quality`).

**label** asks a big model, for a sample of citations, why one paper cited another.
Six reasons, with the prompt written by a loop that labels, judges its own mistakes and redrafts,
which moved held-out agreement from 0.54 to 0.75 over eight generations
(`experiments/01-preprocessing/01-06-prompt-refinement`).

**bert** trains a small model on that sample and lets it label every resolved citation, because
running the big model that many times is not affordable.
The shipped student gets the reason right 89% of the time and is weakest on exactly the interesting
case, one paper criticizing another (`experiments/01-preprocessing/01-02-labeling-quality`).
A newer student trained on the refined prompt is stronger there, F1 0.56 to 0.71, and has labeled
all 71.6 million edges into a side table, but it is not promoted: no sample exists that ranks the
two without circularity (`experiments/01-preprocessing/01-07-student-classifier`).

**consolidate** puts the metadata, the citations and the vectors into a single Postgres database.
The resulting graph behaves like a real citation network, and sorting papers by how often they are
cited returns ResNet, BERT and Transformer at the top, which is the sanity check
(`experiments/01-preprocessing/01-03-graph-structure`).

**embed** turns every abstract into a vector, so papers can be found by meaning rather than by
keyword.
We store two versions and use the asymmetric one, because it matches the best recall we measured
and needs no extra trick at query time (`experiments/03-generation/03-03-embedding-format`).

**topics** sorts the whole corpus into a tree of about 3,600 topics, by repeatedly splitting
whichever clump is still too broad.
The alternative methods throw away papers they cannot place, up to 59% of them, and this one
places every single paper (`experiments/01-preprocessing/01-04-clustering-comparison` and
`01-05-topic-tree`).

## 3. Retrieve: turn a question into the papers that matter

**embed the question** the same way the abstracts were embedded, so they live in one space.
We feed it the raw question, because dressing it up as a fake abstract first helps the other
embedding space and does nothing for this one
(`experiments/03-generation/03-03-embedding-format`).

**hybrid pool** runs two searches, one by meaning and one by title keywords, and merges the two
rankings into a few hundred candidates.
This is where the worst bug lived: the database was quietly returning 40 papers no matter what we
asked for, and fixing it took our hit rate on known-important papers from 86% to 100%
(`experiments/02-retrieval/02-07-retrieval-breadth`).

**frontier detection** looks at what years the candidates come from and decides where "recent"
starts for this particular topic.
A fixed cutoff cannot work, because how fast a field moves is exactly what varies between fields
(`experiments/03-generation/03-04-recency-knob`).

**refined pool** works out which topic the question belongs to, throws out candidates from other
topics, then follows citations inside that topic to find more.
This one is genuinely unsettled: the ablation says keep it, but one survey test recalled more with
it off, so the bigger battery has to decide
(`experiments/03-generation/03-02-component-ablation` against section 04-03 of
`scratchpad/audits/EXPERIMENTS_AUDIT.md`).

**frontier pull** separately searches for the newest papers and adds them, ignoring the topic tree.
It has to exist because the tree was built before the newest papers arrived, so without this step
no 2026 paper ever appears in any report (`experiments/03-generation/03-05-frontier-pull`).

**ancestors** adds the older papers that many of our candidates cite, which is how foundational
work gets in even when it never uses today's vocabulary.
The test case is BYOL in a review about JEPA: it is invisible to a text search and reachable only
through citations, and our old cutoff was rejecting it by one hundredth of a point
(`experiments/02-retrieval/02-03-ancestor-gate` and `02-07-retrieval-breadth`).

**induce subgraph** keeps every citation arrow whose two ends are both papers we kept, which is
what turns a list into a graph.
Turn it off and the report still looks fine by the surface numbers while the chronology falls
apart, which is why we never read one number alone
(`experiments/03-generation/03-02-component-ablation`).

**reader grade** has a model read each candidate's abstract and say what role it plays and how
relevant it is, from -2 to +2.
Ranking on relevance times similarity costs nothing in recall and removes every off-topic paper
from the final set (`experiments/02-retrieval/02-05-reader-fusion`).

**rank landmarks** picks the 30 to 120 papers the review will actually be built from, using
PageRank seeded on the question, with slots held back for recent work.
We put PageRank on trial against four coverage-maximizing alternatives and it beat all of them by
roughly double on finding a field's canonical papers
(`experiments/02-retrieval/02-06-selection-objective`).

**trajectory quota** walks the citation graph outward from the best-rated papers and gives 8 of
the slots to whatever the walks keep landing on.
It is a small addition on top of PageRank rather than a replacement, and it beat plain PageRank on
survey reference lists that neither method had ever seen
(`scratchpad/trajectory-sampler/results.md` and section 04-04 of the audit).

**story** sorts the chosen papers into eras, finds the longest chain of one paper building on
another, and collects the places where papers disagree.
The disagreements come from the citation labels, which is what phase 2 was for.

## 4. Generate: write the review

**schema** asks the model what fields are worth knowing about every paper, given this specific
question, instead of using one fixed template.

**extract** fills in those fields for each chosen paper, from its full text.
Feeding the writer this extracted content, rather than just titles and abstracts, is the single
biggest quality lever we measured (`experiments/03-generation/03-07-graph-representation`).

**digest** is the text the writing model actually sees: the papers, their extracted fields, and
the citation arrows between them written as a list.
We tried six ways of writing a graph into a prompt and this one won on every axis while using the
fewest tokens (same experiment).

**compose** writes the review.
It is explicitly forbidden from spending a section on famous-but-generic papers, which took
Attention, BERT, GPT-3 and Adam down to zero mentions in a niche review without losing any of the
niche coverage (`experiments/03-generation/03-11-hub-suppression`).

**the deep loop**, at higher effort, writes a draft, has a judge read it, asks it what is missing,
goes back and retrieves those things, and repeats.
Six rounds beat one round with no losses on any axis, roughly doubling the papers covered and
taking recall from 0.81 to 0.96 (`experiments/03-generation/03-08-judge-loop`).
The judge itself was tested first, on reports we deliberately damaged, and it caught every kind of
damage without being fooled by length or ordering (`experiments/03-generation/03-01-judge-validity`).
Inside the loop it also reads a few full PDFs per round, four and no more, because reading eight
gave back everything four gained (`experiments/03-generation/03-09-critique-depth`).

**ground** checks every arXiv id in the finished text against the database, repairs typos, and
deletes anything invented.
It is a plain lookup rather than a model checking itself, and it has verified every citation in
every run we have inspected (`experiments/deep-research/results/h2h`).

**render** writes the report out as markdown, LaTeX, a bibliography and a graph picture.

## 5. Serve: hand it to a person

The MCP server exposes the whole thing as tools an assistant can call, and the same process serves
the dashboard where reports are read.
A public copy runs with everything that writes or spends GPU time switched off.

---

## Does the whole thing work

Against a 2023-era baseline, the current pipeline wins on every axis, 8 topics to 0, under three
different judges from two unrelated model families (`experiments/deep-research/results/multi_judge.md`).

The harder test is survey reference lists: take a survey paper, hide it, freeze the corpus to the
month it came out, ask the same question, and see how many of its references come back.
That is section 04 of `scratchpad/audits/EXPERIMENTS_AUDIT.md`, and the full 20-survey run is the
next thing to build.

## Knobs nobody measured

Not every number in the code came from an experiment.
These did not, and should not be quoted as if they did.

| knob | where |
| --- | --- |
| how many candidates each effort level pulls | `pipeline.TIERS` |
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
