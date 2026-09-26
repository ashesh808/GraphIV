# citation_preprocess

Builds the `citations` table from the rendered HTML of papers that have finished `papers_preprocess`. One row per citation occurrence, so a paper citing the same work twice gets two rows.

```
citation_regex.py          the resolver ladder and the index it consults
stage0_create_citation.py  parse the HTML of every finished paper into citation rows
stage1_label_citation.py   run the trained student over every citation with a target
stage2_export_graph.py     export the resolved graph as flat arrays for query-time reading
```

## The stage column

```
0  extracted, not labeled
1  labeled by the student currently in data/citation_labeler/best.pt
```

Only citations that resolved to a paper are labeled. An unresolved reference has no cited work to reason about, so it keeps `stage = 0` forever.

`stage0` queues on `papers.is_citation_parsable IS NULL` rather than on the absence of citation rows. About a fifth of the corpus renders html with no bibliography, and keying on the rows meant those papers were parsed again on every run. After a paper is parsed the column records whether anything was found, so it is asked exactly once.

## How a citation resolves

`citation_regex.py` tries seven rungs in order and records which one fired in `resolved_by`.

```
link              an arXiv id in the bib entry's hyperlink
text              an arXiv id in the raw bib text
doi               DOI lookup
jref              journal-ref key with exactly one hit
title-exact       normalized title hit, year agrees
title-exact-noyr  same, year disagrees
title-fuzzy       blocking key then token_set_ratio
```

Three more values record a fuzzy hit that was rejected, by token overlap, by year or by author overlap, and `none` covers everything that never matched. A rejected row keeps its `resolved_by` and gets no `target_id`, which is provenance rather than corruption.

## Running it

```sh
uv run python scripts/citation_preprocess/stage0_create_citation.py
uv run python scripts/citation_preprocess/stage1_label_citation.py
uv run python scripts/citation_preprocess/stage1_label_citation.py --relabel
```

`stage0` waits for papers at stage 3 and takes `--min-stage 2` to start as soon as the HTML is on disk instead. `stage1` needs `best.pt`, which `scripts/citation_labeler/` produces, and `--relabel` resets every resolved row so a new student can redo the whole table.

`citation_regex.py` is imported by `stage0_create_citation.py` as a sibling module, which keeps every preprocessing step inside `scripts/`.

## The graph export

`stage2_export_graph.py` is an export rather than a queue stage, so it reads no `stage` column and rewrites `[dataset] GRAPH_PATH` whole on every run. It writes one uncompressed npz of flat arrays, 400MB over 3,164,437 papers and 38,159,685 distinct edges.

```
ids        |S16     one arxiv id per row, sorted, and the key every other array shares
day        int32    publication date as days since the epoch, which caps a query with no join
stage      int8     the papers stage column
survey     float32  survey_probability, which selects a review set
level       int8    the three topic_tree columns
cites_ptr  int32    row offsets into cites_idx
cites_idx  int32    who cites paper i, at cites_idx[cites_ptr[i]:cites_ptr[i+1]]
refs_ptr   int32    row offsets into refs_idx
refs_idx   int32    what paper i cites, in the same shape
```

73.8M resolved occurrences collapse to 38.2M distinct edges, since a paper citing the same target in three sentences is one edge. In-degree is `diff(cites_ptr)` and needs no scan. The archive opens in 11ms and both citation arrays read in 0.05s, against roughly nineteen seconds for the same counts out of Postgres.

Run it after `stage1_label_citation.py`, and again whenever the citations table changes.
