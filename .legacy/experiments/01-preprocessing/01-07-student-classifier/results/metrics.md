student-v4 on the teacher-held-out split (n=13,567): acc **0.826**, macro-F1 **0.771**.
On the 1002 gold occurrences: acc **0.852** (58 hand-labeled: **0.862**).

**The gold set cannot rank these two students.** 944 of its 1002 rows were pre-filled by student-v1 and waved through, and 100.0% of those still carry exactly what student-v1 wrote. So student-v1 scores **0.995** here by construction, and student-v4's **0.852** measures agreement with student-v1, not accuracy. Only the hand-typed rows are independent:

| rows | student-v4 | student-v1 |
|---|--:|--:|
| hand-typed (n=58) | 0.862 | 0.914 |
| pre-filled (n=944) | 0.852 | 1.000 |

At n=58 the hand-typed gap is 3 items, which settles nothing. An independent sample is what would.

| student | teacher-held-out acc | macro-F1 |
|---|--:|--:|
| student-v1 | 0.894 | 0.717 |
| student-v2 | 0.897 | 0.713 |
| student-v3 | 0.844 | 0.723 |
| student-v4 | 0.826 | 0.771 |

| intent | F1 |
|---|--:|
| uses | 0.709 |
| extends | 0.747 |
| compares | 0.752 |
| motivates | 0.820 |
| background | 0.887 |
| critiques | 0.708 |

Precision on the balanced gold set does not transfer to a corpus two thirds `background`, so the observed marginal is inverted through P(pred | gold) (condition 1.4).

Read the last two columns as departures from student-v1, not as errors: the confusion behind them is the anchored gold set above.

| intent | student-v4 says | bias-corrected | precision at the corpus rate | student-v1 |
|---|--:|--:|--:|--:|
| uses | 17.09% | 9.01% | 0.48 (0.21-0.70) | 1.00 |
| extends | 2.99% | 1.87% | 0.49 (0.00-0.88) | 1.00 |
| compares | 6.71% | 4.75% | 0.61 (0.24-0.90) | 1.00 |
| motivates | 1.19% | 0.23% | 0.17 (0.00-1.00) | 0.04 |
| background | 69.45% | 83.13% | 0.99 (0.98-0.99) | 1.00 |
| critiques | 2.56% | 1.00% | 0.35 (0.00-0.93) | 1.00 |

Against student-v1 over 67,357,119 shared edges, the two agree on **85.8%**.
