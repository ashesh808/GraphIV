# Deep-lever runs — index

Detailed per-run reviews for experiments 9–12 live in `runs/<topic>/<config>/` (`report.md`, `report.tex`, `run.json`, `digest.txt`, `judge_transcript.json`, `figures/`). This store is the shared, deduped source the lever experiments read; each `experiment-N/results/` holds only the quantitative roll-up (`metrics.md`, `pairwise.json`, `ablation.png`).

**Config legend** — `deep{N}`=judge-loop max_rounds, `k{N}`=critique_k, `r{F}`=recency, `-nofig`=figures off (gallery on when absent), `standard-indegree-r0.0-nofpull`=exp12 *before-2023* single-pass baseline.

**Which experiment uses which configs**
- **exp9** judge-loop rounds: `deep{1,2,4,6}-k4-r0.4-nofig` — swept across ALL 27 topics
- **exp10** critique depth: `deep2-k{0,4,8}-r0.4-nofig` — 8-topic panel
- **exp11** vision figures: `deep2-k4-r0.4` (on) · `deep2-k4-r0.4-nofig` (off) — 8-topic panel
- **exp12** dogfood: `deep3-k6-r0.5` (after-deep) · `standard-indegree-r0.0-nofpull` (before-2023) — 8-topic panel

**243 runs across 27 topics.** The exp9 judge-loop sweep (`deep{1,2,4,6}-k4-r0.4-nofig`) covers all 27; the 27 panel topics also carry the exp10/11/12 configs.

## contrastive-self-supervised-representation-learn

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/contrastive-self-supervised-representation-learn/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/contrastive-self-supervised-representation-learn/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## deep-reinforcement-learning

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/deep-reinforcement-learning/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/deep-reinforcement-learning/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/deep-reinforcement-learning/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/deep-reinforcement-learning/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/deep-reinforcement-learning/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/deep-reinforcement-learning/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/deep-reinforcement-learning/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/deep-reinforcement-learning/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/deep-reinforcement-learning/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/deep-reinforcement-learning/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/deep-reinforcement-learning/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/deep-reinforcement-learning/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/deep-reinforcement-learning/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/deep-reinforcement-learning/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/deep-reinforcement-learning/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/deep-reinforcement-learning/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/deep-reinforcement-learning/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## diffusion-models-for-audio-and-speech-synthesis

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-audio-and-speech-synthesis/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## diffusion-models-for-autonomous-driving

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/diffusion-models-for-autonomous-driving/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-autonomous-driving/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## diffusion-models-for-image-generation

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/diffusion-models-for-image-generation/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/diffusion-models-for-image-generation/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-image-generation/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## diffusion-models-for-molecular-generation

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/diffusion-models-for-molecular-generation/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/diffusion-models-for-molecular-generation/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-molecular-generation/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/diffusion-models-for-molecular-generation/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-molecular-generation/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/diffusion-models-for-molecular-generation/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/diffusion-models-for-molecular-generation/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/diffusion-models-for-molecular-generation/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-molecular-generation/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/diffusion-models-for-molecular-generation/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-molecular-generation/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/diffusion-models-for-molecular-generation/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/diffusion-models-for-molecular-generation/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/diffusion-models-for-molecular-generation/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-molecular-generation/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/diffusion-models-for-molecular-generation/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/diffusion-models-for-molecular-generation/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## diffusion-models-for-video-generation

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/diffusion-models-for-video-generation/standard-indegree-r0.0-nofpull/report.md) | — |
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
| standard-indegree-r0.0-nofpull | [md](runs/graph-neural-networks/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/graph-neural-networks/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/graph-neural-networks/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/graph-neural-networks/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## graph-neural-networks-for-combinatorial-optimiza

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-combinatorial-optimiza/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## graph-neural-networks-for-drug-discovery

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/graph-neural-networks-for-drug-discovery/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-drug-discovery/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## graph-neural-networks-for-recommendation-systems

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/graph-neural-networks-for-recommendation-systems/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/graph-neural-networks-for-recommendation-systems/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## large-language-model-agents-and-tool-use

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/large-language-model-agents-and-tool-use/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/large-language-model-agents-and-tool-use/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/large-language-model-agents-and-tool-use/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## long-context-methods-for-transformers

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/long-context-methods-for-transformers/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/long-context-methods-for-transformers/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/long-context-methods-for-transformers/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/long-context-methods-for-transformers/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/long-context-methods-for-transformers/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/long-context-methods-for-transformers/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/long-context-methods-for-transformers/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/long-context-methods-for-transformers/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/long-context-methods-for-transformers/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/long-context-methods-for-transformers/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/long-context-methods-for-transformers/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/long-context-methods-for-transformers/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/long-context-methods-for-transformers/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/long-context-methods-for-transformers/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/long-context-methods-for-transformers/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/long-context-methods-for-transformers/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/long-context-methods-for-transformers/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## mixture-of-experts-models-for-scaling-neural-net

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/mixture-of-experts-models-for-scaling-neural-net/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## preference-optimization-and-rlhf-for-language-mo

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/preference-optimization-and-rlhf-for-language-mo/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## reinforcement-learning-for-automated-theorem-pro

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-automated-theorem-pro/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## reinforcement-learning-for-autonomous-driving

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/reinforcement-learning-for-autonomous-driving/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/reinforcement-learning-for-autonomous-driving/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## retrieval-augmented-generation

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/retrieval-augmented-generation/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/retrieval-augmented-generation/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/retrieval-augmented-generation/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/retrieval-augmented-generation/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/retrieval-augmented-generation/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/retrieval-augmented-generation/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/retrieval-augmented-generation/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/retrieval-augmented-generation/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/retrieval-augmented-generation/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/retrieval-augmented-generation/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/retrieval-augmented-generation/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/retrieval-augmented-generation/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/retrieval-augmented-generation/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/retrieval-augmented-generation/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/retrieval-augmented-generation/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/retrieval-augmented-generation/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/retrieval-augmented-generation/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## speculative-decoding-for-faster-llm-inference

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/speculative-decoding-for-faster-llm-inference/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/speculative-decoding-for-faster-llm-inference/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## state-space-models-for-sequence-modeling

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/state-space-models-for-sequence-modeling/standard-indegree-r0.0-nofpull/report.md) | — |
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
| standard-indegree-r0.0-nofpull | [md](runs/test-time-compute-and-reasoning-in-large-languag/standard-indegree-r0.0-nofpull/report.md) | — |
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
| standard-indegree-r0.0-nofpull | [md](runs/transformer-attention-models-for-language/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/transformer-attention-models-for-language/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/transformer-attention-models-for-language/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/transformer-attention-models-for-language/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/transformer-attention-models-for-language/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## transformer-models-for-autonomous-driving-percep

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/transformer-models-for-autonomous-driving-percep/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-autonomous-driving-percep/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## transformer-models-for-code-generation

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/transformer-models-for-code-generation/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/transformer-models-for-code-generation/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-code-generation/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/transformer-models-for-code-generation/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-code-generation/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/transformer-models-for-code-generation/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/transformer-models-for-code-generation/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/transformer-models-for-code-generation/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-code-generation/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/transformer-models-for-code-generation/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-code-generation/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/transformer-models-for-code-generation/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/transformer-models-for-code-generation/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/transformer-models-for-code-generation/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-code-generation/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/transformer-models-for-code-generation/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/transformer-models-for-code-generation/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## transformers-for-program-synthesis

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/transformers-for-program-synthesis/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/transformers-for-program-synthesis/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-program-synthesis/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/transformers-for-program-synthesis/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/transformers-for-program-synthesis/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/transformers-for-program-synthesis/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/transformers-for-program-synthesis/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/transformers-for-program-synthesis/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-program-synthesis/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/transformers-for-program-synthesis/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/transformers-for-program-synthesis/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/transformers-for-program-synthesis/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/transformers-for-program-synthesis/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/transformers-for-program-synthesis/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-program-synthesis/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/transformers-for-program-synthesis/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-program-synthesis/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## transformers-for-protein-structure-prediction

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/transformers-for-protein-structure-prediction/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/transformers-for-protein-structure-prediction/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-protein-structure-prediction/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/transformers-for-protein-structure-prediction/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/transformers-for-protein-structure-prediction/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/transformers-for-protein-structure-prediction/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/transformers-for-protein-structure-prediction/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/transformers-for-protein-structure-prediction/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-protein-structure-prediction/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/transformers-for-protein-structure-prediction/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/transformers-for-protein-structure-prediction/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/transformers-for-protein-structure-prediction/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/transformers-for-protein-structure-prediction/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/transformers-for-protein-structure-prediction/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-protein-structure-prediction/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/transformers-for-protein-structure-prediction/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-protein-structure-prediction/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

## transformers-for-time-series-forecasting

| config | review | tex |
|---|---|---|
| standard-indegree-r0.0-nofpull | [md](runs/transformers-for-time-series-forecasting/standard-indegree-r0.0-nofpull/report.md) | — |
| standard-ppr-deep1-k4-r0.4-nofig | [md](runs/transformers-for-time-series-forecasting/standard-ppr-deep1-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-time-series-forecasting/standard-ppr-deep1-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k0-r0.4-nofig | [md](runs/transformers-for-time-series-forecasting/standard-ppr-deep2-k0-r0.4-nofig/report.md) | [tex](runs/transformers-for-time-series-forecasting/standard-ppr-deep2-k0-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k4-r0.4 | [md](runs/transformers-for-time-series-forecasting/standard-ppr-deep2-k4-r0.4/report.md) | [tex](runs/transformers-for-time-series-forecasting/standard-ppr-deep2-k4-r0.4/report.tex) |
| standard-ppr-deep2-k4-r0.4-nofig | [md](runs/transformers-for-time-series-forecasting/standard-ppr-deep2-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-time-series-forecasting/standard-ppr-deep2-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep2-k8-r0.4-nofig | [md](runs/transformers-for-time-series-forecasting/standard-ppr-deep2-k8-r0.4-nofig/report.md) | [tex](runs/transformers-for-time-series-forecasting/standard-ppr-deep2-k8-r0.4-nofig/report.tex) |
| standard-ppr-deep3-k6-r0.5 | [md](runs/transformers-for-time-series-forecasting/standard-ppr-deep3-k6-r0.5/report.md) | [tex](runs/transformers-for-time-series-forecasting/standard-ppr-deep3-k6-r0.5/report.tex) |
| standard-ppr-deep4-k4-r0.4-nofig | [md](runs/transformers-for-time-series-forecasting/standard-ppr-deep4-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-time-series-forecasting/standard-ppr-deep4-k4-r0.4-nofig/report.tex) |
| standard-ppr-deep6-k4-r0.4-nofig | [md](runs/transformers-for-time-series-forecasting/standard-ppr-deep6-k4-r0.4-nofig/report.md) | [tex](runs/transformers-for-time-series-forecasting/standard-ppr-deep6-k4-r0.4-nofig/report.tex) |

