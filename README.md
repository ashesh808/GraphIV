# GraphIV — a grounded literature-review engine over all of arXiv

**GraphIV** (graph + ar**Xiv** — the _IV_ is arXiv's tail) builds a knowledge graph over the entire
arXiv corpus — metadata, a **173M-edge citation graph** with classified intent, and **3.07M** dense
embeddings — and serves it as a research endpoint that turns a question into a **grounded, cited,
chronological literature review** (Markdown + LaTeX, with an optional figure gallery).

Novelty:

- **Local and verifiable** — runs on one consumer GPU against a self-contained Postgres+pgvector
  store; every citation is an `arXiv:<id>` checked against the corpus, not a web-search snippet.
- **Up to date** — a judge-driven deep loop surfaces the newest work (9 verified 2026 papers per
  report on our panel, where a strong single-pass baseline surfaces none).
- **Fast** — a full deep report (effort 4: 3 judge rounds, 200 landmarks, PDF critiques, 14 verified
  figures, ~30k chars) takes **under 9 minutes cold-cache on a single RTX 3090**.
- **Measured** — a four-bucket `experiments/` suite justifies every design choice with a metric
  vector, including the negative results.

It is organized as one importable library (`graphiv/`) driven by single-purpose entrypoints
(`scripts/`): the build stages construct the graph, and the research stage serves it.

```
question ──▶ retrieve (vector + lexical + topic-tree + citation subgraph + frontier pull)
         ──▶ rank (Personalized PageRank + topic-adaptive recency)
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
| `consolidate.py` | graph store: metadata + 173M citations + 3.07M nomic embeddings (HNSW) into one Postgres+pgvector DB |
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
a leaf-independent recent-paper pull; ranking is Personalized PageRank with topic-adaptive recency. The
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
- **`02-retrieval`** — the subgraph recipe, off-topic-noise role judge, the 0.35 ancestor gate
  (sensitivity-swept: a recall plateau, now the shipped default), selection flags.
- **`03-generation`** — judge validity, component ablation, embedding format, recency, frontier-pull,
  landmark selection, graph representation, the deep loop, critique depth, vision figures, and
  **hub-suppression** (keeping generic hubs like _Attention_ from hijacking niche reviews).
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
is fully under `./data`, target footprint < 100 GB. Lint gate:
`ruff check graphiv/ scripts/ ; black … ; pyright … ; lint-imports` — all clean.

## License

[GNU General Public License v3.0](LICENSE) — copyleft: derivatives must stay open under the GPL.
