# Level 2 leaf method

## Question

Whether the 47.5% of papers hdbscan labels `-1` are papers with no neighborhood, and which level 2
method and parameter the corpus should use.

## Configuration

| item | value |
| --- | --- |
| papers | 3,103,758 |
| vectors | `v2.papers.embed_umap`, 50 dim, cosine-metric umap |
| levels 0 and 1 | held fixed at the shipped kmeans k=20, 400 parents |
| external label | `primary_category`, 171 distinct values, never seen by the embedding |
| agreement sample | 300,000 clustered rows, seed 69420 |
| noise rows excluded from agreement | yes, so a noisy arm is not rewarded for declining |

## Is the noise real

Distance is euclidean in the reduced space, to the nearest real leaf centroid inside the same parent.

| quantity | value |
| --- | --- |
| noise rows, median distance | 0.2922 |
| clustered rows, median distance | 0.1877 |
| noise rows, p90 distance | 0.5068 |
| clustered rows, p90 distance | 0.3808 |
| noise rows inside the nearest leaf's p95 member radius | 43.82% |

## Arms

| arm | leaves | noise % | p10 | median | p90 | max | AMI | homogeneity | purity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hdbscan mcs60 ms60 (shipped) | 1,631 | 47.48 | 82 | 252 | 2,771 | 23,636 | 0.5549 | 0.7065 | 0.5945 |
| hdbscan mcs60 ms5 | 2,173 | 42.79 | 73 | 185 | 1,818 | 23,666 | 0.5409 | 0.7051 | 0.5918 |
| hdbscan mcs60 ms5 plus nearest leaf | 2,173 | 0.20 | 249 | 662 | 3,108 | 24,099 | 0.4845 | 0.6749 | 0.5649 |
| kmeans k4 | 1,600 | 0 | 459 | 1,646 | 3,757 | 10,360 | 0.4831 | 0.6748 | 0.5665 |
| kmeans k6 | 2,400 | 0 | 288 | 1,055 | 2,605 | 7,298 | 0.4664 | 0.6892 | 0.5776 |
| kmeans k10 | 4,000 | 0 | 166 | 614 | 1,591 | 5,050 | 0.4416 | 0.7079 | 0.5908 |
| kmeans k20 | 8,000 | 0 | 70 | 300 | 810 | 2,954 | 0.4020 | 0.7342 | 0.6068 |

AMI is corrected for cluster count and homogeneity and purity are not, so across rows of differing
leaf count the three move in opposite directions by construction.

## The shipped tree's largest leaf, 23,636 papers

| title |
| --- |
| Online Automatic Speech Recognition with Listen, Attend and Spell Model |
| Online Target Speaker Voice Activity Detection for Speaker Diarization |
| ConvNeXt Based Neural Network for Audio Anti-Spoofing |
| Dynamic Real-Time Ambisonics Order Adaptation for Immersive Networked Music Performances |
| RIME: Enabling Large-Scale Agentic Music Post-Production |

## The same mass under kmeans k20

| leaf | papers | titles |
| --- | --- | --- |
| 190020000 | 2,632 | Cascaded encoders for unifying streaming and non-streaming ASR; Quantifying Bias in Automatic Speech Recognition |
| 190020001 | 2,371 | Generating music with sentiment using Transformer-GANs; MuseTok: Symbolic Music Tokenization |
| 190020004 | 2,084 | Absorbing Discrete Diffusion for Speech Enhancement; LongCat-Audio-Codec |

## Files

| file | holds |
| --- | --- |
| `dump.py` | the one-time vector and label cache |
| `main.py` | the noise probe and arms A through D |
| `matched.py` | kmeans at leaf counts matched to the hdbscan arms |
| `titles.py` | the leaf title spot-check |
| `noise_probe.json`, `arms.json`, `matched.json` | the tables above |
