# export

Turns the built store into files that leave it, under `[export] EXPORT_PATH`, and the manager runs both stages from its Export tab.
Both read and never write the store.

```
stage0_dump_store.py      graphiv-<date>.dump, the whole store as one pg_dump archive, sentences included
stage1_export_parquet.py  graphiv-<date>/, every paper with its pdf, html and embedding, as Parquet, and both classifiers
```

```sh
uv run python scripts/export/stage0_dump_store.py
uv run python scripts/export/stage1_export_parquet.py
```

The dump is the backup and what `docs/restore.md` restores, and the Parquet release is what gets published:

```
graphiv-<date>/
  papers/       metadata, abstract, review probability, and the embedding as 768 float16
  topics/       each paper's three tree levels and their names
  citations/    resolved citations between exported papers, with intent and score, and no sentence
  classifiers/  citation_intent and survey, each loadable with from_pretrained
  manifest.json the row counts and each classifier's sha256
```

A citation sentence is the citing paper's own text, and most arXiv licenses withhold redistribution, so the release carries none.
Each stage writes under a `.part` name and renames it only once everything landed, so a stopped run leaves nothing that looks finished.
The dump stops once its disk falls under 10 GB free, since that disk may also hold the cluster's WAL.
