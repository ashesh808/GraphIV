# papers_preprocess

Builds the `papers` table from a metadata dump, one stage at a time. Every stage reads its own queue off the `stage` column, does one thing, and advances the rows that succeeded, so any stage can be killed and re-run without losing work.

```
schema.sql                   papers, citations and topics, applied once before anything else
indexes.sql                  every index, applied after the bulk loads
stage0_fetch_source_json.py  refresh the source JSON and insert the ids papers is missing
stage1_download_pdf.py       fetch the PDF of every stage 0 paper
stage2_download_html.py      fetch the LaTeXML HTML of every stage 1 paper
stage3_embed_papers.py       embed every stage 2 abstract, then fit UMAP and reduce
stage4_create_topic_tree.py  cluster the reduced vectors into three topic levels
stage5_topic_labeling.py     name every node of the tree with an LLM
```

## The stage column

```
0  in the table, nothing fetched
1  PDF on disk
2  HTML on disk
3  embedded, both embed_full and embed_umap
4  clustered, level_0 through level_2
```

The cascade is strict. A paper that fails one stage never reaches the next, so it keeps its metadata and gets no vector.

## Running it

Each script reads `config.toml` from the repo root, or `--config_path` for another file.

```sh
psql -h "$PWD/.pg" -p 5433 -d arxivkg -f scripts/papers_preprocess/schema.sql

uv run python scripts/papers_preprocess/stage0_fetch_source_json.py
uv run python scripts/papers_preprocess/stage1_download_pdf.py
uv run python scripts/papers_preprocess/stage2_download_html.py
uv run python scripts/papers_preprocess/stage3_embed_papers.py
uv run python scripts/papers_preprocess/stage4_create_topic_tree.py
uv run python scripts/papers_preprocess/stage5_topic_labeling.py

psql -h "$PWD/.pg" -p 5433 -d arxivkg -f scripts/papers_preprocess/indexes.sql
```

`stage0` takes `--no-fetch` to skip the download and use the JSON already on disk.

Stage 3 needs `llama-embed` up, and refuses to fit UMAP while any paper is still at stage 2, since fitting on a partial corpus yields a model whose neighborhoods are wrong but whose output looks fine.

Stage 5 needs `llama-router` up, and refuses to run while any paper sits at stage 3. It names leaves from the papers nearest their centroid, then parents and grandparents from their children's names, and rebuilds `topics` in full every run, since stage 4 reassigns what a given leaf id means. Reasoning is disabled on every call, without which the model spends its whole completion budget on chain of thought and returns nothing.

Only the embedding is incremental. Stages 3 and 4 refit over the whole corpus on every run, so a delta costs a full UMAP transform and a full reclustering. Fitting either one on the delta alone gives the new papers a label space unrelated to the one the rest of the corpus already carries.
