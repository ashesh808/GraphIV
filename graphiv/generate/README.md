# generate

Graded cohort to a grounded, cited literature review. Every arXiv id in the output is corpus-verified before the report leaves this package.

## Modules

```
pipeline.py      the single-pass driver
loop.py          the judge-driven deep rounds, with gap injection
schema.py        the question-specific extraction schema
extract.py       per-paper schema extraction, cached
critique.py      full-PDF critique, cached
judge.py         the multi-axis judge, which owns loop termination
compose.py       the digest builder and the in-loop skeleton compose
long_compose.py  outline, per-section compose, intro and close
narrate.py       digest narration plus the mechanical grounding guard
latex.py         markdown to report.tex and refs.bib
figures.py       the vision figure gallery
pdf_figures.py   page rendering out of the PDF
fulltext.py      ar5iv section extraction, cached
story.py         the lineage threads behind the outline
graph_viz.py     the story-graph PNG and interactive page
progress.py      per-stage timing written to progress.json
```

## Running it

```sh
uv run python scripts/research.py "<question>" --set-effort 4
```
