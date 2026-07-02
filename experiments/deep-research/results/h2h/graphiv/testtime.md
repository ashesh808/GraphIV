*deep research · 1 round(s) · 120 landmarks · frontier≥2025: 52 · 4 full-PDF critiques · grounded 52 · off-digest 0*

# The Evolution of Inference-Time Intelligence: From Chain-of-Thought to Test-Time Scaling Laws

The pursuit of artificial general intelligence has increasingly focused on the capacity of large language models (LLMs) to perform complex, multi-step reasoning. While traditional scaling laws emphasized the importance of increasing parameter counts and training data, a fundamental limitation remains: the tendency of autoregressive models to struggle with tasks requiring deep logical deliberation. This gap has necessitated a shift in focus from how models are trained to how they are utilized during inference. Understanding this transition is critical, as the ability to allocate additional computational resources at the moment of prediction—test-time compute—represents a potential new frontier for enhancing model accuracy, reliability, and problem-solving depth.

This review traces the trajectory of this development, beginning with the *Foundations of LLM Reasoning: From Prompting to Chain-of-Thought*, which established the initial methods for eliciting step-by-step logic. We then examine the *Methodological Advances in Verifiers and Iterative Refinement* that introduced self-correction mechanisms, followed by the move toward *Structured Search and Tree-Based Reasoning Paradigms* that allow for non-linear exploration of solution spaces. Central to this evolution is the conceptual shift detailed in *Scaling Laws and the Transition to Test-Time Compute*, where the emphasis moves from pre-training scale to inference-time expenditure.

The review further explores how *Reinforcement Learning and the Rise of Reasoning Models* have provided the training frameworks necessary to optimize these inference-time behaviors. We conclude by surveying the *Current Frontiers: Multimodal, Agentic, and Domain-Specific Scaling*, while critically assessing the *Systemic Challenges: Efficiency, Limits, and Evaluation of Test-Time Scaling* that must be overcome to realize the full potential of compute-augmented reasoning.

## Foundations of LLM Reasoning: From Prompting to Chain-of-Thought

The development of reasoning in large language models (LLMs) has transitioned from standard input-output prompting toward sophisticated methods that augment model outputs with intermediate cognitive steps. The foundational shift in this paradigm was established by arXiv:2201.11903, which introduced "chain-of-thought (CoT) prompting." By providing intermediate natural language reasoning steps within few-shot exemplars, this method elicits reasoning abilities in arithmetic, commonsense, and symbolic domains without requiring fine-tuning. A significant strength of this approach is that CoT is an emergent property of scale; for instance, PaLM 540B achieved state-of-the-art accuracy on the GSM8K benchmark, even surpassing fine-tuned models arXiv:2201.11903. However, a critical limitation is that the method does not definitively prove the model is performing true reasoning rather than merely mimicking a linguistic process, and the increased token generation makes it computationally expensive to serve arXiv:2201.11903.

Subsequent research focused on refining these prompting strategies to improve reliability and reduce manual effort. While arXiv:2201.11903 relies on manual few-shot exemplars, arXiv:2210.03493 introduced "Automatic Chain of Thought Prompting" (Auto-CoT), which automates the construction of these demonstrations across various reasoning domains arXiv:2210.03493. To address the potential for errors in a single reasoning path, arXiv:2203.11171 proposed "self-consistency," a strategy that samples a diverse set of reasoning paths and marginalizes them to select the most consistent answer, thereby improving performance on complex arithmetic and commonsense tasks arXiv:2203.11171. This move toward sampling multiple paths represents an early shift toward utilizing more compute at test-time to ensure accuracy.

Further advancements sought to handle increasing task complexity through structural decomposition. arXiv:2205.10625 introduced "least-to-most prompting," which enables models to tackle complex problems by decomposing them into a sequence of simpler subproblems arXiv:2205.10625. Parallel to this, researchers explored disentangling linguistic reasoning from precise computation. While standard CoT can struggle with exact numerical accuracy, arXiv:2211.12588 (Program of Thoughts) and arXiv:2211.10435 (PAL) proposed program-aided reasoning paradigms. These methods decompose problems into steps and execute them via a programming language interpreter, effectively offloading the computational burden from the LLM's linguistic generation to a formal execution environment arXiv:2211.12588, arXiv:2211.10435. Finally, the scope of CoT was expanded to zero-shot settings by arXiv:2205.11916, demonstrating that reasoning capabilities could be elicited even without explicit few-shot exemplars across diverse datasets like SVAMP and AQUA-RAT arXiv:2205.11916.

## Methodological Advances in Verifiers and Iterative Refinement

The evolution of test-time compute has transitioned from simple outcome-based selection to sophisticated, step-by-step verification and iterative self-correction. Early methodological foundations were established by arXiv:2110.14168, which introduced the "generate-and-rank" paradigm. This approach uses a separate verifier to rank multiple high-temperature completions for math word problems, a method that demonstrates significant scaling advantages; specifically, verification can provide a performance boost equivalent to a 30x increase in model size. However, this paradigm faces limitations in efficiency and robustness, as performance tends to decay after 400 completions, likely because the verifier can be misled by adversarial solutions arXiv:2110.14168.

To address the limitations of outcome-based supervision, research has shifted toward process-oriented reward modeling (PRM). arXiv:2305.20050 highlights this distinction, contrasting outcome supervision (ORM) with process supervision (PRM) to improve mathematical reasoning on benchmarks like MATH. This move toward granular verification is further refined by arXiv:2312.08935, which introduces "Math-Shepherd." This method automates the process by providing step-by-step verification and reinforcement without requiring human annotations, utilizing a best-of-N selection strategy to enhance reasoning across GSM8K and MATH datasets. Building on these concepts, arXiv:2408.15240 proposes a generative approach to reward modeling, treating reward modeling as a next-token prediction task within a best-of-N sampling framework, further integrating verification into the generative process itself.

Parallel to these verification advancements is the development of iterative refinement and self-correction mechanisms. Unlike the ranking-based strategies of arXiv:2110.14168, arXiv:2303.17651 proposes a "Self-Refine" paradigm where a model uses its own feedback to iteratively improve its outputs across diverse tasks, including math and code, through up to four iterations of controllable compute. In the domain of code generation, arXiv:2304.05128 advances this by introducing self-debugging, where models investigate execution results and natural language explanations to correct errors in tasks like text-to-SQL and Python generation.

While verification-based methods like arXiv:2305.20050 and arXiv:2312.08935 focus on selecting the best existing path through external or automated scoring, iterative methods like arXiv:2303.17651 and arXiv:2304.05128 focus on the model's ability to actively modify its reasoning trajectory. Together, these advancements represent a shift from merely selecting high-quality outputs to actively constructing and refining them through increased test-time computation.

## Structured Search and Tree-Based Reasoning Paradigms

The evolution of test-time compute has transitioned from simple linear chain-of-thought prompting toward sophisticated structured search paradigms that allow models to explore multiple reasoning trajectories. A foundational advancement in this direction is the Tree of Thoughts (ToT) framework, which introduces deliberate search within trees of thoughts to solve complex mathematical, symbolic, and commonsense reasoning tasks [arXiv:2305.10601]. Unlike standard autoregressive decoding, ToT employs an adaptive compute control mechanism, utilizing thought generation and evaluation to navigate problem spaces, such as the Game of 24 [arXiv:2305.10601].

Building upon these tree-based structures, research has sought to increase the complexity of information dependencies. The Graph of Thoughts (GoT) framework extends the tree paradigm by modeling information as an arbitrary directed graph $G = (V, E)$ [arXiv:2308.09687]. While ToT is limited by its hierarchical branching, GoT allows for non-linear dependencies and thought transformations, such as the aggregation of multiple thought vertices into a single refined state [arXiv:2308.09687]. Notably, while ToT utilizes adaptive compute, GoT studies often employ fixed compute constraints to ensure comparable costs during evaluation [arXiv:2308.09687].

The integration of reinforcement learning-inspired search algorithms has further refined these paradigms. For instance, AlphaZero-like tree-search can be utilized to guide both the decoding and the training of LLMs, applying these methods to domains ranging from chess endgames to mathematical planning [arXiv:2309.17179]. This is complemented by stepwise self-evaluation mechanisms, such as the stochastic beam search approach [arXiv:2305.00633], which uses internal calibration to guide multi-step reasoning in math and commonsense tasks [arXiv:2305.00633].

Recent frontiers in the field are shifting toward latent-space reasoning and hierarchical search. One approach moves away from explicit token-level search toward latent recurrent thinking, where a recurrent block is unrolled to arbitrary depth in latent space to scale test-time compute adaptively [arXiv:2502.05171]. Simultaneously, other researchers have integrated external knowledge into classical search algorithms through hierarchical retrieval-augmented Monte Carlo Tree Search (MCTS) [arXiv:2507.05557]. This method enhances mathematical reasoning by combining MCTS with DLR reference sets, providing a more robust framework for solving high-level mathematics benchmarks like MATH500 and OlympiadBench-TO [arXiv:2507.05557]. Together, these developments represent a trajectory from explicit, discrete thought branching toward integrated, latent, and retrieval-augmented search architectures.

## Scaling Laws and the Transition to Test-Time Compute

The evolution of large language model (LLM) development is currently undergoing a paradigm shift from scaling model parameters to scaling inference-time computation. This transition is characterized by a move from "System-1" intuitive inference—involving techniques like input modification or output calibration—toward "System-2" deliberate reasoning, which utilizes increased test-time compute (TTS) to solve complex problems (arXiv:2501.02497).

Early methodological advancements in this area focused on structured search patterns. For instance, arXiv:2408.00724 introduced the REBASE method, which utilizes tree search to scale inference-time compute specifically for mathematical problem-solving, demonstrating empirical scaling laws on benchmarks such as MATH and GSM8K. This approach treats reasoning as a search process, a concept further expanded in recent surveys that categorize test-time enhancements through techniques like tree search and reflective thinking to bolster performance in mathematics, coding, and scientific domains (arXiv:2501.09686).

A critical tension in current research involves the trade-off between model size and inference compute. While traditional scaling laws emphasize parameter count, recent work suggests that scaling LLM test-time compute optimally can be more effective than simply scaling model parameters (arXiv:2408.03314). This is exemplified by the provocative finding that a 1B parameter model can potentially surpass a 405B parameter model by leveraging reward-aware, compute-optimal TTS strategies (arXiv:2502.06703). Unlike fixed compute strategies, this approach utilizes adaptive compute control through policy models and Process Reward Models (PRMs) to optimize performance on challenging benchmarks like AIME24 and MATH-500 (arXiv:2502.06703).

However, the literature reveals a divergence in how compute is applied. Some research continues to focus on single-pass, full Chain-of-Thought (CoT) decoding under fixed compute constraints to establish compute-accuracy Pareto frontiers across diverse scientific reasoning tasks (arXiv:2512.24776). In contrast, the frontier of "Large Reasoning Models" is moving toward reinforced reasoning, where models utilize intermediate "thought" tokens to facilitate more complex problem-solving in PhD-level science and International Mathematics Olympiad (IMO) contexts (arXiv:2501.09686). Collectively, these papers indicate that the frontier of LLM capability is no longer solely defined by the static size of the weights, but by the dynamic allocation of computational resources during the inference phase.

## Reinforcement Learning and the Rise of Reasoning Models

The current research frontier is defined by a shift toward incentivizing complex reasoning through reinforcement learning (RL), moving beyond simple next-token prediction to encourage the generation of extended chains-of-thought (CoT). This paradigm is exemplified by the OpenAI o1 system, which utilizes large-scale RL to produce long CoT for complex reasoning, coding, and safety alignment tasks [arXiv:2412.16720]. Building on this trajectory, DeepSeek-R1 further advances the field by applying RL to incentivize reasoning capabilities across math, coding, and general reasoning domains [arXiv:2501.12948]. While both represent the frontier of RL-driven reasoning, DeepSeek-R1 provides a broader evaluative scope, demonstrating performance across diverse benchmarks including MMLU-Pro, GPQA Diamond, and SWE-Bench Verified [arXiv:2501.12948], whereas the o1 system card focuses heavily on safety alignment and jailbreak evaluations [arXiv:2412.16720].

A parallel development in this frontier is the scaling of RL to enable models to explore via rewards, as seen in Kimi k1.5 [arXiv:2501.12599]. Unlike models restricted to text, Kimi k1.5 extends the Long-CoT paradigm to multimodal domains, including vision and math-vision tasks [arXiv:2501.12599]. This scaling approach contrasts with earlier methodological advancements that focused on specific reasoning behaviors. For instance, arXiv:2409.12917 introduced multi-turn online RL specifically to train models to self-correct in math and coding, employing regularization to prevent behavior collapse [arXiv:2409.12917]. While self-correction is a vital component of reasoning, the recent frontier models like DeepSeek-R1 [arXiv:2501.12948] and Kimi k1.5 [arXiv:2501.12599] appear to integrate these capabilities into a more holistic, large-scale RL framework that prioritizes long-form exploration.

The transition from methodological refinement to frontier scaling is also marked by different approaches to data. While the frontier models rely on massive RL-driven exploration, the s1 model represents a methodological advancement that achieves test-time scaling through supervised finetuning (SFT) on reasoning traces, specifically using the s1K dataset [arXiv:2501.19393]. This provides a streamlined alternative to the heavy RL requirements of o1 or DeepSeek-R1, focusing specifically on mathematical problem-solving [arXiv:2501.19393]. However, the field remains divided between the high-compute, RL-intensive exploration strategies of Kimi k1.5 and DeepSeek-R1 [arXiv:2501.12599, arXiv:2501.12948] and the more efficient, trace-based supervised scaling seen in s1 [arXiv:2501.19393]. Together, these works illustrate a landscape where the primary lever for increasing reasoning capability is the strategic application of RL to facilitate extended, self-directed cognitive processes.

## Current Frontiers: Multimodal, Agentic, and Domain-Specific Scaling

The current research frontier is characterized by a shift from general language reasoning toward specialized domains, including multimodal perception, agentic task execution, and high-precision scientific reasoning. A primary development in this space is the expansion of test-time scaling (TTS) into multimodal foundation models (MFMs). arXiv:2606.08231 provides the first systematic survey of this transition, moving beyond LLM-centric paradigms by establishing a formal mathematical distinction between TTS and memory via a tripartite taxonomy of sampling, feedback, and search. While this survey offers a robust framework for understanding multimodal reasoning and generation, the field is simultaneously exploring specific mechanisms to improve visual-language performance. For instance, arXiv:2605.30713 emphasizes that diversity is critical in vision-language models, proposing Entropy-based TTC (ETTC) and multi-model ensembles to enhance visual reasoning across six benchmarks, contrasting with more traditional majority voting approaches.

Parallel to the multimodal expansion is the integration of TTS within agentic frameworks. Rather than focusing solely on single-turn reasoning, arXiv:2506.12928 explores how scaling compute can facilitate end-to-end task solving through tools and multi-agent collaboration. This work utilizes diverse strategies such as parallel sampling (including Best-of-N and Beam-Search), sequential revision, and the use of verifiers to merge rollouts, effectively treating the agent's reasoning process as a scalable computational resource.

The frontier also extends into highly specialized scientific and professional domains, where the nature of "reasoning" requires different scaling strategies. In the medical domain, arXiv:2506.13102 investigates model- and task-aware strategies for LLMs and VLMs, specifically focusing on increasing the token budget to improve performance in medical QA and calculations across datasets like PubMedQA and MedQA. This emphasis on token budget contrasts with the symbolic verification approaches seen in theoretical physics. In the physics domain, arXiv:2506.20729 evaluates both sequential and parallel scaling (such as Best-of-N) using a SymPy-augmented verifier to handle mathematical reasoning on the TPBench and AIME datasets.

Finally, scaling is being leveraged to overcome linguistic barriers. arXiv:2505.05408 demonstrates that multilingual mathematical reasoning can be enhanced by scaling inference compute through long chain-of-thought (CoT) processes, specifically using English-centric reasoning finetuning to drive crosslingual performance. Collectively, these works indicate that the next stage of TTS development is moving away from monolithic scaling toward adaptive, domain-aware, and modality-specific implementations.

## Systemic Challenges: Efficiency, Limits, and Evaluation of Test-Time Scaling

As test-time scaling (TTS) transitions from foundational concepts to a complex research frontier, the literature reveals a critical tension between reasoning performance and the systemic costs of computation. While early foundational work established that increasing test-time compute (TTC)—either by expanding input tokens or output tokens—can enhance reasoning in mathematical, coding, and common-sense domains (arXiv:2505.14733), recent scholarship suggests that simply scaling compute is insufficient for sustained progress.

A primary concern in the current frontier is the existence of performance plateaus. Research exploring internal TTS in mathematical and science-domain reasoning suggests that scaling does not yield infinite returns, a phenomenon observed across benchmarks such as AIME 2024/2025, MATH-500, and GPQA (arXiv:2505.20522). This limitation necessitates a shift from brute-force scaling toward more structured methodologies. For instance, rather than uniform compute allocation, recent surveys propose a subproblem structure perspective, where compute is strategically allocated via sequential, parallel, or tree-structured decomposition (e.g., Chain-of-Thought or Tree-of-Thought) across textual and multimodal domains (arXiv:2511.14772).

This move toward structural efficiency is further refined by the need for "adaptive and controllable" TTC. Rather than static scaling, a two-tiered framework has emerged to provide L1 controllability and L2 adaptiveness, allowing models to modulate compute across domains ranging from coding to mobile robotic manipulation (arXiv:2507.02076). However, the effectiveness of these adaptive strategies relies heavily on the quality of verification. The literature distinguishes between process-based and outcome-based verification paradigms, where employing a verifier to explore the decoding search space is essential for navigating complex reasoning paths (arXiv:2508.16665).

Despite these methodological advances, significant systemic challenges regarding efficiency and evaluation persist. There is a growing call for a "system perspective" on TTS that moves beyond mere accuracy to prioritize practical benchmarks like latency and cost-per-token (arXiv:2509.19645). This is particularly urgent given the documented energy costs associated with increasing token counts during inference (arXiv:2505.14733). Consequently, the research frontier is increasingly defined by a multi-dimensional optimization problem: balancing the structural advantages of subproblem decomposition (arXiv:2511.14772) and adaptive control (arXiv:2507.02076) against the hard constraints of energy consumption, latency, and the inevitable performance plateaus encountered in high-level reasoning tasks (arXiv:2505.20522, arXiv:2509.19645).

## Tensions and Open Problems

A fundamental rift persists regarding the optimal mechanism for eliciting complex reasoning: whether it should be driven by structured prompting or emergent reinforcement learning. On one hand, early paradigms relied heavily on prompting strategies like Chain-of-Thought (arXiv:2201.11903) or automated prompting methods (arXiv:2210.03493) to guide the model's internal logic. However, recent work such as arXiv:2503.09567 suggests that these prompting-based approaches may be insufficient compared to the transformative impact of large-scale reinforcement learning, as seen in the incentivized reasoning capabilities of DeepSeek-R1 (arXiv:2501.12948). This tension extends to the very nature of the reasoning process itself; while some argue that reasoning is essentially a form of planning with an internal world model (arXiv:2305.14992), others contend that the true frontier lies in scaling the length and depth of the reasoning chain through specialized training regimes (arXiv:2503.09567).

Another critical debate centers on the efficacy and reliability of self-correction during inference. There is significant skepticism regarding the ability of models to autonomously rectify errors, with studies suggesting that LLMs currently struggle to self-correct reasoning trajectories effectively (arXiv:2310.01798). This skepticism is challenged by more recent investigations into "o1-like" models, which argue that through specific reinforcement learning frameworks (arXiv:2409.12917), models can indeed be trained to self-correct, thereby unlocking new scaling laws at test-time (arXiv:2502.12215). This disagreement highlights a lack of consensus on whether self-correction is an inherent capability that can be unlocked via "bag of tricks" inference-time computation (arXiv:2502.07191) or a fundamental architectural limitation that requires systemic retraining.

Finally, the community is divided on how to optimally allocate compute between training and inference. Traditional scaling laws have long emphasized the importance of pre-training compute (arXiv:2001.08361; arXiv:2203.15556), yet the emergence of reasoning-heavy models suggests a paradigm shift. Recent critiques argue that these classical scaling laws fail to account for the massive gains achievable by scaling reinforcement learning (arXiv:2501.12599) and, more importantly, by scaling test-time compute (arXiv:2502.06703). While some researchers focus on maximizing the efficiency of inference-time scaling (arXiv:2408.03314), others warn that simply repeating or scaling inference compute may be less effective than more sophisticated, adaptive methods of test-time computation (arXiv:2407.21787).

### Outlook

The field is rapidly transitioning from a "pre-training centric" era to a "test-time compute" era, where the frontier lies in the intelligent orchestration of reasoning-at-inference. As we move toward 2026, the focus is shifting from static prompting to dynamic, adaptive scaling—where models must decide how much "thought" to expend based on task complexity (arXiv:2507.02076). The next major breakthroughs are expected to emerge from the integration of multimodal reasoning (arXiv:2606.08231), the development of structured "periodic tables" of reasoning failure modes (arXiv:2606.11470), and the evolution of LLM agents that can autonomously manage their own computational budgets during complex, multi-step tasks (arXiv:2512.02008).

---

## Key Figures

**Chain-of-Thought Prompting Elicits Reasoning in Large Language Models** — arXiv:2201.11903 p.1

![2201.11903](figures/2201.11903_p1.png)

The figure compares "Standard Prompting" and "Chain-of-Thought Prompting" through two side-by-side examples of math word problems. Each example consists of a "Model Input" box containing a question and a "Model Output" box containing the answer, with the Chain-of-Thought version featuring a blue-highlighted intermediate reasoning step. The figure conveys that standard prompting leads to an incorrect answer (27), whereas chain-of-thought prompting enables the model to reach the correct answer (9) by showing its work.

**Training Verifiers to Solve Math Word Problems** — arXiv:2110.14168 p.2

![2110.14168](figures/2110.14168_p2.png)

The figure displays three text boxes, each containing a math word problem, its step-by-step solution, and a final answer. Within the solutions, specific numerical calculations are highlighted in red text to denote calculation annotations.

**DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning** — arXiv:2501.12948 p.4

![2501.12948](figures/2501.12948_p4.png)

Figure 1 consists of two line graphs plotted against "Steps" on the x-axis. The left graph shows "Accuracy" on the y-axis, comparing the "r1-zero-pass@1" and "r1-zero-cons@16" metrics against a horizontal dashed line representing "human participants." The right graph shows "Average length per response" on the y-axis, illustrating a steady upward trend in response length as training steps increase.

**Self-Consistency Improves Chain of Thought Reasoning in Language Models** — arXiv:2203.11171 p.1

![2203.11171](figures/2203.11171_p1.png)

The figure illustrates the self-consistency method using a mathematical word problem as an example. It shows a single question branching into multiple "Chain-of-Thought" reasoning paths via arrows, each leading to a different final answer, which are then aggregated to identify the most frequent (consistent) answer.

**Measuring Mathematical Problem Solving With the MATH Dataset** — arXiv:2103.03874 p.2

![2103.03874](figures/2103.03874_p2.png)

The figure is divided into two columns comparing "Metamath Theorem Proving" and the "MATH Dataset (Ours)." The left column displays formal logic proofs and simple arithmetic problems, while the right column presents competition-level mathematical problems accompanied by step-by-step natural language solutions and boxed final answers. The figure conveys that while previous datasets focus on formal proofs or plug-and-chug arithmetic, the new MATH dataset focuses on complex problem-solving with multi-step reasoning.

**Scaling LLM Test-Time Compute Optimally can be More Effective than
  Scaling Model Parameters** — arXiv:2408.03314 p.2

![2408.03314](figures/2408.03314_p2.png)

The figure consists of two side-by-side panels comparing compute-optimal scaling strategies. The left panel is a line graph showing MATH Accuracy (%) versus Generation Budget, plotting four curves (Majority, CRM Best-of-N Weighted, PRM Best-of-N Weighted, and PRM Compute Optimal) to demonstrate that compute-optimal scaling outperforms best-of-N scaling. The right panel is a grouped bar chart showing Relative Improvement in Test-Time Compute (%) across different ratios of Inference Tokens to Pretraining Tokens, categorized by question difficulty (Easy, Medium, Hard), to convey how test-time compute effectiveness varies based on the pretraining-to-inference ratio.

**Tree of Thoughts: Deliberate Problem Solving with Large Language Models** — arXiv:2305.10601 p.2

![2305.10601](figures/2305.10601_p2.png)

The figure uses ovals for "Input" and "Output" and rectangles for "thought" steps to compare four prompting methods: Input-Output (IO), Chain of Thought (CoT), Self-Consistency with CoT (CoT-SC), and Tree of Thoughts (ToT). While IO and CoT show linear paths and CoT-SC uses a majority vote of multiple paths, the ToT diagram illustrates a branching structure where multiple thoughts are generated and evaluated to navigate toward an output.

**DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open
  Language Models** — arXiv:2402.03300 p.1

![2402.03300](figures/2402.03300_p1.png)

This line graph plots the MATH Top@1 accuracy on the y-axis against the date on the x-axis. It uses a dashed line connecting various labeled open-source models (such as LLaMA1-65B, Mistral-7B, and Qwen-72B) to show a performance trend over time, culminating in a red star representing DeepSeekMath-7B. Horizontal dotted lines indicate the performance levels of proprietary models, including Gemini-Ultra, GPT-4 API, and early versions of GPT-4.

**Mathematical Reasoning in Large Language Models: Benchmarks, Architectures, Evaluation, and Open Challenges** — arXiv:2605.19723 p.4

![2605.19723](figures/2605.19723_p4.png)

The figure consists of two text boxes containing a math word problem and a corresponding step-by-step erroneous solution. It conveys an example of a reasoning failure where a model provides a logical sequence of steps that ultimately leads to an incorrect mathematical answer.

**Test-Time Scaling in Multimodal Foundation Models: A Comprehensive Survey of Generation and Reasoning** — arXiv:2606.08231 p.2

![2606.08231](figures/2606.08231_p2.png)

Figure 1(a) is a timeline chart showing the evolution of multimodal generation (black triangles) and reasoning (white triangles) from 2024Q4 to 2025Q4, categorized into sampling-based, feedback-based, and search-based methods. Figure 1(b) is a line graph plotting the quarterly number of arXiv entries related to "test-time scaling" in a multimodal context, showing a growth trend from 8 entries in 2024Q4 to 39 in 2025Q4. Figure 1(c) uses two comparative diagrams with icons to illustrate the differences between pre-training scaling (characterized by high compute cost and limited search space) and test-time scaling (characterized by low cost and a broader search space).

**The Periodic Table of LLM Reasoning: A Structured Survey of Reasoning Paradigms, Methods, and Failure Modes** — arXiv:2606.11470 p.3

![2606.11470](figures/2606.11470_p3.png)

The figure consists of three main panels labeled "Context Stream," "One Forward Pass," and "Distribution Over Next Token Exit," connected by a large arrow at the bottom to represent a single step in a continuous chain. The first panel shows a text sequence with highlighted tokens, the second displays a vertical stack of processing layers (Embed, Attention, and MLP), and the third shows a horizontal bar chart representing a probability distribution over potential next tokens. Collectively, the diagram conveys how an LLM processes a context stream through a sequence of layers to produce a probability distribution for the next token, illustrating the iterative nature of reasoning as repeated next-token prediction.

**Diversity Matters: Revisiting Test-Time Compute in Vision-Language Models** — arXiv:2605.30713 p.3

![2605.30713](figures/2605.30713_p3.png)

The figure consists of two bar charts, (a) Direct Answer Prompt and (b) CoT Prompt, comparing accuracy percentages across various vision-language benchmarks including Overall, MathVista, MathVision, TQA, ScienceQA, MMStar, and MMMU. Chart (a) compares "Vanilla" against "Majority Voting" strategies, while chart (b) compares "Vanilla," "Pivot Word," "CoT Length," "Feature-All," and "Majority Voting" strategies. The charts convey that while majority voting shows no improvement in the Direct Answer setting, it offers modest but consistent accuracy gains in the CoT Prompt setting.

**Revisiting the Effectiveness of LLM Pruning for Test-Time Scaling** — arXiv:2604.25098 p.2

![2604.25098](figures/2604.25098_p2.png)

The figure compares structured and unstructured pruning in Large Language Models (LLMs) using a mathematical query about the divisors of 196. The top panel shows a structured pruned model where entire blocks are removed (indicated by red 'X' marks), resulting in a repetitive, incoherent chain of thought and an incorrect answer. The bottom panel shows an unstructured pruned model where individual weights are removed (indicated by red 'X' marks), resulting in a coherent chain of thought and the correct answer.
