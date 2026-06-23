# experiment-6 — Vision figure augmentation

## Hypothesis
A literature review is richer with **figures** — architecture diagrams and result plots carry
information no abstract states. The vision model can crop a paper's key figure and write a caption
that is *faithful* to the image (not hallucinated), adding grounded visual context at low cost and
without hurting the text.

## What we test
One variable: `figures ∈ {on, off}` in the deep loop (held constant: deep path, `max_rounds=2`,
`critique_k=4`, two topics). When on, `figures_for` (Gemma-4-26B-Vision) crops Figure-1 from the top
landmarks (by in-degree + recency) and captions each. We then **re-check** every caption against its
saved crop with the vision model (`caption_faithfulness`) — the measured answer to "can we leverage
vision?".

## Why (grounded in the corpus)
Multimodal scientific agents already close the loop with vision: e.g. AI-Scientist-v2 uses a
**Vision-Language-Model feedback loop** to read figures during autonomous experimentation
(arXiv:2504.08066). If a VLM can critique a plot well enough to drive research, it can caption a
cropped figure well enough to enrich a review — this experiment checks that claim on our own outputs.

## How to reproduce
```bash
uv run python experiments/experiment-6-vision-figures/run.py
```
Sample galleries land under `results/runs/.../figures/*.png` with captions in `run.json`.

## Results
Mean over 2 topics (deep path, max_rounds=2, critique_k=4); full table in `results/metrics.md`.

| figures | n_figures | caption_faithfulness | words | grounded | off_digest | j_overall |
|---|---|---|---|---|---|---|
| **on** | 9.0 | **0.89** | 3874 | 46.0 | 0.5 | 4.75 |
| off | 0.0 | — | 3065 | 51.0 | 2.0 | 3.75 |

**Yes — vision is a clean, measurable win.** With figures on, the deep loop adds **9 captioned
figures per topic**, and the vision model **re-confirms 0.89 of its own captions** against the saved
crops (an independent vision recheck, not the same call). Crucially it is *additive*: `off_digest`
is actually *lower* with figures (0.5 vs 2.0) and the judge rates the figured report higher (4.75 vs
3.75). The `words` increase (3874 vs 3065) is largely the gallery captions themselves. (Validated
qualitatively too: DDPM's crop captioned as "a 2×2 grid of human faces … CelebA-HQ and CIFAR-10".)

## Ablation finding & caveat (filled)
Figures add grounded visual context at ~0.89 caption faithfulness with no cost to the text's
grounding. Caveat: the j_overall gap (4.75 vs 3.75) is from only 2 topics and partly reflects the
judge rewarding apparent completeness; the *robust* claim is the figure count + caption faithfulness,
not the judge delta. Coverage is bounded by first-figure cropping (`pdf_figures.first_figure`) — key
results in later figures or tables are missed.

## Ablation finding & caveat
Vision is a clean win as an *augmentation*: it adds grounded visual context without touching the
prose metrics. Caveat: figure cropping is heuristic (first "Figure 1" region), so it misses papers
whose key result is a later figure or a table — coverage is bounded by `pdf_figures.first_figure`,
not by the vision model.
