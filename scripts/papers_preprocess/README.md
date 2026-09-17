# papers_preprocess

Builds the `papers` table from a metadata dump, one stage at a time. Every stage reads its own queue off the `stage` column, does one thing, and advances the rows that succeeded, so any stage can be killed and re-run without losing work.

```
schema.sql                   papers and citations, applied once before anything else
indexes.sql                  every index, applied after the bulk loads
stage0_fetch_source_json.py  refresh the source JSON and insert the ids papers is missing
stage1_download_pdf.py       fetch the PDF of every stage 0 paper
stage2_download_html.py      fetch the LaTeXML HTML of every stage 1 paper
stage3_embed_papers.py       embed every stage 2 abstract
stage4_label_survey.py       score every stage 3 paper for looking like a review
```

## The stage column

```
0  in the table, nothing fetched
1  PDF on disk
2  HTML on disk
3  embedded, embed_full written
4  scored, survey_probability written
```

One paper has one PDF, named for the version `latest_version` holds. The bulk mirror carries only
v1 of most revised papers, so stage 1 asks for v1 on a miss and saves it under the latest name.
`latest_version` is the source's answer and no stage rewrites it, or stage 0 would read the row as
a new version on every run and fetch it again forever.

`is_citation_parsable` is not a stage. It is null until `citation_preprocess` has parsed the paper
once, then true or false depending on whether the html carried a bibliography, which is what stops
the fifth of the corpus that carries none from being parsed again on every run.

The cascade is strict. A paper that fails one stage never reaches the next, so it keeps its metadata and gets no vector.

## Running it

Each script reads `config.toml` from the repo root, or `--config_path` for another file.

```sh
psql -h "$PWD/.pg" -p 5433 -d arxivkg -f scripts/papers_preprocess/schema.sql

uv run python scripts/papers_preprocess/stage0_fetch_source_json.py
uv run python scripts/papers_preprocess/stage1_download_pdf.py
uv run python scripts/papers_preprocess/stage2_download_html.py
uv run python scripts/papers_preprocess/stage3_embed_papers.py
uv run python scripts/papers_preprocess/stage4_label_survey.py

psql -h "$PWD/.pg" -p 5433 -d arxivkg -f scripts/papers_preprocess/indexes.sql
```

`stage0` takes `--no-fetch` to skip the download and use the JSON already on disk.

Stage 3 needs `llama-embed` up, and refuses to fit UMAP while any paper is still at stage 2, since fitting on a partial corpus yields a model whose neighborhoods are wrong but whose output looks fine.

Stage 5 needs `llama-router` up, and refuses to run while any paper sits at stage 3. It names leaves from the papers nearest their centroid, then parents and grandparents from their children's names, and rebuilds `topics` in full every run, since stage 4 reassigns what a given leaf id means. Reasoning is disabled on every call, without which the model spends its whole completion budget on chain of thought and returns nothing.

Only the embedding is incremental. Stages 3 and 4 refit over the whole corpus on every run, so a delta costs a full UMAP transform and a full reclustering. Fitting either one on the delta alone gives the new papers a label space unrelated to the one the rest of the corpus already carries.
