# citation_preprocess

Builds the `citations` table from the html of every paper that finished `papers_preprocess`.
There is one row per citation, so a paper citing the same work twice gets two rows.

```
citation_regex.py          resolves a citation to an arXiv id, cheapest method first
stage0_create_citation.py  parses each finished paper's html into citation rows
stage1_label_citation.py   labels every resolved citation with the trained student
stage2_export_graph.py     exports the resolved graph as flat arrays the server reads
```

## The Stage Column

```
0  extracted, not labeled
1  labeled by the student in data/citation_labeler/best.pt
```

Only citations that resolved to a paper get labeled.
An unresolved one has no cited work to reason about, so it stays at 0.

`stage0` queues on `papers.is_citation_parsable IS NULL`, not on a paper having no citation rows.
About a fifth of the corpus has html with no bibliography, and keying on the rows parsed those papers again on every run.

## How a Citation Resolves

We try seven methods in order and record the one that hit in `resolved_by`.

```
link              an arXiv id in the bib entry's hyperlink
text              an arXiv id in the raw bib text
doi               DOI lookup
jref              journal-ref key with exactly one hit
title-exact       normalized title hit, year agrees
title-exact-noyr  same, year disagrees
title-fuzzy       blocking key then token_set_ratio
```

Three more values record a fuzzy hit we rejected, on token overlap, on year or on authors, and `none` covers everything that never matched.
A rejected row keeps its `resolved_by` and gets no `target_id`, which is a record of what happened rather than corruption.

## Running It

```sh
uv run python scripts/citation_preprocess/stage0_create_citation.py
uv run python scripts/citation_preprocess/stage1_label_citation.py
uv run python scripts/citation_preprocess/stage1_label_citation.py --relabel
uv run python scripts/citation_preprocess/stage2_export_graph.py
```

`stage0` waits for papers at stage 3, or takes `--min-stage 2` to start as soon as the html is on disk.
`stage1` needs `best.pt` from `scripts/citation_labeler/`, and `--relabel` resets every resolved row so a new student can redo the whole table.
`citation_regex.py` is imported as a sibling module, which keeps all the preprocessing inside `scripts/`.

## The Graph Export

Stage 2 is an export rather than a queue stage.
It reads no `stage` column and rewrites `[dataset] GRAPH_PATH` whole on every run, as one uncompressed archive of flat arrays, about 400 MB.

```
ids        |S16     one arxiv id per row, sorted, the key every other array shares
day        int32    publication date as days since the epoch, so a date cap needs no join
stage      int8     the papers stage column
survey     float32  survey_probability, which selects a review set
level      int8     the three topic_tree columns
cites_ptr  int32    row offsets into cites_idx
cites_idx  int32    who cites paper i, at cites_idx[cites_ptr[i]:cites_ptr[i+1]]
refs_ptr   int32    row offsets into refs_idx
refs_idx   int32    what paper i cites, in the same shape
```

73.8M resolved citations collapse to 38.2M distinct edges, since a paper citing the same target in three sentences is one edge.
In-degree is `diff(cites_ptr)` and needs no scan.
The archive opens in 11 ms and both citation arrays read in 0.05 s, against about nineteen seconds for the same counts out of Postgres.

Run it after `stage1_label_citation.py`, and again whenever the citations table changes.
