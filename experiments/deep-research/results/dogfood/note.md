# Dogfood: GraphIV surveying its own design space

One `--set-effort 4` run (5m09s, 2026-07-03) on:

> *citation-graph-based retrieval-augmented generation for scientific literature review:
> retrieval over citation networks, grounded long-form synthesis, and evaluation of generated
> reviews*

The judge saturated after **one round** (the question maps onto a dense, well-connected
subgraph): 120 landmarks, 56 at the 2024+ frontier, **43 grounded / 0 off-digest citations**.
The full review is [`report.md`](report.md) (tex + bib alongside). This is the working method
behind the system: we asked the tool to survey its own field, read the result, and let it
steer design — not "self-awareness," but a research instrument pointed at itself.

## What the survey confirms we built

- Citation-graph-native retrieval over vector-only RAG (the G-Retriever / GRAG / CG-RAG line —
  arXiv:2402.07630, 2405.16506, 2501.15067) → our PPR-ranked induced subgraph.
- Long-form review synthesis with structural grounding (LitFM's citing-sentence edge
  annotations, arXiv:2409.12177, parallel our intent-labeled edges + context sentences).
- Post-hoc citation correction (CiteFix, arXiv:2504.15629) → our fuzzy-correct → corpus-verify
  → strip guard, which goes further: existence is checked against the full corpus.

## Gaps it surfaced — and what we did about them

- **Human expert validation of generated reviews** (named "a critical gap" via
  arXiv:2606.09105): true of GraphIV too. Our validated-LLM-judge + objective metric vector is
  the affordable proxy; expert study stays future work and the paper's limitations say so.
- **Interleaved claim-level attribution** (arXiv:2407.01796): we cite at claim granularity but
  don't emit paired claim→reference structures; the faithfulness tripwire samples instead.
  A candidate lever, unmeasured — left on the table deliberately (measure-before-ship).
- **Stance-typed claim networks** (arXiv:2605.30966): our intent+polarity edges are a
  corpus-scale version of this; the reified per-claim form is richer and future work.
- **Graph-driven idea generation** (Graph2Idea, arXiv:2606.09105; citation-evolution DAGs,
  arXiv:2605.14790): the natural next application of the store beyond reviews.

Reproduce: `uv run python phases/phase-6/run.py "<the question above>" --set-effort 4`.
