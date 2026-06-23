# test-time compute and reasoning in large language models

*effort standard · pool 431 · landmarks 80 · schema ['reasoning_method', 'inference_mechanism', 'reasoning_domain', 'scaling_effect', 'evaluation_benchmark', 'scaling_tradeoff'] · grounded 33 · off-digest 0*

---

# Literature Review: Test-Time Compute and Reasoning in Large Language Models

The evolution of reasoning in Large Language Models (LLMs) has transitioned from optimizing training-time scaling laws to a sophisticated frontier of optimizing test-time compute. This review traces the development from foundational transformer architectures to modern methods that utilize search, verification, and reinforcement learning to enhance reasoning capabilities.

## Origins: Foundations of Scaling and Attention (2017–2020)

The trajectory begins with the architectural foundation of the Transformer, established in arXiv:1706.03762, which revolutionized machine translation and English constituency parsing. This architecture enabled the development of scaling laws; arXiv:2001.08361 demonstrated that model loss scales as a power-law with model size, dataset size, and training compute, suggesting an optimal allocation of fixed compute budgets.

Building on these scaling principles, arXiv:2005.14165 demonstrated that scaling up language models significantly improves task-agnostic, few-shot performance across domains like arithmetic and question-answering through text-based demonstrations. This era also established critical evaluation frameworks, such as the MMLU benchmark for multitask understanding (arXiv:2009.03300) and the CommonsenseQA dataset (arXiv:1811.00937). Early efforts to align models with human intent, such as learning to summarize from human feedback (arXiv:2009.01325), laid the groundwork for subsequent instruction-following and reinforcement learning paradigms.

## Key Advances: Prompting, Verifiers, and Intermediate Computation (2020–2022)

As models grew, research shifted toward eliciting reasoning through specialized inference mechanisms. A major breakthrough occurred with Chain-of-Thought (CoT) prompting (arXiv:2201.11903), which improved performance in arithmetic and symbolic reasoning by encouraging step-by-step reasoning. This was further refined by "Zero-shot CoT" (arXiv:2205.11916), which uses the prompt "Let's think step by step" to elicit reasoning without explicit demonstrations.

Parallel to prompting, researchers explored increasing test-time compute through sampling and verification:
* **Sampling and Consistency:** arXiv:2203.11171 introduced "Self-Consistency," which improves CoT reasoning by sampling diverse reasoning paths and selecting the most consistent answer via marginalization. Similarly, arXiv:2107.03374 showed that repeated sampling could achieve a 70.2% success rate in Python code-writing on the HumanEval benchmark.
* **Intermediate Computation:** arXiv:2112.00114 introduced "scratchpads" for multi-step computations, providing a structured space for intermediate reasoning steps.
* **Verification Mechanisms:** To move beyond simple sampling, arXiv:2110.14168 proposed training verifiers to judge the correctness of candidate solutions in math word problems, noting that verification scales more effectively with data than standard finetuning. This concept was extended by arXiv:2206.02336, which utilized a "step-aware verifier" and a weighted voting scheme to improve arithmetic reasoning.

During this period, the limitations of scaling were also identified. arXiv:2103.03874 noted that accuracy in mathematics remains relatively low even with enormous Transformer models, suggesting that simply increasing parameter counts is an impractical path to strong mathematical reasoning.

## Current Frontier: Search, Process Supervision, and Test-Time Scaling (2022–2025)

The current frontier focuses on treating reasoning as a search and planning problem, often utilizing "test-time compute" to outperform larger models.

### Search and Planning Paradigms
Recent advances have moved from linear CoT to complex tree and graph structures. The "Tree of Thoughts" (ToT) framework (arXiv:2305.10601) enables deliberate problem-solving by exploring multiple reasoning paths and backtracking. This was expanded by "Graph of Thoughts" (GoT) (arXiv:2308.09687), which improves sorting quality by 62% over ToT while reducing costs. Other methods, such as "Reasoning via Planning" (RAP) (arXiv:2305.14992), utilize Monte Carlo Tree Search (MCTS) to balance exploration and exploitation in logical inference.

### Process Supervision and Reward Models
A pivotal shift has occurred from outcome-based feedback to process-based supervision. arXiv:2305.20050 introduced process supervision to verify individual steps in mathematics. This has been refined by "Math-Shepherd" (arXiv:2312.08935), which uses step-by-step PPO to reinforce models without human annotations, and "ReST-MCTS*" (arXiv:2406.03816), which uses process rewards to guide tree search. Recent findings suggest that searching against Process Advantage Verifiers (PAVs) is 1.5–5x more compute-efficient than using Outcome Reward Models (ORMs) (arXiv:2410.08146).

### The Test-Time Compute Scaling Law
The most significant recent discovery is the explicit scaling law for inference. arXiv:2408.00724 and arXiv:2408.03314 demonstrate that scaling inference compute (via strategies like majority voting, best-of-N, or tree search) can be more efficient than scaling model parameters; for instance, a smaller model with advanced inference can outperform a model 14x its size (arXiv:2408.03314). This is exemplified by the ability of 1B models to potentially surpass 405B models through compute-optimal test-time scaling (arXiv:2502.06703).

### Reinforcement Learning and Self-Improvement
Modern models like DeepSeek-R1 (arXiv:2501.12948) and Kimi k1.5 (arXiv:2501.12599) utilize pure reinforcement learning or long-CoT to incentivize reasoning capabilities in STEM fields. Other approaches, such as V-STaR (arXiv:2402.06457), use self-improvement by fine-tuning on correct and incorrect solutions via DPO.

## Tensions and Open Problems

Despite these advances, several tensions remain in the literature:
* **The "Overthinking" Problem:** While more compute generally helps, arXiv:2412.21187 argues that excessive computational resources for simple problems (e.g., "2+3=?") yield minimal benefit, a phenomenon termed "overthinking."
* **Self-Correction Limits:** There is significant debate regarding the ability of models to self-correct. While some propose iterative refinement (arXiv:2303.17651), others argue that LLMs cannot yet perform intrinsic self-correction effectively (arXiv:2310.01798).
* **Efficiency vs. Accuracy:** A central tension exists in balancing the length of reasoning (token budget) against accuracy. Recent work explores "Length-Harmonizing Fine-Tuning" (arXiv:2501.12570) and "Token-Budget-Aware" reasoning (arXiv:2412.18547) to manage this tradeoff.
* **Data Efficiency:** While scaling laws emphasize massive datasets, arXiv:2502.03387 (LIMO) suggests that sophisticated reasoning can emerge using only 1% of the training data required by prior approaches, highlighting a potential shift from quantity to quality in training.