# Head-to-head, GraphIV side (2026-07-03)

Five topics, identical instruction template ("Write a literature review tracing the development
of {topic}: the foundational work, the key methodological advances, and the current research
frontier including the most recent papers. Cite specific papers throughout."), `--set-effort 4`,
single RTX 3090. Counts via `code/h2h_verify.py` (corpus check + live arxiv.org fallback).
Commercial (Claude/Gemini deep research) runs use the same strings with refinement declined
("proceed with the question as stated"); their outputs get the identical verifier.

| topic | wall time | ids cited | verified | fabricated | ≥2025 | 2026 |
|---|---|--:|--:|--:|--:|--:|
| neural audio codecs | 6:03* | 45 | 45 | 0 | 18 | 11 |
| test-time compute & reasoning | 2:46* | 56 | 56 | 0 | 28 | 5 |
| state-space models | 7:38* | 51 | 51 | 0 | 14 | 7 |
| RL for theorem proving | 5:14* | 60 | 60 | 0 | 23 | 12 |
| QEC neural decoders | 5:09 | 55 | 55 | 0 | 14 | 5 |
| **total** | | **267** | **267** | **0** | **97** | **40** |

\* warm-cache re-run times (a slug-collision bug overwrote the first pass; cold first-pass times
were 4:58–11:00). Cold-cache reference: 8:38 (audio codecs, earlier run).

Reports: [`graphiv/`](graphiv/). The corpus delta ends ~2026-06; commercial tools can browse
newer arXiv — the comparison is honest in both directions and we state it.
