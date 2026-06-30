# arxivkg — a grounded literature-review engine over all of arXiv

**arxivkg** builds a knowledge graph over the entire arXiv corpus — metadata, a **173M-edge citation
graph** with classified intent, and **3.07M** dense embeddings — and serves it as a research endpoint
that turns a question into a **grounded, cited, chronological literature review** (Markdown + LaTeX,
with an optional figure gallery).

It is organized as a uniform **`phases/` pipeline** (phases 1–5 build the graph; **phase 6 is the live
research endpoint**) on a single self-contained **Postgres + pgvector** store, plus a measured
**`experiments/` suite** that justifies every design choice.

```
question ──▶ retrieve (vector + lexical + topic-tree + citation subgraph + frontier pull)
         ──▶ rank (Personalized PageRank + topic-adaptive recency)
         ──▶ extract (per-paper schema fields from full text)
         ──▶ compose (chronological, grounded, cited review)  ──▶ report.md + report.tex (+ figures)
```

## The pipeline (`phases/`)

| phase | does one thing |
|---|---|
| **1** | PDF acquisition (GCS → vault, `aria2c`) |
| **2** | HTML acquisition (ar5iv) |
| **3** | Citation graph: parse → match each citation to an arXiv id + context; classify **intent** (background/uses/extends/compares/critiques/motivates) and polarity via a Gemma teacher → DistilBERT student over the full corpus |
| **4** | Graph store: consolidate metadata + 173M citations + 3.07M nomic embeddings (HNSW) into one Postgres+pgvector DB |
| **5** | Semantic index: density-aware topic tree (3,582 leaves / 2.92M papers) |
| **6** | **Research endpoint**: question → grounded literature review (md + tex), topic-adaptive recency, a judge-driven deep loop with full-PDF critique, and a vision figure gallery |

Every phase has the same `run.py` contract (`--dry-run` first, idempotent, config-driven); each
phase's `config.json` is the single place its parameters + component toggles live. See
[`docs/`](docs/) for design notes.

## The research endpoint (phase 6)

```bash
# effort is a single 0-5 master dial (0 instant … 5 exhaustive; 3+ = judge-driven deep loop)
uv run python phases/phase-6/run.py "diffusion models for molecular generation" --set-effort 4
uv run python phases/phase-6/run.py "<question>" --dry-run        # read-only plan
```

Retrieval fuses a vector pool, lexical signals, a topic-tree anchor, an induced citation subgraph, and
a leaf-independent recent-paper pull; ranking is Personalized PageRank with topic-adaptive recency. The
deep loop (effort ≥ 3) adds judge-driven gap expansion, per-paper full-PDF critique, sectioned
long-form compose, and a caption-faithfulness-checked figure gallery. Output is a grounded review with
every claim cited as `arXiv:<id>` (hallucinated ids are stripped post-hoc).

## The evidence (`experiments/`)

Every lever is measured, never asserted — each experiment reports a **metric vector** (any single
number is gameable). Four buckets; full index + per-experiment write-ups (md/tex/pdf) in
[`experiments/README.md`](experiments/README.md):

- **`01-preprocessing`** — resolver quality, label quality, graph structure, clustering, topic tree.
- **`02-retrieval`** — the subgraph recipe, off-topic-noise role judge, the 0.35 ancestor gate, selection flags.
- **`03-generation`** — judge validity, component ablation, embedding format, recency, frontier-pull,
  landmark selection, graph representation, the deep loop, critique depth, vision figures, and
  **hub-suppression** (keeping generic hubs like *Attention* from hijacking niche reviews).
- **`deep-research`** — the flagship before/after: the deployed pipeline is preferred **23/4/0** overall.

## Reproduce

```bash
nix develop          # dev shell (Python 3.13, CUDA, ruff/black/pyright, TeX)
uv sync              # install deps
nix run .#pg-start   # launch the project-local Postgres+pgvector

uv run python phases/phase-1/run.py --dry-run   # every phase: --dry-run first
# … phases 1-5 build the store from the arXiv metadata dump + nomic embeddings (see docs/) …
uv run python phases/phase-6/run.py "your question here" --set-effort 4
```

The large stores (PDFs, HTML, the Postgres datadir, embeddings) live on external mounts and are
**not committed**; `docs/` documents how to build or download them (the served path is fully under
`./data`, target footprint < 100 GB). Lint gate: `ruff check phases/ experiments/ ; black … ; pyright …`
— all clean.

## License

[GNU General Public License v3.0](LICENSE) — copyleft: derivatives must stay open under the GPL.
