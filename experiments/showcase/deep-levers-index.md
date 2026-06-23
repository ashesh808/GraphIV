# Deep-lever runs — index

Detailed per-run reviews for experiments 9–12 live in `runs/<topic>/<config>/` (`report.md`, `report.tex`, `run.json`, `digest.txt`, `judge_transcript.json`, `figures/`). This store is the shared, deduped source the lever experiments read; each `experiment-N/results/` holds only the quantitative roll-up (`metrics.md`, `pairwise.json`, `ablation.png`).

**Config legend** — `deep{N}`=judge-loop max_rounds, `k{N}`=critique_k, `r{F}`=recency, `-nofig`=figures off (gallery on when absent), `standard-indegree-r0.0-nofpull`=exp12 *before-2023* single-pass baseline.

**Which experiment uses which configs**
- **exp9** judge-loop rounds: `deep{1,2,4,6}-k4-r0.4-nofig`
- **exp10** critique depth: `deep2-k{0,4,8}-r0.4-nofig`
- **exp11** vision figures: `deep2-k4-r0.4` (on) · `deep2-k4-r0.4-nofig` (off)
- **exp12** dogfood: `deep3-k6-r0.5` (after-deep) · `standard-indegree-r0.0-nofpull` (before-2023)

**72 runs across 8 topics.**

## diffusion-models-for-image-generation

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/diffusion-models-for-image-generation/standard-indegree-r0.0-nofpull/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-indegree-r0.0-nofpull/report.tex) |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## diffusion-models-for-video-generation

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/diffusion-models-for-video-generation/standard-indegree-r0.0-nofpull/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-indegree-r0.0-nofpull/report.tex) |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/diffusion-models-for-video-generation/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/diffusion-models-for-video-generation/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/diffusion-models-for-video-generation/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/diffusion-models-for-video-generation/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/diffusion-models-for-video-generation/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/diffusion-models-for-video-generation/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/diffusion-models-for-video-generation/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/diffusion-models-for-video-generation/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-video-generation/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## graph-neural-networks

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/graph-neural-networks/standard-indegree-r0.0-nofpull/report.md) | [tex](runs/graph-neural-networks/standard-indegree-r0.0-nofpull/report.tex) |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/graph-neural-networks/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/graph-neural-networks/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## graph-neural-networks-for-drug-discovery

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/graph-neural-networks-for-drug-discovery/standard-indegree-r0.0-nofpull/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-indegree-r0.0-nofpull/report.tex) |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## large-language-model-agents-and-tool-use

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/large-language-model-agents-and-tool-use/standard-indegree-r0.0-nofpull/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-indegree-r0.0-nofpull/report.tex) |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## state-space-models-for-sequence-modeling

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/state-space-models-for-sequence-modeling/standard-indegree-r0.0-nofpull/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-indegree-r0.0-nofpull/report.tex) |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/state-space-models-for-sequence-modeling/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/state-space-models-for-sequence-modeling/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/state-space-models-for-sequence-modeling/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/state-space-models-for-sequence-modeling/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/state-space-models-for-sequence-modeling/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/state-space-models-for-sequence-modeling/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/state-space-models-for-sequence-modeling/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/state-space-models-for-sequence-modeling/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/state-space-models-for-sequence-modeling/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## test-time-compute-and-reasoning-in-large-languag

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-indegree-r0.0-nofpull/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-indegree-r0.0-nofpull/report.tex) |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/test-time-compute-and-reasoning-in-large-languag/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## transformer-attention-models-for-language

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/transformer-attention-models-for-language/standard-indegree-r0.0-nofpull/report.md) | [tex](runs/transformer-attention-models-for-language/standard-indegree-r0.0-nofpull/report.tex) |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/transformer-attention-models-for-language/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/transformer-attention-models-for-language/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |
