# citation_preprocess

Builds the `citations` table from the rendered HTML of papers that have finished `papers_preprocess`. One row per citation occurrence, so a paper citing the same work twice gets two rows.

```
matcher.py                 the resolver ladder and the index it consults
stage0_create_citation.py  parse the HTML of every finished paper into citation rows
stage1_label_citation.py   run the trained student over every citation with a target
```

## The stage column

```
0  extracted, not labeled
1  labeled by the student currently in data/citation_labeler/best.pt
```

Only citations that resolved to a paper are labeled. An unresolved reference has no cited work to reason about, so it keeps `stage = 0` forever.

## How a citation resolves

`matcher.py` tries seven rungs in order and records which one fired in `resolved_by`.

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

`stage0` waits for papers at stage 4 and takes `--min-stage 2` to start as soon as the HTML is on disk instead. `stage1` needs `best.pt`, which `scripts/citation_labeler/` produces, and `--relabel` resets every resolved row so a new student can redo the whole table.

`matcher.py` is imported by `stage0_create_citation.py` as a sibling module, which keeps every preprocessing step inside `scripts/`.
