# Topic name generation

## Question

What a topic name costs, whether the abstract earns its tokens, and why names collide.

## Configuration

| item | value |
| --- | --- |
| tree | kmeans/kmeans/kmeans at k=16, 16 / 256 / 4,096 nodes |
| model | Gemma-4-26B-Batched via llama-router on `localhost:11434` |
| sample | the 10 papers nearest each leaf centroid, euclidean in the reduced space |
| abstract | truncated to 700 characters |
| pool | 4 concurrent for the arms, 8 for the shipped stage |
| probe set | two whole level 1 subtrees, 32 leaves |

## Reasoning must be off

| setting | content | completion tokens | latency |
| --- | --- | --- | --- |
| default, `max_tokens` 40 | empty | 40, all chain of thought | 10.81 s |
| default, `max_tokens` 300 | Automatic Speech Recognition | 262 | n/a |
| `chat_template_kwargs.enable_thinking` false | Automatic speech recognition research | 5 | n/a |
| `reasoning_effort` none | Automatic speech recognition systems | 5 | 0.52 s |

## Throughput

| arm | 32 leaves | req/s | prompt tokens | completion tokens | latency | 4,368 nodes |
| --- | --- | --- | --- | --- | --- | --- |
| titles only | 4.3 s | 7.46 | 216 | 5 | 0.52 s | ~10 min |
| titles and abstracts | 19.3 s | 1.66 | 1,496 | 5 | 2.33 s | ~42 min |
| refine pass | 3.4 s | 9.40 | 180 | 5 | 0.43 s | +8 min |

Shipped at pool 8: 4,096 leaves in 34 minutes, 2.0 req/s.

## The refine pass, rejected

A second top-down pass rewriting each child under its parent, with the papers no longer in view.

| input | output |
| --- | --- |
| Hashing Algorithms and Techniques | Cryptographic Hash Function Design |
| Belief Propagation Algorithms | Message Passing Techniques |
| Clustering Algorithms | Unsupervised Pattern Recognition Methods |
| Algorithmic Complexity Analysis | Asymptotic Resource Estimation |
| Confined Fluid Dynamics | Flow Within Microchannels |
| Statistical Estimation and Optimization | Stochastic Learning Theory |

## Collisions, at a 6 word cap and per-node naming

| level | nodes | distinct names | collisions |
| --- | --- | --- | --- |
| leaf | 4,096 | 3,712 | 384 |
| parent | 256 | 221 | 35 |
| grandparent | 16 | 16 | 0 by string, 4 overlapping groups |

Two leaves under one parent, both named Random Graph Theory:

| leaf | nearest-centroid titles |
| --- | --- |
| 4/4/5 | Determinantal spanning forests on planar graphs; Weak regularity and finitely forcible graph limits; Entropy inequalities for factors of IID |
| 4/4/11 | Probability a random graph with a given degree sequence is connected; Giant component of random geometric graphs; Diameter thresholds of random Cayley graphs |

## Collisions, at a 15 word leaf cap with siblings named together

| level | nodes | distinct names | collisions |
| --- | --- | --- | --- |
| leaf | 4,096 | 4,083 | 13 |
| parent | 256 | 249 | 7 |
| grandparent | 16 | 16 | 0 by string, 0 overlapping |

| level | mean words | max words |
| --- | --- | --- |
| leaf | 8.0 | 15 |
| parent | 2.7 | 3 |
| grandparent | 2.1 | 3 |

## Files

| file | holds |
| --- | --- |
| `main.py` | the four arms and the timing table |
| `names.json` | the 32 probe leaves under every arm |
| `timing.json` | the throughput table |
