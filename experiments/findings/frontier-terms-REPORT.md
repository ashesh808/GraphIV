# frontier-terms

Every table below is written by `report.py` out of `results/`, never by hand.

## Configuration

| item | value |
| --- | --- |
| seed_limit | 5000 |
| top_k | 200 |
| hop_limit | 20000 |
| ancestors | True |
| frontier | True |
| core | 200 |
| depth | 4 |
| decay | 0.5 |
| headline budget | 1000 |
| lattice settings | 2,048 |
| ladder | 0, 0.25, 0.5, 1, 2, 3, 4 |

## What each term buys, across the three metrics

![marginals](figures/term_marginals.png)

## SurveyMatch

| item | value |
| --- | --- |
| cases | 300 |
| mean ceiling | 0.831 |
| median key | 58 |
| median pool | 7,314 |
| median seconds | 3.00 |
| p90 seconds | 6.03 |

### SurveyMatch, what each term buys

| term | mean marginal | at its best point | W/L | p | the point tested |
| --- | --- | --- | --- | --- | --- |
| anc | +0.1294 | +0.4732 | 299/1 | 2.96e-88 | anc |
| cocite | +0.0991 | +0.0077 | 101/37 | 4.75e-08 | cos+anc+cocite |
| anc_decay | +0.0913 | -0.0066 | 25/26 | 1.000 | anc+anc_decay |
| anc2 | +0.0703 | +0.0099 | 117/46 | 2.54e-08 | cos+rec+anc+anc2+anc_decay+cocite+hub |
| cos | +0.0074 | +0.0059 | 58/33 | 0.011 | cos+anc+cocite |
| hub | -0.0294 | +0.0042 | 61/68 | 0.597 | anc+cocite+hub |
| couple | -0.0301 | -0.0127 | 31/116 | 9.39e-13 | cos+anc+anc_decay+cocite+couple |
| rec | -0.0382 | +0.0022 | 47/84 | 1.56e-03 | rec+anc+anc_decay+cocite |
| fro_decay | -0.0386 | -0.0183 | 16/127 | 1.25e-22 | cos+anc+anc_decay+fro_decay+cocite |
| fro2 | -0.0397 | -0.0062 | 35/100 | 1.94e-08 | anc+fro2+anc_decay+cocite |
| fro | -0.0515 | -0.0053 | 36/90 | 1.64e-06 | anc+fro+anc_decay+cocite |

### SurveyMatch, the strongest lattice points

| terms kept | mean | sd | W/L vs best | p |
| --- | --- | --- | --- | --- |
| anc | 0.8000 | 0.173 | 0/0 | 1.000 |
| cos+anc+cocite | 0.7969 | 0.168 | 34/73 | 2.06e-04 |
| anc+cocite+hub | 0.7952 | 0.169 | 32/100 | 2.43e-09 |
| cos+anc+cocite+hub | 0.7944 | 0.167 | 37/112 | 5.79e-10 |
| anc+anc_decay | 0.7934 | 0.173 | 25/26 | 1.000 |
| anc+anc_decay+cocite+hub | 0.7931 | 0.170 | 32/105 | 2.88e-10 |
| cos+anc+anc_decay+cocite | 0.7920 | 0.171 | 33/79 | 1.64e-05 |
| anc+cocite | 0.7910 | 0.173 | 31/71 | 9.31e-05 |
| rec+anc+anc_decay+cocite | 0.7908 | 0.169 | 35/110 | 3.19e-10 |
| cos+rec+anc+anc_decay+cocite | 0.7907 | 0.168 | 35/109 | 4.86e-10 |
| cos+anc+anc_decay+cocite+hub | 0.7899 | 0.170 | 34/114 | 2.69e-11 |
| cos+anc | 0.7892 | 0.169 | 30/113 | 1.58e-12 |
| anc+anc_decay+cocite | 0.7887 | 0.173 | 32/76 | 2.76e-05 |
| cos+rec+anc+anc2+anc_decay+cocite+hub | 0.7875 | 0.172 | 37/120 | 2.00e-11 |
| rec+anc+anc2+anc_decay+cocite+hub | 0.7874 | 0.172 | 36/117 | 3.40e-11 |

### SurveyMatch, one exponent moved from `anc`

| term | 0 | 0.25 | 0.5 | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cos | **0.8000** | 0.7969 | 0.7946 | 0.7892 | 0.7616 | 0.7257 | 0.6864 |
| rec | 0.8000 | **0.8050** | 0.7919 | 0.6907 | 0.4123 | 0.2684 | 0.2171 |
| anc | 0.3269 | **0.8000** | 0.8000 | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| fro | 0.8000 | **0.8051** | 0.7880 | 0.6794 | 0.5174 | 0.4988 | 0.4920 |
| anc2 | **0.8000** | 0.7399 | 0.7077 | 0.6751 | 0.6367 | 0.6152 | 0.6021 |
| fro2 | **0.8000** | 0.7998 | 0.7867 | 0.7178 | 0.5649 | 0.5054 | 0.4801 |
| anc_decay | 0.8000 | **0.8014** | 0.7993 | 0.7934 | 0.7903 | 0.7903 | 0.7903 |
| fro_decay | **0.8000** | 0.7974 | 0.7858 | 0.7169 | 0.5811 | 0.5221 | 0.5083 |
| cocite | **0.8000** | 0.7953 | 0.7945 | 0.7910 | 0.7837 | 0.7787 | 0.7744 |
| couple | **0.8000** | 0.7925 | 0.7796 | 0.7233 | 0.6060 | 0.5399 | 0.4991 |
| hub | **0.8000** | 0.7966 | 0.7884 | 0.7478 | 0.6451 | 0.5695 | 0.5177 |

![ladder](figures/ladder_SurveyMatch.png)

### SurveyMatch, coordinate descent

| descent | start | tuned | the exponents it stopped at |
| --- | --- | --- | --- |
| from the lattice best | 0.8000 | 0.8108 | anc=1.5, cocite=0.25, cos=0.5, hub=0.25, rec=0.25 |
| from the shipped point | 0.7704 | 0.8123 | anc=4, cocite=0.5, cos=0.75, fro=0.25, hub=0.5, rec=0.75 |
| from everything on | 0.6416 | 0.8123 | anc=4, cocite=0.5, cos=0.75, fro=0.25, hub=0.5, rec=0.75 |

## FrontierMatch

| item | value |
| --- | --- |
| cases | 300 |
| mean ceiling | 0.816 |
| median key | 36 |
| median pool | 8,466 |
| median seconds | 0.96 |
| p90 seconds | 1.74 |

### FrontierMatch, what each term buys

| term | mean marginal | at its best point | W/L | p | the point tested |
| --- | --- | --- | --- | --- | --- |
| cocite | +0.0840 | +0.0311 | 142/15 | 4.07e-27 | cos+rec+anc+anc_decay+cocite+hub |
| anc_decay | +0.0767 | +0.0047 | 71/48 | 0.043 | cos+rec+anc+anc_decay+cocite+hub |
| anc | +0.0652 | +0.0055 | 91/35 | 6.36e-07 | cos+rec+anc+anc_decay+cocite+hub |
| cos | +0.0099 | +0.0038 | 46/28 | 0.047 | cos+rec+anc+anc_decay+cocite+hub |
| rec | +0.0072 | +0.0346 | 108/22 | 7.97e-15 | cos+rec+anc+anc_decay+cocite+hub |
| anc2 | -0.0003 | -0.0136 | 36/95 | 2.56e-07 | cos+rec+anc+anc2+cocite+hub |
| hub | -0.0021 | +0.0078 | 74/18 | 3.10e-09 | cos+rec+anc+anc_decay+cocite+hub |
| couple | -0.0031 | -0.0131 | 33/117 | 3.21e-12 | cos+rec+anc+anc_decay+cocite+couple+hub |
| fro2 | -0.0078 | -0.0054 | 44/87 | 2.16e-04 | cos+rec+anc+fro2+anc_decay+cocite+hub |
| fro_decay | -0.0107 | -0.0079 | 35/94 | 2.04e-07 | cos+rec+anc+anc_decay+fro_decay+cocite+hub |
| fro | -0.0254 | -0.0045 | 43/90 | 5.63e-05 | rec+anc+fro+anc_decay+cocite+hub |

### FrontierMatch, the strongest lattice points

| terms kept | mean | sd | W/L vs best | p |
| --- | --- | --- | --- | --- |
| cos+rec+anc+anc_decay+cocite+hub | 0.7551 | 0.225 | 0/0 | 1.000 |
| rec+anc+cocite+hub | 0.7528 | 0.222 | 55/68 | 0.279 |
| cos+rec+anc_decay+cocite | 0.7515 | 0.222 | 35/77 | 8.98e-05 |
| rec+anc+anc_decay+cocite+hub | 0.7513 | 0.228 | 28/46 | 0.047 |
| cos+rec+anc+cocite | 0.7511 | 0.222 | 48/72 | 0.035 |
| cos+rec+anc+cocite+hub | 0.7504 | 0.223 | 48/71 | 0.043 |
| cos+rec+anc+fro2+anc_decay+cocite+hub | 0.7497 | 0.217 | 44/87 | 2.16e-04 |
| cos+rec+anc_decay+cocite+hub | 0.7496 | 0.218 | 35/91 | 6.36e-07 |
| cos+rec+anc+fro2+anc_decay+cocite | 0.7485 | 0.219 | 43/85 | 2.59e-04 |
| rec+anc+cocite | 0.7483 | 0.222 | 49/84 | 3.05e-03 |
| rec+anc_decay+cocite+hub | 0.7480 | 0.221 | 36/78 | 1.04e-04 |
| cos+rec+anc+anc_decay+cocite | 0.7473 | 0.229 | 18/74 | 3.10e-09 |
| cos+rec+anc+anc_decay+fro_decay+cocite+hub | 0.7472 | 0.222 | 35/94 | 2.04e-07 |
| rec+anc+fro+anc_decay+cocite+hub | 0.7469 | 0.221 | 43/98 | 4.15e-06 |
| cos+rec+anc+fro+anc_decay+cocite+hub | 0.7467 | 0.223 | 43/91 | 4.11e-05 |

### FrontierMatch, one exponent moved from `cos+rec+anc+anc_decay+cocite+hub`

| term | 0 | 0.25 | 0.5 | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cos | 0.7513 | 0.7528 | 0.7549 | **0.7551** | 0.7505 | 0.7429 | 0.7348 |
| rec | 0.7205 | 0.7367 | 0.7447 | **0.7551** | 0.7500 | 0.6986 | 0.6291 |
| anc | 0.7496 | 0.7537 | **0.7557** | 0.7551 | 0.7472 | 0.7427 | 0.7355 |
| fro | 0.7551 | **0.7585** | 0.7572 | 0.7467 | 0.6885 | 0.6340 | 0.5965 |
| anc2 | **0.7551** | 0.7503 | 0.7450 | 0.7285 | 0.6767 | 0.6144 | 0.5612 |
| fro2 | 0.7551 | **0.7584** | 0.7568 | 0.7497 | 0.7118 | 0.6713 | 0.6406 |
| anc_decay | 0.7504 | 0.7611 | **0.7620** | 0.7551 | 0.7468 | 0.7448 | 0.7439 |
| fro_decay | 0.7551 | **0.7577** | 0.7563 | 0.7472 | 0.7148 | 0.6765 | 0.6471 |
| cocite | 0.7240 | 0.7363 | 0.7456 | **0.7551** | 0.7548 | 0.7502 | 0.7467 |
| couple | 0.7551 | **0.7565** | 0.7533 | 0.7420 | 0.7117 | 0.6820 | 0.6562 |
| hub | 0.7473 | 0.7499 | 0.7520 | **0.7551** | 0.7481 | 0.7385 | 0.7284 |

![ladder](figures/ladder_FrontierMatch.png)

### FrontierMatch, coordinate descent

| descent | start | tuned | the exponents it stopped at |
| --- | --- | --- | --- |
| from the lattice best | 0.7551 | 0.7698 | anc=2, anc_decay=0.25, cocite=2.5, cos=0.75, fro=0.25, hub=2.5, rec=1.5 |
| from the shipped point | 0.7365 | 0.7697 | anc=2.5, anc_decay=0.25, cocite=3, cos=0.5, fro=0.25, hub=4, rec=1.5 |
| from everything on | 0.6659 | 0.7687 | anc=4, cocite=4, cos=1, couple=0.5, fro_decay=0.25, hub=4, rec=2 |

## ConsensusMatch

| item | value |
| --- | --- |
| cases | 151 |
| mean ceiling | 0.993 |
| median key | 10 |
| median pool | 8,549 |
| median seconds | 1.10 |
| p90 seconds | 2.38 |

### ConsensusMatch, what each term buys

| term | mean marginal | at its best point | W/L | p | the point tested |
| --- | --- | --- | --- | --- | --- |
| anc | +0.1844 | +0.1850 | 107/13 | 1.50e-19 | cos+rec+anc+cocite |
| cocite | +0.1644 | +0.0682 | 72/19 | 1.97e-08 | cos+rec+anc+cocite |
| anc2 | +0.1267 | +0.0529 | 67/35 | 1.99e-03 | rec+anc+anc2+anc_decay+cocite+hub |
| cos | +0.0026 | +0.0207 | 43/15 | 3.07e-04 | cos+rec+anc+cocite |
| anc_decay | -0.0098 | +0.0037 | 38/37 | 1.000 | rec+anc+anc_decay+cocite |
| couple | -0.0299 | +0.0145 | 52/36 | 0.109 | rec+anc+anc2+anc_decay+cocite+couple |
| fro | -0.0370 | +0.0229 | 56/38 | 0.079 | cos+rec+anc+fro+anc2+cocite |
| fro_decay | -0.0391 | +0.0250 | 58/38 | 0.052 | cos+rec+anc+anc2+fro_decay+cocite |
| rec | -0.0446 | +0.0609 | 67/22 | 1.90e-06 | cos+rec+anc+cocite |
| hub | -0.0497 | +0.0382 | 55/17 | 8.14e-06 | rec+anc+anc2+anc_decay+cocite+hub |
| fro2 | -0.0499 | -0.0058 | 43/44 | 1.000 | cos+rec+anc+anc2+fro2+anc_decay+cocite |

### ConsensusMatch, the strongest lattice points

| terms kept | mean | sd | W/L vs best | p |
| --- | --- | --- | --- | --- |
| cos+rec+anc+cocite | 0.7963 | 0.228 | 0/0 | 1.000 |
| rec+anc+anc_decay+cocite | 0.7794 | 0.226 | 23/47 | 5.58e-03 |
| rec+anc+cocite | 0.7757 | 0.239 | 15/43 | 3.07e-04 |
| cos+rec+anc+anc_decay+cocite | 0.7656 | 0.217 | 17/55 | 8.14e-06 |
| rec+anc+anc2+anc_decay+cocite+hub | 0.7607 | 0.235 | 21/55 | 1.21e-04 |
| cos+rec+anc+anc2+anc_decay+cocite+hub | 0.7597 | 0.228 | 21/58 | 3.76e-05 |
| cos+rec+anc+anc2+anc_decay+cocite | 0.7484 | 0.227 | 21/64 | 3.28e-06 |
| cos+anc+anc_decay+cocite | 0.7466 | 0.234 | 21/63 | 4.97e-06 |
| anc+anc_decay+cocite | 0.7456 | 0.230 | 24/66 | 1.09e-05 |
| cos+rec+anc+anc2+fro2+anc_decay+cocite | 0.7426 | 0.235 | 18/72 | 8.07e-09 |
| rec+anc+anc2+fro2+anc_decay+cocite | 0.7413 | 0.238 | 17/67 | 3.50e-08 |
| anc+cocite+hub | 0.7406 | 0.252 | 26/69 | 1.18e-05 |
| cos+anc+cocite+hub | 0.7400 | 0.242 | 19/66 | 3.04e-07 |
| rec+anc+cocite+hub | 0.7395 | 0.233 | 15/64 | 2.30e-08 |
| cos+rec+anc+anc2+cocite+hub | 0.7393 | 0.251 | 18/66 | 1.33e-07 |

### ConsensusMatch, one exponent moved from `cos+rec+anc+cocite`

| term | 0 | 0.25 | 0.5 | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cos | 0.7757 | 0.7861 | 0.7920 | **0.7963** | 0.7921 | 0.7698 | 0.7400 |
| rec | 0.7354 | 0.7579 | 0.7797 | **0.7963** | 0.7044 | 0.3983 | 0.2372 |
| anc | 0.6114 | 0.7215 | 0.7756 | **0.7963** | 0.7820 | 0.7549 | 0.7335 |
| fro | **0.7963** | 0.7841 | 0.7562 | 0.6648 | 0.5575 | 0.5056 | 0.4650 |
| anc2 | **0.7963** | 0.7849 | 0.7662 | 0.7108 | 0.6254 | 0.5693 | 0.5433 |
| fro2 | **0.7963** | 0.7832 | 0.7586 | 0.6690 | 0.5095 | 0.4246 | 0.3605 |
| anc_decay | 0.7963 | **0.7973** | 0.7909 | 0.7656 | 0.6221 | 0.4208 | 0.3676 |
| fro_decay | **0.7963** | 0.7882 | 0.7601 | 0.6894 | 0.5281 | 0.4015 | 0.3676 |
| cocite | 0.7281 | 0.7803 | **0.7969** | 0.7963 | 0.7785 | 0.7678 | 0.7596 |
| couple | **0.7963** | 0.7824 | 0.7618 | 0.7055 | 0.6285 | 0.5395 | 0.4700 |
| hub | **0.7963** | 0.7946 | 0.7889 | 0.7376 | 0.6363 | 0.5675 | 0.5155 |

![ladder](figures/ladder_ConsensusMatch.png)

### ConsensusMatch, coordinate descent

| descent | start | tuned | the exponents it stopped at |
| --- | --- | --- | --- |
| from the lattice best | 0.7963 | 0.8000 | anc=1, cocite=1, cos=1.5, rec=1 |
| from the shipped point | 0.6734 | 0.8095 | anc=4, anc_decay=1, cocite=2.5, cos=1.5, fro=0.25, hub=0.25, rec=3 |
| from everything on | 0.5076 | 0.8021 | anc=4, anc2=1, cocite=3, cos=4, fro=0.5, fro_decay=0.25, rec=4 |

## Every exponent moved off its own metric's tuned point

One exponent moves, the rest stay, and the sign test is paired over the cases.
A blank cell is a move that metric's point already sits at.

| move | ConsensusMatch | FrontierMatch | SurveyMatch |
| --- | --- | --- | --- |
| `cos` to 0 | -0.0094 (12W/21L, p=0.163) | -0.0009 (21W/31L, p=0.212) | -0.0014 (19W/39L, p=0.012) |
| `cos` to 0.25 | -0.0093 (10W/22L, p=0.050) | -0.0006 (14W/22L, p=0.243) | -0.0005 (20W/27L, p=0.382) |
| `cos` to 0.5 | -0.0081 (9W/19L, p=0.087) | -0.0002 (13W/14L, p=1.000) | -0.0003 (11W/17L, p=0.345) |
| `rec` to 0 | -0.0652 (17W/67L, p=0.000) | -0.0260 (22W/82L, p=0.000) | -0.0075 (24W/46L, p=0.012) |
| `rec` to 0.25 | -0.0501 (21W/62L, p=0.000) | -0.0184 (24W/76L, p=0.000) | -0.0033 (22W/34L, p=0.141) |
| `rec` to 0.5 | -0.0456 (21W/60L, p=0.000) | -0.0108 (27W/55L, p=0.003) | -0.0010 (20W/28L, p=0.312) |
| `anc` to 0 | -0.2653 (5W/124L, p=0.000) | -0.0347 (20W/146L, p=0.000) | -0.3616 (2W/296L, p=0.000) |
| `anc` to 0.25 | -0.2293 (9W/118L, p=0.000) | -0.0249 (20W/134L, p=0.000) | -0.2453 (2W/285L, p=0.000) |
| `anc` to 0.5 | -0.1900 (11W/107L, p=0.000) | -0.0159 (21W/104L, p=0.000) | -0.1511 (2W/260L, p=0.000) |
| `fro` to 0 | -0.0026 (10W/15L, p=0.424) | -0.0012 (24W/37L, p=0.124) | -0.0012 (19W/32L, p=0.092) |
| `fro` to 0.5 | -0.0064 (9W/18L, p=0.122) | -0.0010 (26W/33L, p=0.435) | -0.0011 (18W/36L, p=0.020) |
| `anc2` to 0.25 | -0.0038 (8W/16L, p=0.152) | -0.0018 (9W/37L, p=0.000) | -0.0024 (9W/37L, p=0.000) |
| `anc2` to 0.5 | -0.0109 (10W/24L, p=0.024) | -0.0045 (11W/51L, p=0.000) | -0.0041 (8W/46L, p=0.000) |
| `fro2` to 0.25 | -0.0074 (8W/20L, p=0.036) | -0.0000 (26W/26L, p=1.000) | -0.0008 (17W/30L, p=0.079) |
| `fro2` to 0.5 | -0.0178 (10W/33L, p=0.001) | -0.0028 (27W/52L, p=0.007) | -0.0029 (14W/56L, p=0.000) |
| `anc_decay` to 0 | -0.0182 (7W/32L, p=0.000) | -0.0014 (13W/28L, p=0.028) |  |
| `anc_decay` to 0.25 | -0.0119 (7W/24L, p=0.003) |  | -0.0003 (3W/8L, p=0.227) |
| `anc_decay` to 0.5 | -0.0080 (6W/19L, p=0.015) | -0.0001 (14W/13L, p=1.000) | -0.0009 (2W/16L, p=0.001) |
| `fro_decay` to 0.25 | -0.0077 (5W/18L, p=0.011) | -0.0005 (25W/32L, p=0.427) | -0.0010 (22W/37L, p=0.067) |
| `fro_decay` to 0.5 | -0.0175 (6W/32L, p=0.000) | -0.0040 (23W/52L, p=0.001) | -0.0037 (21W/61L, p=0.000) |
| `cocite` to 0 | -0.0291 (16W/48L, p=0.000) | -0.0714 (9W/199L, p=0.000) | -0.0013 (17W/44L, p=0.001) |
| `cocite` to 0.25 | -0.0243 (15W/44L, p=0.000) | -0.0529 (12W/177L, p=0.000) | -0.0002 (16W/23L, p=0.337) |
| `cocite` to 0.5 | -0.0172 (15W/38L, p=0.002) | -0.0390 (16W/154L, p=0.000) |  |
| `couple` to 0.25 | -0.0075 (5W/17L, p=0.017) | -0.0007 (21W/28L, p=0.392) | -0.0015 (14W/42L, p=0.000) |
| `couple` to 0.5 | -0.0174 (7W/30L, p=0.000) | -0.0024 (26W/48L, p=0.014) | -0.0037 (15W/62L, p=0.000) |
| `hub` to 0 | -0.0027 (5W/11L, p=0.210) | -0.0108 (16W/82L, p=0.000) | -0.0017 (20W/32L, p=0.126) |
| `hub` to 0.25 |  | -0.0096 (16W/76L, p=0.000) | -0.0009 (11W/23L, p=0.058) |
| `hub` to 0.5 | -0.0038 (3W/9L, p=0.146) | -0.0073 (16W/65L, p=0.000) |  |

## What the benchmark reported, running the production code path

Written by `scripts/evaluate_retrieval/stage{0..3}` into `experiments/retrieve/`.
The headline is recall@1000, except ConsensusMatch which saturates there and is
reported at 100.

| metric | recipe | cases | headline | ceiling | seconds |
| --- | --- | --- | --- | --- | --- |
| ConsensusMatch | all_terms | 151 | 0.5076 | 0.9928 | 0.72 |
| ConsensusMatch | consensus | 151 | 0.8095 | 0.9928 | 0.73 |
| ConsensusMatch | consensus_no_forward | 151 | 0.8068 | 0.9928 | 0.72 |
| ConsensusMatch | cosine_only | 151 | 0.2690 | 0.8042 | 0.40 |
| ConsensusMatch | survey | 151 | 0.7428 | 0.9928 | 0.72 |
| FrontierMatch | all_terms | 300 | 0.6659 | 0.8159 | 0.92 |
| FrontierMatch | cosine_only | 300 | 0.3758 | 0.6010 | 0.51 |
| FrontierMatch | frontier | 300 | 0.7698 | 0.8159 | 0.95 |
| FrontierMatch | frontier_no_forward | 300 | 0.7686 | 0.8159 | 0.92 |
| FrontierMatch | survey | 300 | 0.7259 | 0.8159 | 0.92 |
| PrecisionMatch | cosine_only | 300 | 0.1876 | 0.1876 | 0.63 |
| PrecisionMatch | frontier | 300 | 0.2792 | 0.2792 | 0.99 |
| PrecisionMatch | survey | 300 | 0.2829 | 0.2829 | 1.00 |
| SurveyMatch | all_terms | 300 | 0.6416 | 0.8309 | 0.77 |
| SurveyMatch | anc_only | 300 | 0.8000 | 0.8309 | 0.77 |
| SurveyMatch | cosine_only | 300 | 0.3698 | 0.5660 | 0.46 |
| SurveyMatch | no_expansion | 300 | 0.4749 | 0.5660 | 0.49 |
| SurveyMatch | survey | 300 | 0.8123 | 0.8309 | 0.78 |
| SurveyMatch | survey_no_forward | 300 | 0.8111 | 0.8309 | 0.77 |
