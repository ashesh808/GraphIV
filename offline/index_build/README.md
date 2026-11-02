# Runtime corpus snapshots

Builds immutable FAISS, SQLite, and citation-graph artifacts from supplied corpus data.
The builder does not generate embeddings or seed the service with example papers.
The query embedding endpoint must use the same model as the supplied paper vectors.

```text
build.py       build and validate a local snapshot from PostgreSQL or JSONL
publish.py     explicitly upload a validated snapshot; optionally activate its manifest
```

Export the existing PostgreSQL corpus using the DSN in `configs/offline.toml`:

```sh
uv run python -m offline.index_build.build \
  --postgres \
  --snapshot-id arxiv-2026-11-01 \
  --embedding-model nomic-embed-text-v2-moe \
  --out data/snapshots/arxiv-2026-11-01
```

`GRAPHIV_POSTGRES_DSN` overrides the configured DSN. The exporter reads all four tables
in one read-only, repeatable-read transaction. Original `halfvec` values are cast to
float32 arrays; the source database is not modified.

Alternatively, supply JSONL files:

```sh
uv run python -m offline.index_build.build \
  --papers data/export/papers.jsonl \
  --citations data/export/citations.jsonl \
  --topics data/export/topic_tree.jsonl \
  --topic-names data/export/topic_names.jsonl \
  --snapshot-id arxiv-2026-11-01 \
  --embedding-model nomic-embed-text-v2-moe \
  --out data/snapshots/arxiv-2026-11-01
```

Topics and topic names are optional. Citations may be an empty JSONL file.
Records use the original PostgreSQL column names:

| Input | Fields |
| --- | --- |
| Papers | `arxiv_id`, `title`, `abstract`, ISO `date`, `stage`, `primary_category`, `authors`, `surnames` array, `embed_full` float array, `survey_probability` |
| Citations | `citation_id`, `source_id`, nullable `target_id`, `stage`, `sentence`, `intent`, `intent_score` |
| Topic tree | `arxiv_id`, `stage`, `level_0`, `level_1`, `level_2` |
| Topic names | `level_0`, nullable `level_1`, nullable `level_2`, `name` |

`embedding` is accepted as an alias for `embed_full`. Missing paper stages default to
3 when a vector is supplied, otherwise 0; citation stages default to 0. Set citation
`stage = 1` for completed labels. Supply surnames for author lookup; absent/null
surnames remain an empty array. Embedded papers require a date, a finite nonzero
vector, and one consistent dimension. `--dimension` can additionally enforce the
expected dimension.

Each output directory contains:

| File | Contract |
| --- | --- |
| `metadata.sqlite` | [`src/storage/schema.sql`](../../src/storage/schema.sql), schema version 1, original float32 vector blobs and `vector_ids` label mapping |
| `index.faiss` | L2-normalized vectors in an inner-product `IndexFlatIP`; labels are sequential SQLite `vector_ids.faiss_id` values |
| `graph.npz` | The existing GraphExport arrays, with resolved citation pairs deduplicated and both CSR directions preserved |
| `manifest.json` | Snapshot ID, embedding model/dimension, artifact locations and SHA-256 checksums |

The builder validates artifacts with the runtime loaders before atomically making the
output directory visible. It refuses to replace an existing directory. Choose a new
snapshot ID and destination for every version.

The default exact FAISS index needs about `4 × papers × embedding dimension` bytes of
RAM. SQLite retains another vector copy on disk, plus paper metadata and citation
sentences. Graph construction also needs working memory. Size the build machine,
runtime memory, and artifact cache for the actual corpus; a full arXiv snapshot will
not fit the small infrastructure defaults.

Publication is a separate action:

```sh
uv run python -m offline.index_build.publish \
  --snapshot_path data/snapshots/arxiv-2026-11-01

# Switch the active metadata/manifest.json only after all immutable objects exist.
uv run python -m offline.index_build.publish \
  --snapshot_path data/snapshots/arxiv-2026-11-01 --activate
```

Authentication uses the Azure SDK environment configuration documented in
[`src/storage`](../../src/storage/README.md). Files publish to their manifest-defined
containers; an immutable `snapshots/<id>/manifest.json` publishes last. Activation
requires `--activate`; `--manifest_blob` changes the active alias. No build command
uploads data automatically.

On macOS, run FAISS/runtime tests separately from the Torch recipe-tuning tests because
their wheels bundle different OpenMP runtimes:

```sh
uv run pytest --ignore=tests/recipe_tuning
uv run pytest tests/recipe_tuning
```

No duplicate-runtime environment override is required or enabled.
