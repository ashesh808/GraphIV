# Published corpus rollout and validation

Status as of 2026-11-01: **implementation deployed; full-corpus acceptance blocked by dataset authorization**. GraphIV is not yet research-ready. No demonstration reports, empty corpora, or mocked research runs count as validation.

## Source and access

The requested [GraphIV release](https://huggingface.co/datasets/kkuroma/GraphIV/tree/GraphIV-2026-10-01) resolves to commit `cc781313c13b9cbd08110c97eb84b7e1a62180e1`. Its published inventory contains 7 paper, 4 citation, and 1 topic Parquet shards, totaling 6,486,435,579 bytes. The dataset card reports 3,165,827 papers, 74,764,672 citation occurrences, and 3,165,827 topic rows. These are **source inventory counts**, not successful import measurements.

A request for the actual pinned `papers/papers-00000.parquet` returned HTTP 401 with `X-Error-Code: GatedRepo`. The local Hugging Face token lookup is empty. A read token from an account granted dataset access is required before the full source can be downloaded. Use a Key Vault secret reference or local `hf auth login`; credentials do not belong in source, Terraform variables, or this document.

## Implemented behavior

- The offline worker downloads immutable Parquet shards, verifies their source sizes/checksums, and reads bounded Arrow batches directly. It preserves original float16 vectors and every citation occurrence. Published non-null intent labels become completed runtime labels (`stage = 1`); original confidence scores remain attached.
- Topic hierarchy IDs and names populate the existing runtime tables. The graph export contains distinct resolved paper pairs, while occurrence-level intent records remain in SQLite.
- BoundedField and LeyLine algorithms, recipes, and scoring formulas are unchanged. Their adapters support both PostgreSQL and the immutable Blob-backed SQLite corpus. Original successor confidence filtering is retained; confidence values are also exposed in saved graph and lineage edge records.
- The API uses pinned official `nomic-ai/nomic-embed-text-v2-moe` CPU weights, 768 dimensions, mean pooling, normalization, maximum 512 tokens, and the original `search_query: ` prefix. There is no alternate embedding-provider fallback for this configuration. Gemini 3.1 Flash Lite remains the report/research LLM through Vercel AI Gateway.
- Citation sentences are unavailable. Reports disclose that labels are precomputed model predictions; citation quotations and sentence-based disputes are omitted. No JIT extraction or intent classification is performed.
- The Next.js frontend submits questions to the existing API, polls job stages, resumes status within the browser tab, opens persisted reports, and retains paper/citation-graph exploration. Its structured reader and exports include the evidence limitation.

## Memory and storage

The full original FlatIP payload would require 9,725,420,544 bytes (9.06 GiB), exceeding the 8 GiB Consumption limit before the encoder or graph loads. The replacement is an IVF/SQ8 candidate index with 1,024 lists, initial `nprobe = 128`, and fourfold candidate oversampling. Its estimated vector-code/ID payload is 2,456,681,752 bytes (2.29 GiB), plus centroids and bookkeeping. Final similarity scores are recalculated using the original float16 vectors in SQLite; approximation affects candidate recall, not the cosine formula.

The existing API is configured for 4 CPU / 8 GiB. A 100 GiB Azure Files cache in the existing storage account is mounted using managed identity because the source, metadata, vectors, and model exceed Consumption ephemeral storage. The optional offline build job uses the same cache and has no idle replicas. Azure Blob Storage remains the publication/report store and the single Python backend remains the research service.

Full-corpus peak memory, recall, and latency are **unmeasured** until the gated source is available. Startup integrity scans and very selective historical filters can cause substantial disk I/O. The actual quality gate must pass before activation; publishing a built snapshot alone does not change the active manifest.

## Measurements obtained

| Check | Observed result |
| --- | --- |
| Azure Files read/write | Passed; mounted capacity 107,374,182,400 bytes |
| Official Nomic weights downloaded to persistent cache | Passed; immutable revision `1066b6599d099fbb93dfcb64f9c37a7c9e503e85` |
| Real Nomic CPU forward pass on Azure | Passed; 768 dimensions, vector norm 1.000000052 |
| First download + load + one query | 59.63 seconds |
| Encoder probe peak process RSS | 1,990,705,152 bytes; separate probe process, not a research-job measurement |
| Published Parquet access | Blocked: HTTP 401 `GatedRepo` |
| Full corpus import and activation | Not executed |
| Full corpus ANN recall / document-vector compatibility | Not executed |

The model probe verifies the encoder itself; it does not prove compatibility with the inaccessible published vectors or full deployment memory capacity.

## Required real research acceptance

| Research question | Papers / citations / lineages / successors | Latency / peak memory | Result |
| --- | --- | --- | --- |
| Linear attention versus selective state-space models, including their research lineages | Unmeasured | Unmeasured | Pending corpus access |
| Evidence grounding and citation faithfulness in retrieval-augmented generation, including follow-up papers | Unmeasured | Unmeasured | Pending corpus access |

After authorization:

1. Run the cloud Parquet build and publish an inactive snapshot. Inspect its exact source/import counts, intent/confidence counts, source hashes, elapsed time, and peak RSS.
2. Run `offline.index_build.benchmark` on the complete snapshot using `offline/index_build/validation_queries.jsonl`. Require at least 98% recall@200 for every supplied query, exact cosine agreement, and at least 0.999 cosine between 16 original published vectors and the original document encoder. Inspect actual full-corpus memory and latency. If settings change, rerun against the final saved index configuration.
3. Explicitly activate the verified snapshot, restart the API, and require research readiness with the pinned full corpus and Nomic identity.
4. Run `offline.index_build.verify_deployment --verify-blob` for both real questions. The command rejects incomplete provenance, empty results, absent lineages/successors, missing measurements, missing report artifacts, fabricated citation sentences, and paper metadata that disagrees with the deployed corpus. It independently SHA-checks persisted Blob payloads when requested.
5. Submit real questions from [graphiv.vercel.app](https://graphiv.vercel.app), observe progress, open completed reports, and inspect their papers and citation graph. Record browser verification separately; an HTTP script does not establish browser interaction.

The offline package [README](../offline/index_build/README.md) contains build, quality, publication, and acceptance commands. Replace this pending status with actual receipts after those steps succeed.
