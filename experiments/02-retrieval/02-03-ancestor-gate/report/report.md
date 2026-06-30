# Experiment — Ancestor relevance gate

*Retrieval · plugging the one mechanism through which off-topic noise enters the subgraph.*

## What we did

`02-02` found ~22% of landmarks off-topic AND carrying high in-degree (5.4) — famous cross-field hubs (GPT-3 / StyleGAN under "diffusion"). They enter through one mechanism: `augment_with_ancestors` → `store.ancestors` pulls the top-120 **most-cited** one-hop-back papers (ranked by citer count *before* cosine), so fame beats relevance. We gate that injection by a cosine floor and measure **both** sides of the tradeoff:

- **precision** = LLM `relevance_rate` (1 − unrelated) over all **27** topics (reuses the `02-02` role-judge cache — labels are retrieval-independent, so only newly-introduced landmarks cost a call).
- **recall** = `landmark_recall` + `spine_recall` over the **3 gold** topics (set membership, no LLM).

Swept: `baseline` (no floor), `floor35` (0.35), `floor45` (0.45), `floor45_cat` (0.45 + modal-category match). Only the **injected ancestors** are gated; the core hybrid pool and cosine-gated `frontier_pull` are untouched.

## Results

| variant | precision (27) | unrelated | landmark_recall (gold-3) | spine_recall (gold-3) |
|---|--:|--:|--:|--:|
| baseline | 0.781 | 0.219 | 0.742 | 0.917 |
| **floor35** | **0.837** | 0.163 | **0.808** | **1.000** |
| floor45 | 0.896 | 0.104 | 0.522 | 0.600 |
| floor45_cat | 0.902 | 0.098 | 0.522 | 0.600 |

![ablation](../results/ablation.png)

## Conclusion

The tradeoff is **floor-dependent**:

- **A gentle floor (0.35) is a Pareto win, not a tradeoff.** Precision +5.6 pts (robust, n=27) *and* gold recall up (0.742→0.808, spine →1.0). Removing clearly-off-topic ancestors (cosine < 0.35) frees PPR's 40 landmark slots for on-topic papers instead of famous hubs — both metrics rise together.
- **An aggressive floor (0.45) is the real tradeoff.** Precision climbs to 0.896 but gold recall collapses to 0.522 (spine 0.6): 0.45 starts cutting genuine low-cosine foundational papers (VAE / Sohl-Dickstein sit ~0.4–0.5). Not worth it.
- **The category gate adds ~nothing** (0.896 → 0.902); drop it.

**Verdict:** a `min_cosine ≈ 0.35` floor on `augment_with_ancestors` is worth promoting to production — a low-risk Pareto improvement. The aggressive floor is "a fair tradeoff worth discussing, not shipping."

## Caveats

Recall is n=3 gold; precision is n=27. The mechanism (0.35 ≪ foundational cosine) makes the no-recall-loss claim sound, but a wider gold set would harden it.
