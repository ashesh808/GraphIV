# Published corpus rollout and validation

Status as of 2026-11-02 19:34 UTC: **full corpus active; both v4 research jobs passed data, lineage, memory and Blob-integrity checks; report-prose acceptance remains pending**. Independent review found unsupported comparative claims caused by truncated abstracts and overly prescriptive composition prompts. The v5 writer now uses full abstracts and source-excerpt checks and is warming the same corpus. Two fresh v5 browser runs and final narrative review are required. No demonstration reports, empty datasets or mocked services count as acceptance.

## Source and access

The requested [GraphIV release](https://huggingface.co/datasets/kkuroma/GraphIV/tree/GraphIV-2026-10-01) resolves to commit `cc781313c13b9cbd08110c97eb84b7e1a62180e1`. Its published inventory contains 7 paper, 4 citation, and 1 topic Parquet shards, totaling 6,486,435,579 bytes. Authenticated reads of all 12 actual Parquet footers confirm 3,165,827 papers, 74,764,672 citation occurrences, and 3,165,827 topic rows. The bounded footer audit read only 1,841,027 bytes locally; the full source was downloaded and imported on Azure. The [footer audit](validation/2026-11-02/published-parquet-footers.json), [column statistics](validation/2026-11-02/published-parquet-statistics.json), and [published manifest](validation/2026-11-02/published-corpus-manifest.json) retain the source and import evidence separately.

Dataset access was restored on 2026-11-02 after local Hugging Face login. The pinned paper shard returned HTTP 200. The existing offline worker receives the read credential through a secret-scoped Key Vault reference; no credential value is stored in Terraform state or source. All 6,486,435,579 source bytes downloaded and passed their published checksums and actual Arrow-schema/count validation on Azure.

The first build stopped at database initialization because POSIX advisory locking on this Azure Files mount returned `database is locked`. A direct mount check confirmed that SQLite's `unix-dotfile` writer locking works. Private staging writers now use that supported locking mechanism; completed snapshots open read-only with `immutable=1`. Snapshots remain content-verified and are never changed underneath readers. This uses the existing filesystem and backend, without an infrastructure change. See [SQLite locking backends](https://www.sqlite.org/vfs.html) and [immutable read semantics](https://www.sqlite.org/uri.html).

The completed snapshot `graphiv-2026-10-01-nomic-sq8` records these actual import measurements:

| Imported data | Recorded count |
| --- | ---: |
| Papers and embedded vectors | 3,165,827 each |
| Citation occurrences | 74,764,672 |
| Rows with precomputed intent labels | 74,764,672 |
| Rows with original confidence scores | 74,764,672 |
| Published citation sentences | 0 |
| Unresolved citation targets | 0 |
| Distinct resolved graph pairs | 38,931,148 |
| Topic rows / topic names | 3,165,827 / 4,368 |

Occurrence counts and distinct graph-pair counts describe different representations. The importer preserves every occurrence in SQLite while deduplicating pairs for GraphExport. These counts come from the completed manifest, not from a small fixture or a source-only estimate.

The successful offline execution completed import and inactive publication in 5,589.898 seconds (93 minutes 10 seconds), reporting peak process RSS of 3,960,127,488 bytes (3.69 GiB). The [build receipt](validation/2026-11-02/build-receipt.json) and [monitor observations](validation/2026-11-02/build-monitor.jsonl) retain the actual completion event and sampled Azure metrics. The maximum of those recorded container-memory samples was 7,360,626,688 bytes; samples do not establish the execution's absolute memory peak.

## Implemented behavior

- The offline worker downloads immutable Parquet shards, verifies their source sizes/checksums, and reads bounded Arrow batches directly. It preserves original float16 vectors and every citation occurrence. Published non-null intent labels become completed runtime labels (`stage = 1`); original confidence scores remain attached.
- Topic hierarchy IDs and names populate the existing runtime tables. The graph export contains distinct resolved paper pairs, while occurrence-level intent records remain in SQLite.
- BoundedField and LeyLine algorithms, recipes, and scoring formulas are unchanged. Their adapters support both PostgreSQL and the immutable Blob-backed SQLite corpus. Original successor confidence filtering is retained; confidence values are also exposed in saved graph and lineage edge records.
- The API uses pinned official `nomic-ai/nomic-embed-text-v2-moe` CPU weights, 768 dimensions, mean pooling, normalization, maximum 512 tokens, and the original `search_query: ` prefix. There is no alternate embedding-provider fallback for this configuration. Gemini 3.1 Flash Lite remains the report/research LLM through Vercel AI Gateway.
- Citation sentences are unavailable. Reports disclose that labels are precomputed model predictions; citation quotations and sentence-based disputes are omitted. No JIT extraction or intent classification is performed.
- The Next.js frontend submits questions to the existing API, polls job stages, resumes status within the browser tab, opens persisted reports, and retains paper/citation-graph exploration. Its structured reader and exports include the evidence limitation.

## Memory and storage

The full original FlatIP payload would require 9,725,420,544 bytes (9.06 GiB), exceeding the 8 GiB Consumption limit before the encoder or graph loads. The built IVF/SQ8 candidate index has 1,024 lists, `nprobe = 128`, fourfold candidate oversampling, and 65,536 training vectors. Its actual file size is 2,459,842,000 bytes (2.29 GiB). Final similarity scores are recalculated using the original float16 vectors in SQLite; approximation affects candidate recall, not the cosine formula. Recorded training and index-add times were 498.881 and 318.034 seconds respectively; these are index stages, not total build or research-job latency.

| Published artifact | Actual bytes |
| --- | ---: |
| `metadata.sqlite` | 21,999,063,040 |
| `index.faiss` | 2,459,842,000 |
| `graph.npz` | 263,982,055 |

The current API image is `graphiv-api:published-corpus-v5`, digest `sha256:4e785ecdc36e33161afccc422ca54dfbe4284d56c1f831f7e13fb77f3bda336f`, deployed as revision `0000007` around 19:33 UTC on 2026-11-02. The offline image remains `graphiv-index-builder:published-corpus-v3`, in the same existing Azure registry. The existing API is configured for 4 CPU / 8 GiB. A 100 GiB Azure Files cache in the existing storage account is mounted using managed identity because the source, metadata, vectors, and model exceed Consumption ephemeral storage. The optional offline build job uses the same cache and has no idle replicas. Azure Blob Storage remains the publication/report store and the single Python backend remains the research service.

The full-corpus quality run passed inside the actual cgroup v1 8,589,934,592-byte limit. Peak process RSS after document checks was 4,507,381,760 bytes (4.20 GiB); the cgroup's recorded peak was 7,485,149,184 bytes (6.97 GiB), including filesystem cache. Sampled anonymous and file-cache peaks were 3,289,214,976 and 5,421,195,264 bytes; they occurred independently and must not be added as simultaneous usage. The observed `oom_kill` and `failcnt` deltas were zero. Cgroup v2-only counters were unavailable, not measured as zero. These are quality-run measurements, not peak memory for a completed research job. Raw v1 paths, values, and parsed telemetry are retained in the [quality receipt](validation/2026-11-02/quality-receipt.json).

## Full-corpus quality gate

The [recorded quality run](validation/2026-11-02/quality-status.json) finished successfully on 2026-11-02. It compared ANN candidates against an exact baseline over the original corpus vectors using [13 real query cases](validation/2026-11-02/quality-queries.jsonl), including historical-date and blocked-ID filters. The required minimum recall@200 was 0.98 for every query. The complete [receipt](validation/2026-11-02/quality-receipt.json) records the following results:

| `nprobe` | Minimum recall@200 | Mean recall@200 | Maximum absolute cosine-score error | Result |
| ---: | ---: | ---: | ---: | --- |
| **128, activated configuration** | **0.995** | **0.9992307692** | **0.0** | Passed |
| 256 | 0.995 | 0.9996153846 | 0.0 | Passed |
| 512 | 1.0 | 1.0 | 0.0 | Passed |

At `nprobe = 128`, individual retrieval calls ranged from 4.6738 to 278.9837 seconds; the median was 10.2086 seconds. The `graph-learning-before-2017` case, capped at 2016-12-31, took **278.9837 seconds**, despite passing recall. This selective historical filter is a demonstrated latency limitation. These numbers describe the retrieval benchmark calls, not complete research requests or a general response-time guarantee.

The same run re-encoded 16 sampled published documents with the pinned original Nomic encoder and `search_document: Title: <title>\nAbstract: <abstract>` formatting, then compared them to their stored original vectors. Minimum cosine was **0.9994056364**, mean cosine was **0.9998808114**, exceeding the required 0.999 for all 16 samples. This establishes compatibility for the tested sample; it is not a re-encoding audit of every published document. The model revision, code revision, sample IDs, and individual cosines are retained in `document_space` in the receipt.

The quality run took 2,024.87 seconds, including the exact baseline and document checks. Cold-start latency has **not** been validly measured: the local monotonic interval overlapped Mac sleep and is excluded. No 120-second cold-start claim is supported.

## Activation

The snapshot was published inactive until the recorded quality gate passed. The [activation review](validation/2026-11-02/activation/review.json) records an explicit activation, all three artifact sizes/checksums, a completed active-alias write, and matching readback. The active `metadata/manifest.json` SHA-256 is `619c453798eab8335b0cd70fae3c915a73ed30e167efb2581b1be4bb67b644d4`, matching the reviewed [candidate manifest](validation/2026-11-02/activation/candidate-manifest.json). The reviewed quality-receipt SHA-256 is `7f5e8a693abb8fde10920e0200146530e0b5663f3ae30d6a3e203eace2c5d82f`, matching the adjacent [receipt copy](validation/2026-11-02/activation/quality-receipt.json).

The [rollback record](validation/2026-11-02/activation/rollback.json) states that no previous active alias existed. After activation, the v3 API reached research readiness with the pinned full corpus and Nomic identity. The v4 access-path correction and v5 report-grounding changes leave this corpus and manifest unchanged. V4 subsequently completed both real research jobs; v5 must regain research readiness and pass the final checks below.

## Initial research attempts and citation-access correction

The [initial browser submission record](validation/2026-11-02/initial-slow-attempts/browser-submissions.json) confirms two real Survey/Standard submissions through the visible Vercel form:

- Linear-attention/SSM job [`7b9e8fe3ddc0446883560cf0cc12f970`](validation/2026-11-02/initial-slow-attempts/7b9e8fe3ddc0446883560cf0cc12f970.json) was created at 18:06:49 UTC. It performed BoundedField retrieval and 13 actual LLM grading calls by 18:14:11 UTC, then remained in mining for more than 20 minutes before intervention. Its saved status was `running`, stage `mining`, with no result.
- RAG-grounding job [`d7017486257442b2b5f502724f54ab60`](validation/2026-11-02/initial-slow-attempts/d7017486257442b2b5f502724f54ab60.json) was created at 18:11:49 UTC and remained queued behind the first job, with no result.

The [read-only citation-access probe](validation/2026-11-02/citation-access-probe.json) against the full immutable SQLite corpus identified an induced-edge query access problem. SQLite selected the incoming `citations_target` index, causing large fanout for highly cited target papers even when both endpoints were restricted to a small set. The three-head default query was interrupted after **30.213 seconds** and returned no completed result or row count. A `citations_source` query over the expanded 33-node set completed in **1.708 seconds**, returning **461 labelled citation occurrences**, all without sentence text. The probe overlapped the initial research job; its timings describe citation access, not completed research latency, and the interrupted query is not a measured speedup baseline.

The source-only correction changes the SQLite adapter's `edges` and `edge_records` methods to select `INDEXED BY citations_source`. Explicit `ORDER BY target_id,intent,citation_id` preserves the original occurrence ordering. Twelve parity cases and 94 targeted tests passed. The successor query, original confidence filtering, BoundedField/LeyLine equations, recipes, and stored corpus artifacts were not changed. The fix was included in v4 and retained in v5. On the first completed v4 run, the observed mining stage finished in about82seconds; complete per-job measurements are in the structural receipts below.

Replacing the revision ended the old process-local jobs. The verifier, which reused those submitted IDs, [failed on HTTP 404](validation/2026-11-02/initial-slow-attempts/verifier/verification.json) after replacement; its [worker status](validation/2026-11-02/initial-slow-attempts/verifier/worker-status.json) finished at 18:35:30 UTC. The captured job records remain `running`/`queued` observations from before replacement, not successful or terminal reports. Both attempts are superseded and neither counts as completed acceptance. Their browser inputs and failed verifier receipts are retained for traceability. Final verification must use two fresh jobs on the corrected revision.

## Measurements obtained

| Check | Observed result |
| --- | --- |
| Azure Files read/write | Passed; mounted capacity 107,374,182,400 bytes |
| Official Nomic weights downloaded to persistent cache | Passed; immutable revision `1066b6599d099fbb93dfcb64f9c37a7c9e503e85` |
| Real Nomic CPU forward pass on Azure | Passed; 768 dimensions, vector norm 1.000000052 |
| Encoder-only first download + load + one query | 59.63 seconds; excludes corpus startup and research |
| Encoder probe peak process RSS | 1,990,705,152 bytes; separate probe process, not a research-job measurement |
| Persistent cache after API revision replacement | Passed; the original marker and model cache survived |
| Two warm Nomic query encodings | 1.171 and 0.699 seconds; encoder-only checks, not corpus retrieval |
| Native Torch + FAISS interoperability on deployed Linux | Passed; small library interoperability check, not corpus recall validation |
| Gateway LLM request from the deployed API | Passed; `google/gemini-3.1-flash-lite` |
| Published Parquet access | Passed with authorized Hugging Face login |
| Full source download + checksum/schema/count checks | Passed; 211.067 seconds, peak RSS 1,400,971,264 bytes |
| Full corpus import and activation | Passed; completed manifest and explicit activation/readback records linked above |
| Full corpus ANN recall / document-vector compatibility | Passed; 13 retrieval cases and 16 original-vector document checks |
| Citation-access diagnostic | Source-index query: 461 occurrences across 33 nodes in 1.708 seconds; default three-head query interrupted at 30.213 seconds |
| Initial real research attempts | Incomplete and superseded after revision replacement; verifier received HTTP 404 |
| V4 actual research-report latency / sampled peak memory | 482.389s /5.066GiB RSS /7.108GiB container;545.266s /5.078GiB RSS /5.847GiB container. Data checks passed; prose required correction. |
| Full cold-start latency | Not validly measured; local timing excluded because it overlapped Mac sleep |

Before corpus activation, a real production-browser submission reached the Azure API and displayed its research-not-ready response; it created no report. The initial preflight command likewise exited FAILED before submitting jobs because `/health/ready` returned 503. After activation, the two browser jobs described above were accepted but did not complete before revision replacement. Their incomplete attempts and failed verification are not successful report evidence. V4 then completed both canonical browser questions and passed the independent structural and Blob checks. Its generated prose was rejected during manual source review, so those passes do not complete the overall acceptance criteria.

Encoder-only probes, the full-corpus quality gate, and real research jobs are separate measurements. The document-vector and cgroup measurements above supersede the earlier lack of full-corpus evidence, while completed research-job measurements are still required.

## Report-source grounding correction

The [v4 structural receipts](validation/2026-11-02/v4-structural-validation/verification.json) verify both actual jobs against the complete corpus and independently read all persisted Blob payloads. The [manual review](validation/2026-11-02/v4-structural-validation/grounding-review.json) records why their prose was not accepted: a420-character abstract prefix hid proposed-method details, while composition instructions encouraged unsupported costs, limitations and methodological evolution. For example, In-Context RALM was incorrectly said to require architectural modifications, contrary to its full abstract.

V5 supplies complete original abstracts, removes those forced conclusions, and repairs generated sentences against cited original sources. Local checks require a verbatim supporting excerpt from each exact cited source; invalid replacements are dropped and the old draft is never a fallback. The model evaluates semantic support, so excerpt matching is not a formal proof of entailment. Internal abstract excerpts are not reconstructed citation sentences and are not rendered as citation quotations. Section headings use source metadata, and path descriptions explicitly qualify citation connectivity. BoundedField, LeyLine, the corpus and their scoring formulas remain unchanged.

The [real Gateway smoke](validation/2026-11-02/v5-source-grounding/gateway-smoke.json) corrected two observed contradictions and regenerated a full RAG section against complete original abstracts using the same Gemini3.1FlashLite model. Source-guard and integration tests passed;474selected Python tests passed overall. Final acceptance still requires the two fresh browser jobs and manual review of their actual output.

V5 also aligns the preparation and runtime snapshot-cache keys. The same full artifact checksums remain required, but an accidental duplicate24.7GB verification pass is removed. A regression reproduces two loads before the correction and one afterward. Cold-start improvement must be measured rather than assumed.

## Required real research acceptance

| Research question | Papers / citations / lineages / successors | Latency / peak memory | Result |
| --- | --- | --- | --- |
| Linear attention versus selective state-space models, including their research lineages | Pending fresh report verification | Pending fresh job measurements | Initial mining attempt superseded; fresh v5 job pending |
| Evidence grounding and citation faithfulness in retrieval-augmented generation, including follow-up papers | Pending fresh report verification | Pending fresh job measurements | Initial queued attempt superseded; fresh v5 job pending |

Remaining acceptance steps:

1. Require research readiness on v5, then submit and complete both distinct questions as fresh jobs from [graphiv.vercel.app](https://graphiv.vercel.app). Observe progress, open their completed reports, and inspect actual papers, authors, research lineages, follow-up papers, graph intent predictions/confidence, and the missing-citation-sentence qualification.
2. Validate those fresh jobs with `offline.index_build.verify_deployment --verify-blob`, reusing their new job IDs rather than submitting duplicates or using the superseded IDs. Require full source provenance, nonempty retrieval, mined/persisted lineages and successors, measured latency/memory, five saved report artifacts, no fabricated citation sentences, and paper metadata matching the deployed corpus. Independently verify persisted Blob payload hashes.
3. Record browser interaction separately from HTTP/artifact verification, and fill the pending table with the real counts, job measurements, report links, and receipts. Reload the library and reopen both saved reports to verify the reading path after completion.

The offline package [README](../offline/index_build/README.md) contains build, quality, publication, and acceptance commands. The existing activation and quality receipts establish only their respective checks; replace the pending research acceptance rows after the actual jobs and report checks succeed.
