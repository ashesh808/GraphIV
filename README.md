# GraphIV, a research endpoint over all of arXiv

**GraphIV** (graph + ar**Xiv**) builds a knowledge graph over the whole arXiv corpus, 3,164,437
papers with 3,128,573 embeddings and 182.6M citation occurrences of which 73.8M resolve to a paper
in the corpus and carry a classified intent, and serves it as a set of MCP tools an LLM agent
drives into a grounded, cited literature review.

It runs on one consumer GPU against a self-contained Postgres and pgvector store. Nothing here is
fine-tuned: the embedder is the official nomic-embed-text-v2-moe GGUF and every model role is a
stock open model behind an OpenAI-compatible endpoint. A domain fine-tune was tried and failed,
which is the point, since the results come from the graph and the recipe rather than from weights
anyone would have to reproduce.

## What it is for

A citation is not a link. Each of the 73.8M resolved ones carries why it was made, one of
background, uses, extends, compares, critiques or motivates, together with the sentence that made
it. That is what lets the system answer three things no ranking can answer on its own: which papers
a field argues with, the dated path that led to them, and which brand new papers have taken a
position on the answer without yet being cited by anyone.

```
a question ─▶ retrieve   cosine, one citation hop, a six-term graph score, then a reader
           ─▶ mine       the papers the field argues with, the paths, the disputes, the successors
           ─▶ read       the full text on disk, into a schema the caller invents
           ─▶ report     the document, with every arXiv id checked against the corpus
```

The loop belongs to the calling agent. The server holds the corpus, the tuned constants and the
rankings, and answers one call at a time.

## The library

```
src/core/      the contracts, the citation graph as CSR, the embedding and router clients
src/retrieve/  a question and a date cap into a ranked pool, with no model anywhere in it
src/miner/     a list of papers into what the field argues with and how it got there
src/report/    the document, its method table, and the guard every draft passes through
src/eval/      the four benchmarks that score a recipe
src/mcp/       the tool surface, one file per tool
src/webui/     the dashboard over past runs
```

Imports only ever point down that list, which `import-linter` enforces. Each subpackage carries its
own README. A recipe file under `retrieval_recipes/` names the components and every exponent, so
changing the score edits a toml and no code.

## The tools

| tool | what it answers |
| --- | --- |
| `refine` | what focused question this corpus can actually answer |
| `identify_areas` | which areas a question has to be searched as separately |
| `retrieve` | what one area currently is, graded by role, and an id for the ranking |
| `mine` | what it argues with, how it got here, and what has appeared since |
| `read_paper` | a paper's sections, or a schema the caller invented, filled from its full text |
| `write_report` | the document, written to disk and grounded |
| `what_cites` | who took a position on one paper, and the sentence they used |
| `search_papers` | plain cosine, to turn a title into an id |

```bash
uv run python scripts/serve.py          # stdio
uv run python scripts/serve.py --http   # streamable-http, and the dashboard, on 8756
```

## What is measured

The retriever is scored by four benchmarks that contain no language model anywhere, each case
selected from a review classifier and the topic tree, each answer key drawn from what later
documents actually cited.

| benchmark | one case is | recall@1000 |
| --- | --- | --- |
| SurveyMatch | one review against its own resolved references | 0.812 |
| FrontierMatch | what the later of two reviews added | 0.770 |
| ConsensusMatch | what three reviews on one topic all cite | 0.810 |

Two human reviews of one topic written within three months agree at recall 0.265 over 93 pairs, so
that number sits beside ours in every report and chasing recall far past 0.65 is chasing noise.

`experiments/` carries the per-recipe runs behind those, and `docs/decisions.md` records what was
tried and dropped, including the negative results.

## Reproduce

```bash
nix develop          # the dev shell: Python 3.13, CUDA, ruff, black, pyright
uv sync
nix run .#pg-start   # the project-local Postgres and pgvector

uv run python scripts/papers_preprocess/stage0_fetch_source_json.py --dry-run
# the build stages construct the store from the metadata dump and the embeddings, see docs/
uv run python scripts/serve.py --http
```

`docs/restore.md` covers restoring the prebuilt store rather than building it, and pointing the
model layer at any OpenAI-compatible endpoint. The large stores, the PDFs, the HTML, the Postgres
datadir and the embeddings, are not committed. The served path is entirely under `./data`.
