| arm | gold_recall | generic_frac | specific_retained | bg_mean |
| --- | --- | --- | --- | --- |
| none | 0.808 | 0.608 | 0.448 | 0.574 |
| lift | 0.742 | 0.504 | 0.566 | 0.598 |
| pr_ratio | 0.686 | 0.443 | 0.659 | 0.579 |
| pop_bg3 | 0.808 | 0.599 | 0.463 | 0.565 |
| pop_bg5 | 0.808 | 0.595 | 0.467 | 0.556 |
| pop_bg7 | 0.808 | 0.584 | 0.479 | 0.545 |
| pop_bg10 | 0.742 | 0.543 | 0.529 | 0.521 |

_gold_recall must HOLD (tripwire); generic_frac DOWN + specific_retained UP per the independent oracle. pop_bg holds recall (s<=0.7) but is gentle; topic-blind pr_ratio moves the oracle most but costs recall -- no structural silver bullet, so the shipped fix is the compose guard (see report)._
