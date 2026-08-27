# GraphIV — a grounded literature-review engine over all of arXiv

**GraphIV** (graph + ar**Xiv** — the _IV_ is arXiv's tail) builds a knowledge graph over the entire
arXiv corpus — metadata, a **177M-edge citation graph** with classified intent, and **3.10M** dense
embeddings — and serves it as a research endpoint that turns a question into a **grounded, cited,
chronological literature review** (Markdown + LaTeX, with an optional figure gallery).

Novelty:

- **Local and verifiable** — runs on one consumer GPU against a self-contained Postgres+pgvector
  store; every citation is an `arXiv:<id>` checked against the corpus, not a web-search snippet.
- **Stock models only** — nothing here is fine-tuned. The embedder is the official
  nomic-embed-text-v2-moe GGUF and every LLM role is an off-the-shelf open model behind an
  OpenAI-compatible endpoint. We did try a domain fine-tune and it failed (lineage recall rose,
  litmus pool-hit collapsed from 1.0 to 0.19), which is the point: the results come from the
  graph and the retrieval recipe, not from weights you would have to reproduce.
- **Up to date** — a judge-driven deep loop surfaces the newest work (9 verified 2026 papers per
  report on our panel, where a strong single-pass baseline surfaces none).
- **Fast** — a full deep report (effort 4: 3 judge rounds, 200 landmarks, PDF critiques, 14 verified
  figures, ~30k chars) takes **under 9 minutes cold-cache on a single RTX 3090**.
- **Checked, not asserted** — seven in ten cited sentences are verified as supported by the
  paper they cite, scored by a checker first shown able to reject: it passes 15-20% of citations
  broken on purpose against 71-74% of real ones.
- **Measured** — a four-bucket `experiments/` suite justifies every design choice with a metric
  vector, including the negative results.

It is organized as one importable library (`graphiv/`) driven by single-purpose entrypoints
(`scripts/`): the build stages construct the graph, and the research stage serves it.

```
question ──▶ retrieve (vector + lexical + topic-tree + citation subgraph + frontier pull)
         ──▶ rank (survey or frontier mode, decided from the question)
         ──▶ extract (per-paper schema fields from full text)
         ──▶ compose (chronological, grounded, cited review)  ──▶ report.md + report.tex (+ figures)
```

## The pipeline (`scripts/`)

| stage | does one thing |
| --- | --- |
| `seed.py` | refresh the arXiv metadata JSONL from the Kaggle snapshot |
| `download_pdf.py` | PDF acquisition (GCS → vault, `aria2c`) |
| `download_html.py` | HTML acquisition (arxiv.org LaTeXML, ar5iv fallback) |
| `citations.py` | citation graph: resolve each reference to an arXiv id, then classify **intent** (background/uses/extends/compares/critiques/motivates) and polarity via a Gemma teacher → DistilBERT student over the full corpus |
| `consolidate.py` | graph store: metadata + 177M citations + 3.10M nomic embeddings (HNSW) into one Postgres+pgvector DB |
| `topics.py` | semantic index: density-aware topic tree (3,582 leaves / 2.92M papers) |
| `research.py` | **the research endpoint**: question → grounded literature review (md + tex) |
| `serve.py` | the MCP server and the Research Library dashboard |

Every stage shares one contract (`--dry-run` first, idempotent, config-driven); `config.toml`
is the single place every parameter and toggle lives. See [`docs/`](docs/) for design notes and
[`scripts/README.md`](scripts/README.md) for the flag grammar.

## The library (`graphiv/`)

```
core/  config, store, embedding, LLM, the shared data contracts
download/ preprocess/   build the graph
retrieve/ generate/     answer a question against it
serve/                  MCP tools and the dashboard
```

Imports only ever point down that list, which `import-linter` enforces as a layers contract.
Each subpackage carries its own README.

## The research endpoint

```bash
# effort is a single 0-5 master dial (0 instant … 5 exhaustive; 3+ = judge-driven deep loop)
uv run python scripts/research.py "diffusion models for molecular generation" --set-effort 4
uv run python scripts/research.py "<question>" --dry-run        # read-only plan
```

Retrieval fuses a vector pool, lexical signals, a topic-tree anchor, an induced citation subgraph, and
a leaf-independent recent-paper pull. Ranking runs in one of two modes, decided from the question at
refinement time: **survey** answers with the lineage a field is built on, **frontier** answers with
what is being done now and reserves slots for recent work. Both spend eight slots on LeyLine. The
deep loop (effort ≥ 3) adds judge-driven gap expansion, per-paper full-PDF critique, sectioned
long-form compose, and a caption-faithfulness-checked figure gallery. Output is a grounded review
(md + tex/bibtex) with every claim cited as `arXiv:<id>` — and **every cited id verified against the
corpus by construction**: typo'd ids are fuzzy-corrected to the retrieved pool, sections citing
invalid ids get one repair pass, and fabricated survivors are stripped, so a report cannot cite a
nonexistent paper. Full text (PDF/HTML) is fetched per-paper on demand when not stored locally.

## The evidence (`experiments/`)

Every lever is measured, never asserted — each experiment reports a **metric vector** (any single
number is gameable). Four buckets; full index + per-experiment write-ups (md/tex/pdf) in
[`experiments/README.md`](experiments/README.md):

- **`01-preprocessing`** — resolver quality, label quality, graph structure, clustering, topic tree.
- **`02-retrieval`** — benchmarked against LitSearch, then pool construction, signal quality, the
  fusion rule, the selection objective, LeyLine and frontier reach, all on a 60-survey qrels
  benchmark. The finding that carries: what enters the pool decides the outcome, not how it is
  ranked (a 96-paper spread against 18 for the combining rule).
- **`03-generation`** — does the writer make things up. One metric throughout: whether a sentence
  is backed by a paper. Two thirds of cited sentences check out (two judge families agree on 89%
  of them, kappa 0.762); the checker rejects 80-85% of citations broken on purpose; 60% of sentences
  carry a citation at all; and the citation graph in the prompt does **not** improve any of it.
- **`deep-research`** — the flagship before/after: the deployed pipeline wins the pairwise **8/0/0 on
  overall and grounding** (n=8, confirmed by two disjoint-family judges), surfacing 9 verified 2026
  papers/topic where the baseline finds none.

## Reproduce

```bash
nix develop          # dev shell (Python 3.13, CUDA, ruff/black/pyright, TeX)
uv sync              # install deps
nix run .#pg-start   # launch the project-local Postgres+pgvector

uv run python scripts/seed.py --dry-run   # every stage: --dry-run first
# … the build stages construct the store from the metadata dump + nomic embeddings (see docs/) …
uv run python scripts/research.py "your question here" --set-effort 4
```

To **restore the prebuilt store** instead of building it (a ~17 GB `pg_dump`, download link pending),
and to point the LLM layer at any OpenAI-compatible endpoint, see [`docs/restore.md`](docs/restore.md).
The large stores (PDFs, HTML, the Postgres datadir, embeddings) are **not committed**; the served path
is fully under `./data`, target footprint < 100 GB.

Five gates, all clean:

```bash
uv run ruff check graphiv scripts experiments tests
uv run black --check graphiv scripts experiments tests
uv run pyright graphiv scripts
uv run lint-imports
uv run pytest tests -q
```

## License

[GNU General Public License v3.0](LICENSE) — copyleft: derivatives must stay open under the GPL.
