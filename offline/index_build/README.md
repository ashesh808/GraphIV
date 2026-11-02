# Runtime corpus snapshots

Build immutable SQLite, FAISS, and citation-graph artifacts from supplied data. The
builder preserves existing document embeddings; it does not generate papers,
embeddings, citation sentences, or intent labels.

| Module | Responsibility |
| --- | --- |
| `run_hf.py` | Resolve a published HF release to a commit, validate and download its Parquets, build, and optionally publish |
| `parquet.py` | Stream the published paper, citation, and topic tables in bounded Arrow batches |
| `build.py` | Import Parquet, PostgreSQL, or JSONL records and validate a local immutable snapshot |
| `indexes.py` | Build an exact flat or compressed IVF/SQ8 FAISS index from stored vectors |
| `graph.py` | Deduplicate resolved citation pairs in SQLite and write both CSR graph directions |
| `publish.py` | Upload immutable artifacts and optionally activate the manifest |

## Published GraphIV release

The [GraphIV-2026-10-01 dataset card](https://huggingface.co/datasets/kkuroma/GraphIV/blob/GraphIV-2026-10-01/README.md)
describes 3,165,827 papers, 74,764,672 citation occurrences, and one topic row per
paper. The release contains seven paper, four citation, and one topic Parquet file
(6,486,435,579 source bytes). These are source-release declarations; the completed
build's manifest records the imported counts and checksums.

Access to the data requires HF authorization. Accept the dataset's terms in HF and
supply `HF_TOKEN` through the environment or a local HF login. The builder does not
accept terms, log tokens, or replace unavailable data with sample records.

```sh
uv run --no-dev --group index-build python -m offline.index_build.run_hf \
  --workdir /mnt/graphiv-build \
  --revision GraphIV-2026-10-01 \
  --snapshot-id graphiv-2026-10-01-nomic-sq8 \
  --index-kind ivfsq8
```

The tag is resolved once to an immutable commit. Metadata is saved to
`source-manifest.json`, including every source file's size and available LFS
SHA-256. Downloads use that commit; all declared files, sizes, checksums, Parquet
schemas, and footer row counts are checked. Every primary stream must consume
exactly its declared count. No JSONL expansion is required.

Published embeddings are 768-dimensional float16 vectors from
`nomic-embed-text-v2-moe`. SQLite retains their original float16 values. Queries
must use this same model and its documented `search_query:` prefix; an unrelated
embedding model, including OpenAI's 1536-dimensional model, is incompatible. The
builder never re-embeds the corpus.

Citation occurrences remain separate SQLite rows, including repeated source/target
pairs. Published intent labels and float32 confidence values are retained; completed
labels receive `stage = 1`. The release omits citation sentences, so `sentence` is
`NULL` and the manifest explicitly sets `citation_sentences = false`. There is no
PDF retrieval or JIT extraction. Consumers can use precomputed intents and must
qualify the absence of sentence-level evidence. Flattened topic names are rebuilt
into the existing hierarchical tables; incomplete assignments remain incomplete.

Progress is newline-delimited JSON with phase, elapsed time, peak RSS in bytes, and
input row counts. `build-report.json` records final counts, artifact/index metrics,
source provenance, and redacted failure types. A failed build leaves no visible
snapshot. Rerunning uses cached source files; a completed snapshot is reused only
after artifact checksums, source commit, model, and build options match. Change the
snapshot ID for a different source or index configuration.

To build from Parquets already present on disk:

```sh
uv run --no-dev --group index-build python -m offline.index_build.build \
  --parquet-root /mnt/graphiv-build/source/COMMIT \
  --source-manifest /mnt/graphiv-build/source-manifest.json \
  --source-commit COMMIT \
  --snapshot-id graphiv-2026-10-01-nomic-sq8 \
  --embedding-model nomic-embed-text-v2-moe \
  --index-kind ivfsq8 \
  --out /mnt/graphiv-build/snapshots/graphiv-2026-10-01-nomic-sq8
```

## Index accuracy and resource sizing

The generic builder defaults to `flat`: L2-normalized vectors in exact
`IndexFlatIP`. `run_hf` defaults to `ivfsq8`, a normalized inner-product IVF index
with 8-bit scalar quantization, bounded deterministic training, and sequential
SQLite `vector_ids` labels. Defaults are `--nlist 1024 --nprobe 128
--train-size 65536 --seed 0`. Small fixtures reduce the number of lists to what
their training set supports. Configuration and actual training counts are recorded
in the manifest.

The runtime reranks ANN candidates using the original stored vectors and widens
candidate/probe budgets under filters. Compression changes candidate recall; it is
not an exact-search equivalence claim. Evaluate recall and report quality against
flat search on the actual release before choosing production settings. Retrieval,
mining, scoring, and report composition algorithms are unchanged.

For `N` embeddings of dimension `d`, a flat index requires approximately `4*N*d`
bytes of RAM. Float16 vectors in SQLite require `2*N*d` disk bytes before database
page overhead; IVF/SQ8 codes use roughly `N*d` bytes plus IDs, centroids, and other
index overhead. At the declared release size these vector payloads alone are about
9.7 GB flat, 4.9 GB SQLite float16, and 2.4 GB SQ8, respectively. Paper metadata,
all citation occurrences and indexes, graph arrays, model weights, and temporary
sort/build files add to these numbers.

Imports run in a private staging database with a bounded SQLite page cache,
file-backed temporary storage, deferred citation indexes, and bulk surname
indexing. Graph construction deduplicates integer pairs in SQLite, streams sorted
CSR indices into disk-backed NumPy arrays, and compresses the existing GraphExport
format. It does not collect all edges or vectors into Python or call `np.unique`
over a corpus-sized edge array. FAISS training uses a bounded sample and adds
vectors in batches.

### Quality receipt

Run the quality gate on the completed snapshot before activation. Supply JSONL
queries with `id` and `text`; optional `date_max` (ISO date) and `blocked` IDs test
historical and exclusion filters. The command encodes questions with the pinned
original Nomic model, scans the stored vectors in bounded batches for an
independent exact top-200 baseline, and compares compressed-index recall and exact
returned cosine scores. It also re-encodes 16 actual published title/abstract pairs
using `search_document: Title: <title>\nAbstract: <abstract>`, the original 512-token
window, and requires cosine similarity of at least 0.999 to their stored vectors.

```sh
uv run --no-dev --extra nomic python -m offline.index_build.benchmark \
  --snapshot-path /mnt/graphiv-build/snapshots/graphiv-2026-10-01-nomic-sq8 \
  --queries /mnt/graphiv-build/quality-queries.jsonl \
  --model-cache /mnt/graphiv-build/nomic \
  --nprobe 256 --nprobe 512 \
  --out /mnt/graphiv-build/quality-receipt.json
```

The receipt records each query's recall, score error, filter settings and latency,
along with artifact hashes, index settings, file sizes, process peak RSS, and the
document comparisons. Default acceptance is at least 0.98 recall for every query
and score error at most 1e-8. A passing alternative `nprobe` is only a recommendation;
the active stored configuration must pass. Rebuild with a new snapshot ID and
accepted settings if required. `--index-only` accepts supplied query embeddings
without the document-space gate and explicitly cannot pass deployment validation.
Fixtures establish implementation behavior; only a receipt generated from the
actual release establishes its measured recall and model compatibility.

Size both build disk and runtime cache from measured artifacts; the small default
Container Apps deployment cannot hold a full release on its ephemeral disk. The
published workflow supports a separate builder job and persistent `/var/lib/graphiv`
cache. A 100 GiB share is a provisioned capacity, not a measured size guarantee.
Source Parquets, output SQLite/index/graph, working files, and runtime snapshots may
coexist. Inspect `build-report.json`, disk usage, RSS, and runtime readiness before
starting research.

## Outputs and publication

| File | Contract |
| --- | --- |
| `metadata.sqlite` | [Schema version 1](../../src/storage/schema.sql), original vector blobs with explicit `vector_dtype`, and `vector_ids` mapping |
| `index.faiss` | Flat or IVF/SQ8 normalized inner-product index, with original ordinal IDs |
| `graph.npz` | Existing GraphExport arrays, deduplicated resolved paper pairs and both CSR directions |
| `manifest.json` | Artifact locations/checksums, model/dimension, source commit/files/counts, capabilities, build/index metrics |

Runtime loaders validate artifacts before the output directory is atomically made
visible. An existing destination is never overwritten. Individual citation rows
are retained in SQLite; graph pairs are deduplicated to preserve GraphExport's
existing semantics.

Build commands do not upload automatically. Publication is an explicit action:

```sh
uv run --no-dev python -m offline.index_build.publish \
  --snapshot_path /mnt/graphiv-build/snapshots/graphiv-2026-10-01-nomic-sq8

# Activate only after the real-corpus quality benchmark passes.
uv run --no-dev python -m offline.index_build.publish \
  --snapshot_path /mnt/graphiv-build/snapshots/graphiv-2026-10-01-nomic-sq8 --activate
```

The initial `run_hf` job uses `--publish` alone, leaving the active manifest unchanged.
Run the real-corpus quality benchmark against the built snapshot, review its receipt,
and activate only after it passes. Then rerun the verified snapshot with
`--publish --activate`; completed local artifacts are reused after checksum and
configuration verification. `--activate` requires `--publish`. Azure authentication
uses managed identity (`AZURE_CLIENT_ID` when assigned) and
`GRAPHIV_STORAGE_ACCOUNT_URL`; container overrides are
`GRAPHIV_VECTOR_CONTAINER`, `GRAPHIV_METADATA_CONTAINER`, and
`GRAPHIV_GRAPH_CONTAINER`. `GRAPHIV_MANIFEST_BLOB` defaults to `manifest.json`.
Artifacts publish to manifest-defined paths; the immutable
`snapshots/<id>/manifest.json` is committed last, then the active manifest alias is
updated if requested. See [storage configuration](../../src/storage/README.md).

For a snapshot already published completely, the activation helper avoids rereading
the large local artifacts. Supply the actual passing benchmark receipt, its reviewed
manifest SHA, and the expected snapshot ID:

```sh
uv run --no-dev python -m offline.index_build.activate \
  --quality-receipt /path/to/quality-receipt.json \
  --manifest-sha256 "$GRAPHIV_EXPECTED_MANIFEST_SHA" \
  --snapshot-id graphiv-2026-10-01-nomic-sq8 \
  --out /tmp/graphiv-activation-review
```

This defaults to a review without cloud writes. It checks the published immutable
manifest, full release identity/counts, quality gates, and all three producer hash/size
properties; `--producer-sizes` optionally supplies a JSON map keyed by `vectors`,
`metadata`, and `graph`. The previous alias bytes and rollback details are saved locally.
After reviewing the real receipt and publication completion, use the same inputs with
`--execute` and a new empty `--out` directory to overwrite only the active alias and
verify its readback. The restarted application independently downloads and checksums
the actual artifact bytes before research becomes ready.

The separate offline image includes PyArrow and HF downloading without Torch:

```sh
docker build -f offline/index_build/Dockerfile -t graphiv-index-builder .
docker run --rm --env HF_TOKEN \
  --mount type=bind,src=/mnt/graphiv-build,dst=/var/lib/graphiv/build \
  graphiv-index-builder --workdir /var/lib/graphiv/build
```

The container uses SQLite's `unix-dotfile` locking for its unique private staging
database because this Azure Files mount does not provide compatible POSIX advisory
locks. Set `GRAPHIV_SQLITE_WRITE_VFS=unix-dotfile` when invoking the builder directly
on the same share; leave it unset for ordinary local filesystems. Completed runtime
snapshots are immutable, checksum-verified, and opened with `mode=ro&immutable=1`.
Never modify those files beneath an active reader; publish a new snapshot ID instead.

Use a work directory with sufficient space. For Azure publication, configure the
storage environment above and an identity with artifact-container write access;
the application identity only needs corpus read access. The Dockerfile-specific
ignore file includes the offline code while excluding local data and secrets.

## Existing PostgreSQL and JSONL sources

The original import paths remain available. Export the existing PostgreSQL corpus
using the DSN in `configs/offline.toml`:

```sh
uv run python -m offline.index_build.build \
  --postgres --snapshot-id arxiv-2026-11-01 \
  --embedding-model nomic-embed-text-v2-moe \
  --out data/snapshots/arxiv-2026-11-01
```

`GRAPHIV_POSTGRES_DSN` overrides the configured DSN. All four source tables are read
in one read-only, repeatable-read transaction. Original `halfvec` values are cast
to float32 arrays; the source database is unchanged.

For JSONL, replace `--postgres` with `--papers papers.jsonl --citations
citations.jsonl`; optional `--topics` and `--topic-names` accept separate files.
Records use original PostgreSQL column names:

| Input | Fields |
| --- | --- |
| Papers | `arxiv_id`, `title`, `abstract`, ISO `date`, `stage`, `primary_category`, `authors`, `surnames` array, `embed_full` float array, `survey_probability` |
| Citations | `citation_id`, `source_id`, nullable `target_id`, `stage`, `sentence`, `intent`, `intent_score` |
| Topic tree | `arxiv_id`, `stage`, `level_0`, `level_1`, `level_2` |
| Topic names | `level_0`, nullable `level_1`, nullable `level_2`, `name` |

`embedding` aliases `embed_full`. Missing paper stages default to 3 when a vector
is supplied, otherwise 0; citation stages default to 0. Use citation `stage = 1`
for completed labels. Absent surnames become an empty array. Embedded papers
require a date, a finite nonzero vector, and consistent dimensions; `--dimension`
can additionally enforce the expected dimension. Generic imports default to
float32 storage; `--vector-dtype float16` is an explicit option.

On macOS, run FAISS/runtime tests separately from Torch recipe-tuning tests because
their wheels bundle different OpenMP runtimes:

```sh
uv run pytest --ignore=tests/recipe_tuning
uv run pytest tests/recipe_tuning
```

No duplicate-runtime environment override is required or enabled.

## Real deployment acceptance

After publishing the full snapshot and making research readiness true, run the
real-only acceptance command. It submits two actual research jobs (linear
attention/state-space models and RAG grounding) and can incur model usage. Supply
`GRAPHIV_API_TOKEN` in the environment; credentials are never CLI arguments.

```sh
uv run --no-dev python -m offline.index_build.verify_deployment \
  --api-origin "$GRAPHIV_API_URL" \
  --vercel-origin "$GRAPHIV_WEB_URL" \
  --out /tmp/graphiv-acceptance-2026-11-01 \
  --timeout 3600 --verify-blob
```

`--verify-blob` uses the same Azure SDK identity/storage environment as publication,
with read permissions. It independently lists and reads each committed report
marker, verifies all immutable generation payload checksums against HTTP downloads,
and compares the active corpus manifest with the reports' provenance. Omit the
flag when independently verifying Blob access is unavailable; the receipt then
identifies its persistence proof as HTTP library/read/download only. An optional
`--corpus-database /path/to/metadata.sqlite` additionally checks IDs, titles and
authors against a separate read-only local corpus copy.

The command rejects unready research before any submission. Both reports must
complete and persist all five standard files, appear in the API library, render
the submitted question on Vercel, and identify the full pinned published release
with all source hashes/counts. All returned citation/paper IDs and paper metadata
are checked through the authenticated read-only `/api/corpus/validate` endpoint.
Each case needs a nonempty retrieval pool and kept set; together they must produce
nonzero mined and persisted graph edges, lineages, and successors. Real execution
RSS/container peaks, timings, stages, citations, artifact hashes, source provenance,
and degraded evidence features are captured. Missing metrics or absent evidence
fail acceptance instead of becoming inferred successes or synthetic zero counts.

Use `--question` twice to replace the two questions; `--effort` and `--mode` select
supported research inputs. `--timeout` bounds job polling across both cases;
`--request-timeout` bounds each HTTP request. A Vercel protection bypass, if needed,
comes only from `VERCEL_AUTOMATION_BYPASS_SECRET` and is sent only to the frontend.
API bearer credentials are sent only to the API origin; redirects are refused.

To verify the two real jobs already submitted through the browser, add `--job-id`
twice, in question order. Exactly two distinct server-generated IDs are required.
Every polled job must match its exact question, mode, and effort; the verifier then
checks the same completed reports, corpus records, metrics, and persistence without
submitting additional research. Keep the supplied/default question text and settings
identical to the browser submissions. Existing IDs do not automatically establish
interactive browser verification; that observation remains a separate recorded check.

`verification.json`, `verification.md`, and downloaded report/corpus-record files
are written to a new output directory. A failure produces an explicitly failed
receipt and exit status 1. There is no fixture or offline-success mode. No passing
receipt exists until the actual deployed services have completed these checks.
This command verifies HTTP/SSR behavior; interactive browser submission, paper
selection, graph interaction, and scientific report review remain separate checks.
