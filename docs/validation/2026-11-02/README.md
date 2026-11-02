# Cloud vs local GraphIV

This comparison describes the **cloud deployment validated on 2 November 2026** and
the **local defaults in this repository**. Both run the same Python research
pipeline. The main differences are where the data lives, how models are served,
and the resources available to the backend.

**Cloud status:** full-corpus research passed, including two questions submitted
through [graphiv.vercel.app](https://graphiv.vercel.app), completed reports, paper
inspection, citation graphs, and independently verified Azure Blob persistence.
See the [acceptance summary](final-acceptance/acceptance-summary.json).

## At a glance

| Component | Local setup | Validated cloud deployment |
| --- | --- | --- |
| Frontend | Next.js on your computer, usually port 3000. The legacy dashboard is also available. | The same Next.js application on Vercel. Users can submit questions, monitor progress, and explore reports, papers, and graphs. |
| Backend | One Python process started with `graphiv-serve`; use the `both` role for research and report access. | The same Python application in one Azure Container Apps replica, exposing HTTP and MCP. |
| Corpus | Defaults to your existing PostgreSQL/pgvector database and local GraphExport file. A checkout does not include a populated corpus. | The full published `GraphIV-2026-10-01` release, read through the Azure snapshot adapter. No production PostgreSQL database is required. |
| Data storage | PostgreSQL by default; local SQLite/FAISS snapshots are also supported. | Immutable SQLite metadata, FAISS index, and citation graph published in Azure Blob Storage and loaded into a persistent Azure Files cache. |
| Vector retrieval | PostgreSQL/pgvector with the default adapter; FAISS when using a local snapshot. | Compressed FAISS IVF/SQ8 selects candidates; final cosine scores are recomputed from the original stored vectors. |
| Query embeddings | Defaults to a local endpoint serving `nomic-embed-text-v2-moe`. The native Nomic encoder is also supported. | Pinned native Nomic encoder on the API's CPU: `nomic-embed-text-v2-moe`, 768 dimensions, with the `search_query: ` prefix. |
| Research/report LLM | Defaults to `Gemma-4-26B-Batched` at a local OpenAI-compatible endpoint; configurable. | `google/gemini-3.1-flash-lite` through Vercel AI Gateway. |
| Completed reports | Saved under `data/runs` by default. | Saved as versioned Azure Blob objects, with checksums and a final commit marker. Reports survive API restarts. |
| Credentials | Loopback development can run without an API token. Configured external services may require credentials. | The Next.js server holds the backend bearer token; Azure managed identity accesses storage and Key Vault. Tokens are not exposed to the browser. |
| Resources | Limited by your machine; no local full-corpus memory minimum was established in this validation. | One backend with 4 CPU / 8 GiB RAM and a 100 GiB persistent file-cache share. Disk capacity and RAM are separate limits. |

Corpus storage, report storage, and model endpoints are configurable independently.
For example, a local process can read the same SQLite/FAISS snapshot as Azure, and
PostgreSQL remains supported by the backend. These are configuration choices, not
separate implementations of BoundedField or LeyLine.

## What stays the same

- **BoundedField** performs vector retrieval, citation-graph expansion, and
  graph-aware ranking using the existing recipes and scoring formulas.
- **LeyLine** uses existing citation-intent labels and confidence scores to find
  magnets, lineages, and successors. Published completed labels are imported with
  `stage = 1`; citation occurrences, including repeated pairs, are preserved.
- **Research orchestration** uses the existing Python API through Next.js.
- **Job state** is held in memory. One job runs at a time, with up to four
  queued/running jobs. Restarting loses job status and in-progress work;
  completed reports remain in the configured store.

Matching algorithms does not guarantee identical reports: the configured corpus,
retrieval candidates, LLM, and generated output can differ. A local setup using the
same published snapshot still needs a compatible Nomic query encoder. **OpenAI
`text-embedding-3-small` cannot query these Nomic vectors.**

## Data and evidence differences

The deployed snapshot contains **3,165,827 papers**, **74,764,672 citation
occurrences**, **38,931,148 distinct citation pairs**, and the published topic
hierarchy and names. It was built directly from Parquet without the original
PostgreSQL database.

The published release **does not include citation sentences**. This limitation
applies to cloud and local runs using that release:

- Intent labels and confidence remain available as precomputed predictions.
- Citation quotations and sentence-based dispute analysis are unavailable.
- Reports use available abstracts and source material. Citation paths show
  connectivity rather than proving influence.
- No JIT extraction or new intent classification is performed.

An independently built local PostgreSQL corpus may contain citation sentences.
Running locally alone does not restore those missing sentences.

## Why cloud uses a compressed index

A full `IndexFlatIP` would need about **9.06 GiB for its vectors alone**, exceeding
the deployed backend's 8 GiB limit before loading the query model and graph.
The published compressed index is **2.29 GiB on disk**; that file size is not the
total runtime memory requirement.

Against exact search over the full corpus, 13 validation queries achieved
**99.5% minimum recall@200** and **99.923% mean recall@200**. Returned cosine scores
matched the original-vector baseline with zero measured error. Candidate retrieval
remains approximate; rescoring cannot recover missed candidates. See the
[quality receipt](quality-receipt.json). The same snapshot can be used locally.

## What was actually verified

Both cloud cases used **Survey / Standard**, the full published corpus, and real
model services. No example reports or mocked corpus were used.

| Cloud case | Retained / exported papers | Citation occurrences mined | Lineages / successors found | Processing time | Peak container memory |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Linear attention and selective SSMs](https://graphiv.vercel.app/runs/2026-11-02-how-do-linear-attention-mechanisms-and-selective) | 40 / 121 | 23,094 | 491 / 413 | 6m 17s | 6.010 GiB |
| [RAG grounding and citation faithfulness](https://graphiv.vercel.app/runs/2026-11-02-what-methods-improve-evidence-grounding-and-cita) | 40 / 121 | 25,233 | 493 / 1,036 | 7m 41s | 5.668 GiB |

The retrieval pools contained 14,926 and 9,824 papers. Each report displays five
selected lineages and 25 follow-up papers. Peak process memory was about 5.09 GiB
per run; container measurements include filesystem cache. No OOM kills were recorded.

These were warm-runtime measurements. The second job waited **6m 7s** in the queue,
making submission-to-completion **13m 49s**. Revision warmup took **13m 4s with
populated caches**; empty-cache startup was not validly measured. A historical-date
retrieval benchmark took **4m 39s**. These are not response-time guarantees.

Review checked all 28 and 39 cited abstracts. The first report received two
documented precision corrections; the second required none. Timings exclude review
and republication. Source review is not a formal proof of every scientific claim.

Local Python and frontend checks verified implementation behavior. **This folder
does not contain a matching local full-corpus end-to-end benchmark**, so it does
not establish a cloud-versus-local speed, memory, or report-quality comparison.

## Running the interface locally

Configure a real corpus, matching embeddings, and an LLM first. The checked-in
[runtime configuration](../../../configs/runtime.toml) defaults to local PostgreSQL
and local model endpoints. To use the published snapshot instead, select the
`sqlite` backend and configure its metadata, index, and graph paths; see
[storage configuration](../../storage.md) and the
[snapshot builder](../../../offline/index_build/README.md).

From the repository root, start the backend:

```sh
uv run graphiv-serve --http --role both --port 8000
```

In another terminal, start Next.js with an explicit connection to that listener:

```sh
cd apps/web
npm install
GRAPHIV_API_URL=http://127.0.0.1:8000 npm run dev
```

Open `http://127.0.0.1:3000`. If authentication is enabled, also configure the
matching server-only `GRAPHIV_API_TOKEN`. An explicit backend URL surfaces connection
errors; it does not substitute example reports. Local launch commands alone do not
download the corpus or make research ready.

## Reading this validation folder

| Record | What it establishes |
| --- | --- |
| [Final acceptance summary](final-acceptance/acceptance-summary.json) | Entry point for the accepted deployment and linked receipt hashes. |
| [Research readiness](final-acceptance/readiness.json) | Loaded snapshot, corpus counts, embedding identity, and available capabilities. |
| [Research and Blob verification](final-acceptance/verification.md) | Actual jobs, paper counts, timings, memory, corpus checks, and persisted report hashes. |
| [Browser verification](final-acceptance/browser-verification.json) | Real form submissions, progress recovery, completed reports, paper inspection, and graph access. |
| [Content review](final-acceptance/content-review.json) | Reviewed sources, corrections, and evidence limitations. |
| [Full rollout record](../../published-corpus-validation.md) | Detailed build, deployment, quality, debugging, and acceptance history. |

`initial-slow-attempts/` and `v4-structural-validation/` retain superseded attempts
and diagnostic results. Use **`final-acceptance/`** for the completed product's
accepted results; earlier partial passes are not additional successful runs.
