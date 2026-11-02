# Runtime corpus and report storage

Corpus and report persistence can be selected independently. For PostgreSQL in
Azure, set `GRAPHIV_RUNTIME=azure`, `GRAPHIV_STORAGE_BACKEND=postgres`,
`GRAPHIV_POSTGRES_DSN`, and `GRAPHIV_GRAPH_PATH` to a compatible mounted graph.
Reports default to Azure Blob in cloud deployments. Set
`GRAPHIV_REPORT_STORAGE_BACKEND=local|azure` to override that choice explicitly.

GraphIV separates a read-only research corpus from the reports a running instance writes.
The algorithms consume [`CorpusStore`](../src/storage/corpus.py); report readers and
writers consume [`ReportStore`](../src/storage/runs.py). Neither contract requires the
runtime to own a PostgreSQL server or to keep its writable data on persistent local disk.

## Backends

| `[storage] BACKEND` | Corpus reads | Completed reports |
| --- | --- | --- |
| `postgres` | The existing PostgreSQL/pgvector store and configured GraphExport file | Local run directories |
| `sqlite` | Immutable SQLite metadata, a FAISS index, and the configured GraphExport file | Local run directories |
| `azure` | A checksummed SQLite/FAISS/GraphExport snapshot downloaded from Blob Storage | Azure Blob Storage, with a local read cache |

`PostgresCorpus` retains the existing queries. `SQLiteCorpus` implements the same explicit
read operations for retrieval, mining, author/topic lookup, grounding, and paper metadata.
The ranking recipes and research algorithms are shared by both implementations.

The SQLite contract is [`src/storage/schema.sql`](../src/storage/schema.sql), version 1.
`papers.embed_full` retains the original vectors as little-endian float32 bytes; the FAISS
index uses normalized vectors with inner-product distance. Every FAISS integer label maps
to a paper through `vector_ids(faiss_id, arxiv_id)`. The adapter validates the index metric
and dimensions. A separate ID-map file is not required.

For local snapshot reads, set `BACKEND = "sqlite"`, `METADATA_PATH`, and `INDEX_PATH` in
[`configs/runtime.toml`](../configs/runtime.toml), plus `[dataset] GRAPH_PATH`.
Paths ending in `_PATH` are relative to that configuration file. The environment overrides
`GRAPHIV_METADATA_PATH`, `GRAPHIV_INDEX_PATH`, and `GRAPHIV_GRAPH_PATH` can select absolute
deployment-specific files.

## Azure snapshot manifest

The runtime reads `manifest.json` from the metadata container. The three artifact names
below are examples; each manifest reference supplies its exact container and object name.

```json
{
  "version": 1,
  "snapshot_id": "arxiv-2026-11-01",
  "embedding": {
    "dimension": 768,
    "model": "the-model-used-to-build-this-index"
  },
  "artifacts": {
    "vectors": {
      "container": "vector-indexes",
      "blob": "snapshots/arxiv-2026-11-01/index.faiss",
      "sha256": "<64-character SHA-256 hex digest>"
    },
    "metadata": {
      "container": "metadata",
      "blob": "snapshots/arxiv-2026-11-01/metadata.sqlite",
      "sha256": "<64-character SHA-256 hex digest>"
    },
    "graph": {
      "container": "citation-graphs",
      "blob": "snapshots/arxiv-2026-11-01/graph.npz",
      "sha256": "<64-character SHA-256 hex digest>"
    }
  }
}
```

`version`, a safe `snapshot_id`, a positive `embedding.dimension`, and all three references
with real checksums are required. `embedding.model` is optional; when present, it must match
the runtime's embedding model. The configured embedding endpoint must produce the same
vector dimension as the published index.

Publish all immutable artifact objects before publishing the manifest that references them.
Use new object names for each snapshot. The runtime streams downloads into a temporary
directory, checks every SHA-256 digest, and exposes the completed snapshot through one
directory rename. A failed download does not replace a previously complete snapshot.
Cached artifacts are verified before reuse; corrupt cache contents fail preparation instead
of being treated as valid data.

The local snapshot directory is keyed by the snapshot ID and manifest digest. A process
keeps the snapshot it opened for its lifetime; restart the application revision to load a
new published manifest. Corpus construction belongs in [`offline/index_build`](../offline/index_build/).

The explicit publisher validates every local checksum before its first upload:

```sh
uv run python -m offline.index_build.publish --snapshot_path /path/to/built-snapshot
# Activate the fully published snapshot for new application processes:
uv run python -m offline.index_build.publish --snapshot_path /path/to/built-snapshot --activate
```

The first command publishes immutable artifacts and `snapshots/<snapshot_id>/manifest.json`.
Only `--activate` updates the runtime's manifest alias, which defaults to `manifest.json`
and can be changed with `--manifest_blob` or `GRAPHIV_MANIFEST_BLOB`. Repeating a publication
reuses objects whose stored producer checksum and size match; conflicts are rejected instead
of overwritten. Use a publisher identity with write permissions to all artifact containers,
separate from the application identity's read access to vector indexes.

## Capacity planning

The builder currently produces an uncompressed `IndexFlatIP`. For `N` vectors of dimension
`d`, the vector payload alone needs approximately **`4 × N × d` bytes of index RAM**.
Budget additional memory for the loaded citation graph, SQLite page cache and query results,
FAISS overhead, and the Python application. The SQLite export also stores each original
float32 vector, adding approximately `4 × N × d` bytes on disk before paper metadata,
citations, indexes, and database overhead. Artifact downloads and their temporary staging
directories need disk space in addition to these working sets.

The current Azure default of **1 CPU and 2 GiB** is suitable for bringing up the empty API
and its health/configuration surfaces. It is not a capacity claim for a full arXiv corpus.
The dataset has not been supplied, so no production memory or disk requirement can be
asserted from the deployment alone.

Measure the actual exported index, metadata, and graph sizes, then measure resident memory
after loading that snapshot before selecting application resources. A larger workload
profile may be needed. A persistent cache can avoid repeated large downloads but does not
reduce the RAM required by a flat FAISS index. A compressed index is a separate engineering
choice requiring compatibility, retrieval-quality, and performance checks; the current
builder does not silently substitute one to fit the default container size.

## Report publication and reads

Local reports preserve the established five-file layout:

```text
<slug>/
  run.json
  report.md
  papers.json
  graph.json
  report.json
```

The report tool finishes writing all five local files before calling the configured report
store. `BlobReportStore` uploads the four content files into an immutable generation:

```text
<slug>/_versions/<generation>/report.md
<slug>/_versions/<generation>/papers.json
<slug>/_versions/<generation>/graph.json
<slug>/_versions/<generation>/report.json
<slug>/run.json
```

The root `run.json` is uploaded **last**. It contains the usual run metadata plus a
`_graphiv_storage` object identifying the generation and each content file's checksum.
Readers list only these root commit markers. A failed first upload remains invisible;
a failed replacement leaves the prior committed generation readable. Uncommitted payload
objects are not listed as reports, and the runtime performs no Blob deletion.

Report details and downloads hydrate the committed generation into the five standard local
filenames, verifying checksums before the cache directory becomes visible. File access is
limited to those five filenames; traversal names and symlink escapes are rejected. Existing
direct `<slug>/<filename>` Blob reports can still be read, while new writes use generations.

The HTTP report routes delegate to the report store and do not open the corpus. Provider
failures return an unavailable response rather than silently showing unrelated local data.
The original `read_runs(root)` and `read_one(root, slug)` functions remain available for
local callers.

## Deployment configuration

| Environment variable | Meaning |
| --- | --- |
| `GRAPHIV_RUNTIME=azure` | Enables deployment defaults and disables inherited local model/DSN settings |
| `GRAPHIV_STORAGE_BACKEND=azure` | Selects Blob snapshots and durable Blob reports |
| `GRAPHIV_STORAGE_ACCOUNT_URL` | HTTPS Blob service endpoint, without embedded credentials or SAS query |
| `AZURE_CLIENT_ID` | User-assigned managed identity client ID |
| `GRAPHIV_METADATA_CONTAINER` | Manifest container; defaults to `metadata` |
| `GRAPHIV_MANIFEST_BLOB` | Manifest object name; defaults to `manifest.json` |
| `GRAPHIV_VECTOR_CONTAINER` | Infrastructure/publisher vector container; normally `vector-indexes` |
| `GRAPHIV_GRAPH_CONTAINER` | Infrastructure/publisher graph container; normally `citation-graphs` |
| `GRAPHIV_REPORTS_CONTAINER` | Durable report container; defaults to `reports` |
| `GRAPHIV_CACHE_PATH` | Writable temporary cache root; Azure defaults to `/var/lib/graphiv/cache` |
| `GRAPHIV_LLM_API_URL`, `GRAPHIV_LLM_MODEL` | Explicit external language-model configuration |
| `GRAPHIV_EMBED_API_URL`, `GRAPHIV_EMBED_MODEL` | Explicit external embedding configuration matching the snapshot |
| `GRAPHIV_LLM_API_KEY`, `GRAPHIV_EMBED_API_KEY` | Optional model credentials supplied through deployment secrets |
| `GRAPHIV_API_TOKEN` | Bearer token protecting the deployed API |

`DefaultAzureCredential` obtains tokens for the configured managed identity. Storage account
keys are not required. `AZURE_STORAGE_CONNECTION_STRING` is accepted only for a loopback
HTTP Azurite endpoint in local tests; public-account connection strings are rejected.

The vector, metadata, and graph objects are read according to the manifest's container
references. The Azure identity must have read access to all three. The existing Terraform
roles grant report writes separately from report reads: enable `allow_report_reads` for a
deployment that serves the saved-report library. A write-only report role can publish reports
but cannot list or hydrate them.

## Readiness and process lifetime

`/health/live` reports that the HTTP process is running. The saved-report library can operate
as soon as report storage and its read permissions are available, even before a research
corpus has been published.

`/health/ready` reports research readiness after the corpus snapshot has downloaded and
validated, the selected backend has opened, and required model/authentication configuration
is present. Preparation does not generate a model completion or validate a model service's
answers. Missing artifacts or configuration keep research unavailable with an explicit
reason; they do not prevent the liveness endpoint from responding.

Run **one Python process in one application replica**. Held MCP rankings, research queue
entries, and job status records currently live in memory. Research jobs are serialized by
the coordinator; pending work and session IDs do not survive a process restart. Completed
Blob reports do survive. Additional workers or replicas require shared session/job state
and a corresponding routing design.

## Verification

The storage tests cover interrupted downloads, checksum failures, path guards, cache
validation, commit-marker ordering, replacement failures, and local API compatibility.
The opt-in Azurite test exercises the actual Azure SDK against a local emulator:

```sh
uv run pytest tests/storage/test_blobs.py tests/storage/test_runs.py -q
# Supply a local-only connection string through the environment, then run:
uv run pytest tests/storage/test_runs.py::test_azurite_snapshot_and_report_roundtrip -m slow -q
```

The integration test reads `GRAPHIV_TEST_AZURITE_CONNECTION_STRING`, creates uniquely named
test containers on that emulator, and removes those test containers after the roundtrip.

The opt-in PostgreSQL compatibility tests run the actual retained queries against pgvector,
export those same records into SQLite/FAISS, and compare search, vectors, metadata, citation
multiplicity, and date/stage filters. Supply a disposable loopback PostgreSQL server through
`GRAPHIV_TEST_POSTGRES_DSN`, then run:

```sh
uv run pytest tests/storage/test_postgres_integration.py -m slow -q
```

The fixture creates and drops a uniquely named test schema. Numeric comparisons allow the
expected small float32/halfvec precision differences; ranking order and filtering remain
explicitly checked on the fixture. These local integration fixtures do not populate the
deployment with a corpus.
