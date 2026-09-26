*deep research · 3 round(s) · 200 landmarks · frontier≥2023: 95 · 3 full-PDF critiques · grounded 41 · off-digest 0*

# The Evolution of State-Space Models: From Classical Control to the Scaling Frontier

The pursuit of efficient sequence modeling has long been defined by a fundamental trade-off between the linear-time recurrence of traditional models and the quadratic-time complexity of attention mechanisms. While recurrent architectures struggle to capture long-range dependencies due to vanishing gradients, the Transformer’s self-attention mechanism imposes a significant computational bottleneck as sequence lengths grow, limiting its application in high-resolution or extremely long-context tasks. State-space models (SSMs) have emerged as a transformative paradigm to resolve this tension, leveraging the mathematical rigor of continuous-time dynamical systems to provide a framework that offers both the parallelizable training of convolutions and the efficient inference of recurrent models.

This review traces the developmental arc of SSMs, beginning with the **Foundations of Recurrent and Structured State-Space Modeling** to establish how classical control theory provides the basis for modern neural sequence processing. We then examine the **Evolution of Structured State-Space Architectures** and the critical **Theoretical Analysis and Generalization of SSMs** that have enabled these models to achieve competitive expressive power. The narrative expands to discuss the versatility of the framework through **Expanding SSMs to Multimodal and Non-Sequence Domains**, followed by an analysis of the emerging **Hybrid Architectures and SSM-Transformer Interplay** that seeks to combine the strengths of both paradigms. Finally, we arrive at **The Current Frontier: Scaling, Efficiency, and Multi-Scale SSMs**, investigating the most recent breakthroughs in optimizing these models for massive-scale deployment and multi-resolution data processing.

## Foundations of Recurrent and Structured State-Space Modeling

The evolution of sequence modeling has been defined by the struggle to capture long-term dependencies while maintaining computational stability. Early foundational work addressed the inherent pathologies of Recurrent Neural Networks (RNNs), specifically the vanishing and exploding gradient problems. arXiv:1211.5063 provided a critical analytical and geometric perspective on these issues, proposing gradient norm clipping to mitigate explosions and a soft constraint to combat vanishing gradients. While these interventions stabilized training, they did not fundamentally alter the architectural limitations of traditional RNNs. Subsequent methodological advancements sought to improve this through gating mechanisms; arXiv:1412.3555 demonstrated that gated units, such as LSTMs and GRUs, could outperform traditional RNNs, noting that GRUs often offer superior convergence and generalization under fixed parameter constraints due to their computational efficiency.

A significant theoretical shift occurred with the introduction of HiPPO (High-order Polynomial Projection Operators), which moved beyond heuristic gating toward an optimal framework for online signal compression. arXiv:2008.07669 proposed projecting continuous signals onto polynomial bases, providing a mathematically principled solution to the function approximation problem. This approach proved more robust to timescale shifts than RNN or neural ODE baselines and established that standard RNN gating is, in fact, a specific instance of HiPPO memory.

Building upon this, the development of Structured State Space (SSM) models bridged the gap between continuous-time dynamics and efficient discrete-time computation. arXiv:2111.00396 introduced S4, which utilizes a "Normal Plus Low-Rank" (NPLR) parameterization to enable stable diagonalization of the HiPPO matrix. This allowed for an asymptotically efficient $\tilde{O}(N+L)$ framework that could compute continuous, recurrent, and convolutional representations. S4's strength lies in its ability to solve long-range tasks where prior models failed, such as achieving 88% accuracy on the Path-X task (length 16k) in the Long Range Arena (LRA) benchmark. However, the model faces potential numerical instabilities when the $A$ matrix has eigenvalues in the right half-plane, a weakness addressed by modifying the NPLR parameterization to $\Lambda - PP^*$ instead of $\Lambda - PQ^*$.

Recent research has focused on optimizing these structures for better implementation and performance. arXiv:2206.11893 introduced S4D, a diagonal state space model designed to be more efficient and easier to implement than the DPLR variant of S4, while still achieving a competitive 85% on the LRA benchmark. Further refinements in initialization have also emerged; arXiv:2206.12037 demonstrated that initializing SSM state matrices using generalized orthogonal basis projections (extending HiPPO) allows S4 models to achieve state-of-the-art results, including 96% on the Path-X task. Together, these advancements represent a transition from heuristic recurrent architectures to mathematically structured models capable of efficient, long-range memory reconstruction.

## Evolution of Structured State-Space Architectures

The evolution of structured state-space models (SSMs) has been characterized by a continuous effort to bridge the expressivity gap between efficient linear recurrences and the high-performance capabilities of Transformer-based attention. Early methodological advancements focused on enhancing the modeling of discrete sequences. For instance, the H3 model introduced a discrete SSM based on a shift matrix and multiplicative interactions to better capture discrete sequence patterns, addressing the expressivity limitations of standard SSMs identified through induction head tasks [arXiv:2212.14052]. While H3 achieved significant speedups—training 4-8 times faster than attention for long sequences via FlashConv [arXiv:2212.14052]—it functioned primarily as a hybrid to bridge the performance gap where traditional SSMs underperformed [arXiv:2212.14052].

Parallel to these developments, researchers explored subquadratic alternatives to attention through different structural paradigms. The Hyena Hierarchy utilized interleaved, implicitly parametrized long convolutions and data-controlled gating [arXiv:2302.10866]. This approach demonstrated superior scaling, being 100x faster than optimized attention at a 64K sequence length [arXiv:2302.10866], and outperformed standard SSMs in recall and reasoning tasks [arXiv:2302.10866]. Similarly, RWKV sought to reconcile the parallelizable training of Transformers with the linear-scaling inference of RNNs [arXiv:2305.13048], providing a mechanism to avoid the quadratic complexity inherent in architectures like Pythia or BLOOM [arXiv:2305.13048].

A significant shift occurred with the introduction of data-controlled mechanisms. GateLoop generalized linear recurrent models by employing data-controlled state transitions [arXiv:2311.01927], outperforming Hyena and S5-Hyena on WikiText-103 [arXiv:2311.01927]. This trajectory toward selectivity culminated in Mamba, which introduced Selective SSMs where parameters are functions of the input [arXiv:2312.00752]. By combining this selectivity with a hardware-aware parallel algorithm, Mamba addressed the fundamental weaknesses of gated convolutions and linear attention, matching the performance of Transformers twice its size while maintaining linear scaling and 5x higher inference throughput [arXiv:2312.00752].

Recent research has moved toward hybridizing these efficient recurrences with localized attention mechanisms to optimize long-context utility. The Griffin and Hawk models mix gated linear recurrences (RG-LRU) with local Multi-Query Attention [arXiv:2402.19427]. While Griffin exceeds Mamba's performance and matches Llama-2 using 6x fewer tokens, it exhibits a distinct trade-off: it excels at sequence extrapolation and long-sequence scaling but performs less effectively on exact-retrieval tasks without specific fine-tuning [arXiv:2402.19427]. This highlights a continuing tension in the field between the efficient, continuous-state modeling of SSMs and the precise, discrete-retrieval strengths of attention-based architectures.

## Theoretical Analysis and Generalization of SSMs

Recent literature has transitioned from treating State-Space Models (SSMs) as purely empirical architectures to developing rigorous theoretical frameworks that explain their capacity, generalization, and relationship to attention mechanisms. A primary focus of this theoretical evolution is establishing the expressive power of SSMs. For instance, arXiv:2309.13414 provides a constructive proof that multi-layer SSMs with layer-wise nonlinearity serve as universal approximators for continuous sequence-to-sequence mappings. Notably, this work demonstrates that these models possess exponentially decaying memory, a property shared with traditional Recurrent Neural Networks (RNNs), and utilizes a Volterra-series-based construction to optimize width dependency relative to sequence length.

The theoretical landscape is further enriched by efforts to unify SSMs with established signal processing and attention paradigms. arXiv:2312.06211 reframes Structured State-space Layers (SSLs) as an extension of deep Wiener models, establishing a connection to system identification through the interconnection of Wiener systems in series. This perspective highlights the parallelizable nature of these models, facilitating efficient training for long-sequence tasks. A more profound unification is found in the State Space Duality (SSD) framework presented in arXiv:2405.21060. This work establishes a formal connection between SSMs and attention mechanisms via the decomposition of structured semiseparable matrices, providing the theoretical basis for Mamba-2, which achieves 2-8X speed improvements over original selective SSMs.

Building upon these structural connections, recent research has turned toward the critical problem of generalization. While earlier approaches often relied on norm-based bounds, arXiv:2405.02670 introduces a data-dependent generalization bound that accounts for the complex interplay between model parameters and temporal dependencies. This contribution is significant because it allows for the design of specific initialization schemes and non-norm-based regularizers aimed at directly minimizing the generalization error. This trajectory is extended by arXiv:2502.01473, which analyzes selective SSMs (such as Mamba and Mamba-2) through the lens of attention. This analysis provides insights into the length-independence of their generalization capabilities, positioning selective SSMs as robust alternatives to Transformers.

Finally, the field is increasingly bridging the gap between control theory and large-scale AI. arXiv:2403.16899 provides a control-theoretic overview, integrating linear SSMs into deep neural architectures to serve as foundation models. By mapping input/output signals within the context of language modeling, this work contextualizes the performance of models like Mamba on benchmarks such as the Long Range Arena (LRA). Collectively, these advancements suggest that the strength of SSMs lies in their ability to reconcile the computational efficiency of recurrent structures with the expressive and generalization properties of attention-based models.

## Expanding SSMs to Multimodal and Non-Sequence Domains

Recent research has moved beyond standard vector-based sequence modeling to adapt State-Space Models (SSMs) to complex topological structures, visual data, and hybrid architectures. This expansion is characterized by a transition from processing linear temporal sequences to handling spatial, relational, and multi-modal information.

A primary frontier involves the integration of SSMs with graph-structured data. Graph State-Space Models generalize traditional vector-based formulations by representing inputs, outputs, and latent states as graphs, thereby explicitly exploiting relational inductive biases [arXiv:2301.01741]. While this approach addresses topological information, more recent advancements seek to refine the intersection of graph learning and sequence modeling. The Message-Passing State-Space Model (MP-SSM) improves upon the traditional Message-Passing Neural Network (MPNN) paradigm by integrating modern SSM principles via a Graph Shift Operator (GSO) [arXiv:2505.18728]. Unlike earlier Graph SSMs, the MP-SSM is specifically designed to preserve permutation equivariance and message-passing compatibility, providing a robust solution to the over-squashing and vanishing gradient problems inherent in standard MPNNs [arXiv:2505.18728]. This allows MP-SSMs to achieve state-of-the-art performance on long-range synthetic benchmarks such as LRGB [arXiv:2505.18728].

In the visual domain, the challenge lies in addressing the position-sensitivity and global context requirements of images. Vision Mamba (Vim) addresses this by introducing a bidirectional SSM, which allows for efficient visual representation learning [arXiv:2401.09417]. This bidirectional approach is particularly notable for its computational efficiency during batch inference at high resolutions, such as 1248x1248 [arXiv:2401.09417]. Further developments in medical image analysis have introduced scanning mechanisms to allow visual Mambas to traverse direction-sensitive information [arXiv:2406.03430].

The research frontier also explores hybridizing SSMs with other architectures to balance efficiency and expressivity. For instance, the Jamba architecture interleaves Transformer layers with Mamba layers using a Mixture-of-Experts (MoE) approach [arXiv:2406.03430]. This hybrid strategy aims to leverage the global receptive field and dynamic weight allocation of SSMs while maintaining the scaling advantages of MoE, effectively positioning these models as alternatives to both traditional CNNs and complex Transformer-based attention mechanisms [arXiv:2406.03430]. Collectively, these developments demonstrate a shift from treating SSMs as purely temporal operators to versatile frameworks capable of modeling complex, non-linear, and multi-dimensional data structures.

## Hybrid Architectures and SSM-Transformer Interplay

The evolution of sequence modeling has transitioned from a dichotomy between recurrent-style models and attention-based architectures toward a sophisticated interplay of hybrid systems. Recent research focuses on reconciling the long-term dependency preservation of Transformers with the computational efficiency of State-Space Models (SSMs) and linear attention mechanisms.

A primary driver of this interplay is the need to manage the quadratic complexity of standard attention. While traditional Transformers struggle with long-sequence generation, StreamingLLM [arXiv:2309.17453] offers a methodological advancement for streaming scenarios by introducing "Attention Sinks." By retaining a small number of initial tokens in the KV cache, this approach enables efficient long-sequence generation across architectures like Llama-2 and Falcon, providing a way to maintain performance without the memory overhead of dense attention [arXiv:2309.17453].

Parallel to these memory management strategies, developments in linear attention seek to bridge the gap between SSMs and Transformers. The Gated Linear Attention (GLA) Transformer [arXiv:2312.06635] represents a significant methodological leap by combining a hardware-efficient algorithm, FLASHLINEARATTENTION, with data-dependent gates. Unlike standard Transformers, GLA achieves linear-time inference complexity and demonstrates superior length generalization—scaling from 2K to over 20K sequences—while maintaining higher training throughput than comparable Mamba models [arXiv:2312.06635].

The current research frontier is perhaps best exemplified by the move toward true architectural hybridization. Jamba [arXiv:2403.19887] integrates Transformer layers, Mamba (SSM) layers, and Mixture-of-Experts (MoE) modules into a single framework. This hybrid design aims to balance the high-quality modeling of Transformers with the throughput and memory efficiency of SSMs and MoE, specifically optimizing KV cache usage to fit large-scale models within a single 80GB GPU [arXiv:2403.19887].

Theoretical frameworks for these developments are being synthesized in recent surveys. While some literature explores the relationship between HMMs, RNNs, and Transformers regarding long-term dependencies [arXiv:2406.09062], other reviews provide a more granular distinction between continuous-time SSMs (such as latent neural ODEs and SDEs) and discrete-valued models like HMMs [arXiv:2412.11211]. These reviews highlight a critical tension in the field: the need to unify discrete-time modeling with continuous-valued SSMs to achieve a comprehensive understanding of deep learning-based sequence processing [arXiv:2412.11211]. Together, these advancements suggest a trajectory where the rigid boundaries between attention and recurrence are dissolving in favor of modular, hybrid systems optimized for both hardware efficiency and long-context reasoning.

## The Current Frontier: Scaling, Efficiency, and Multi-Scale SSMs

The current research frontier in sequence modeling is characterized by a push toward theoretical unification, multi-scale temporal resolution, and optimized hardware deployment. Recent scholarship has moved beyond the initial success of S4 and Mamba to address fundamental questions regarding the structural nature of these models. For instance, arXiv:2601.13357 provides a critical comparative analysis between Hidden Markov Models (HMMs) and State Space Models (SSMs), distinguishing HMMs' discrete latent states from the continuous-valued latent states used in classical SSMs, and further contrasting modern NLP-focused SSMs—which utilize deterministic discretized linear systems—against their stochastic predecessors.

A significant theoretical advancement is found in the attempt to unify disparate architectures. arXiv:2510.09389 introduces a framework that casts the linear combination coefficients of sequence models as outputs of autonomous linear dynamical systems. This provides a formal mechanism to view Transformers, SSMs, and gated linear RNNs as special cases of a single phenomenon. Crucially, this work identifies that the quadratic complexity inherent in Transformers is fundamentally linked to nonlinear readout maps, whereas linear maps allow for aggregation into a fixed-dimensional recurrent state, offering a mathematical justification for the efficiency of SSMs.

To address the limitations of single-resolution modeling, recent methodological shifts have embraced multi-scale dynamics. The MS-SSM architecture (arXiv:2512.23824) decomposes dynamical systems into multiple time scales to operate at varying resolutions. By utilizing linear recurrences and convolution equivalence, MS-SSM (in both S4 and S6 variants) enables parallelizable training and fast inference, specifically aiming to mitigate the limited effective memory observed in traditional SSMs. This represents a departure from the monolithic state representations seen in earlier iterations of the field.

Efficiency at scale is also being pursued through both architectural refinement and hardware-aware optimization. While arXiv:2503.18970 surveys the evolution of SSMs as efficient alternatives to the quadratic complexity of Transformers and the vanishing gradient issues of RNNs, other research focuses on the practicalities of deployment. For example, the KernelEvolve framework (arXiv:2512.23236) utilizes a self-improving state machine and tree search strategies to optimize kernel coding for heterogeneous AI accelerators, targeting sub-second latency in massive-scale inference. Complementing these hardware-level optimizations, the SEAL framework (arXiv:2501.15225) enhances long-context retrieval in existing LLMs by adjusting the strength of individual attention components via gradient descent. Unlike traditional methods that might require extensive retraining, SEAL allows for efficient updates with minimal data by avoiding the infeasible sequential pruning of all heads or channels. Together, these developments indicate a transition from merely replicating Transformer performance to engineering specialized, multi-scale, and hardware-optimized sequence processors.

## Tensions and Open Problems

A central tension in the field concerns the fundamental efficacy of State Space Models (SSMs) compared to the Transformer architecture. While the Transformer has long been the gold standard for sequence modeling, recent work such as arXiv:2402.01032 argues that Transformers still maintain a superior ability to "repeat after me" and handle complex instruction following compared to SSM-based alternatives. This is countered by architectural innovations like Griffin (arXiv:2402.19427), which attempts to bridge this gap by hybridizing gated linear recurrences with local attention to capture both long-range dependencies and fine-grained local context. Furthermore, the actual utility of the "state" in these models remains under scrutiny; while earlier works like arXiv:2212.14052 sought to enhance language modeling through structured state-space representations, arXiv:2404.08819 critiques this premise, suggesting that the perceived "state" in many modern SSMs may be an illusion that fails to capture the true underlying dynamics of the sequence.

Another significant debate revolves around the practical limits of long-context modeling and the metrics used to evaluate it. The emergence of Mamba (arXiv:2312.00752) promised linear-time sequence modeling that could theoretically bypass the quadratic bottlenecks of attention. However, the RULER benchmark (arXiv:2404.06654) challenges these claims by suggesting that the "real" effective context size of many long-context models, including RWKV (arXiv:2305.13048), may be significantly lower than their theoretical limits when subjected to rigorous retrieval and reasoning tasks. This tension highlights a disconnect between theoretical complexity bounds and the empirical ability of a model to maintain high-fidelity information retrieval over massive windows.

Finally, there is an ongoing disagreement regarding the optimization and scaling laws of these architectures. While traditional scaling laws (arXiv:2001.08361) provided a roadmap for Transformer development, proponents of alternative architectures like RWKV (arXiv:2305.13048) argue that these laws do not directly translate to recurrent or linear-time models, necessitating a new understanding of how parameter count and data influence performance. This is compounded by technical disputes over the structural requirements of state spaces; for instance, while some argue for the necessity of complex structured matrices, others suggest that simple discrete state models (arXiv:2303.09489) are sufficient and more effective for time-series modeling, as further supported by recent attempts to unify SSMs with simpler exponential smoothing methods (arXiv:2403.17445).

## Outlook

The frontier of the field is rapidly shifting from architectural design toward the intersection of model theory and automated hardware optimization. As we move beyond pure sequence modeling, the focus is turning toward the formal relationship between SSMs and probabilistic frameworks like Hidden Markov Models (arXiv:2601.13357) and the development of autonomous, hardware-aware optimization frameworks. We are entering an era where "Kernel-centric" scaling—utilizing multi-agent frameworks (arXiv:2603.10085) and evolutionary search (arXiv:2604.11109) to co-optimize LLM logic and GPU kernels—will likely define the next generation of efficient, high-performance foundation models.

---

## Key Figures

**Attention Is All You Need** — arXiv:1706.03762 p.3

![1706.03762](figures/1706.03762_p3.png)

The figure depicts the Transformer model architecture, consisting of an encoder stack on the left and a decoder stack on the right, both composed of $N$ identical layers. The diagram uses colored boxes to represent functional components—such as Multi-Head Attention, Feed Forward, and Add & Norm layers—connected by arrows that illustrate the flow of data from input/output embeddings through the encoder-decoder structure to the final softmax output.

**Efficiently Modeling Long Sequences with Structured State Spaces** — arXiv:2111.00396 p.2

![2111.00396](figures/2111.00396_p2.png)

The figure consists of three panels illustrating the transition from continuous to discrete state space models. The left panel shows a block diagram of a continuous system with input $u$, state $x$, and output $y$ governed by differential equations, while the center panel displays a signal with a dashed red line and a matrix $A$ to represent long-range dependencies. The right panel depicts discrete representations through a sequence of boxes and a convolution operation, conveying how SSMs can be computed efficiently as either recurrences or convolutions.

**Mamba: Linear-Time Sequence Modeling with Selective State Spaces** — arXiv:2312.00752 p.3

![2312.00752](figures/2312.00752_p3.png)

The figure illustrates a Selective State Space Model where an input $x_t$ is processed through a selection mechanism that projects and discretizes parameters $\Delta_t$, $B_t$, and $C_t$ to influence the state transition. Arrows show the flow of information from the previous latent state $h_{t-1}$ through a transition matrix $A$ and the selective parameters to produce the current latent state $h_t$ and output $y_t$. A triangular diagram in the corner depicts the hardware hierarchy of GPU HBM, SRAM, and the model's state expansion.

**Language Models are Few-Shot Learners** — arXiv:2005.14165 p.3

![2005.14165](figures/2005.14165_p3.png)

The figure uses a hierarchical diagram with brackets to illustrate the relationship between an "outer loop" of unsupervised pre-training via SGD and an "inner loop" of in-context learning. The outer loop is represented by a long purple arrow, while the inner loop consists of three separate boxes labeled "sequence #1" through "sequence #3," each containing examples of tasks (arithmetic, translation, or word pairs) followed by blue vertical labels for "in-context learning." The diagram conveys that pre-training enables the model to perform rapid adaptation to new tasks within a single sequence during inference.

**BERT: Pre-training of Deep Bidirectional Transformers for Language
  Understanding** — arXiv:1810.04805 p.3

![1810.04805](figures/1810.04805_p3.png)

The figure illustrates the two stages of the BERT framework, consisting of a "Pre-training" block on the left and a "Fine-Tuning" block on the right connected by a dashed arrow. The pre-training stage shows an unlabeled pair of masked sentences (A and B) being processed through BERT to perform Next Sentence Prediction (NSP) and Masked Language Modeling (MLM), while the fine-tuning stage shows how the same architecture is applied to specific downstream tasks like MNLI, NER, and SQuAD using inputs such as question-answer pairs.

**Transformers are RNNs: Fast Autoregressive Transformers with Linear
  Attention** — arXiv:2006.16236 p.6

![2006.16236](figures/2006.16236_p6.png)

The figure consists of two log-log line plots comparing the computational requirements of different attention mechanisms (linear, softmax, and three lsh variants) against sequence length. The left plot shows "Time (milliseconds)" and the right plot shows "GPU Memory (MB)" on the y-axes, conveying that while softmax scales quadratically with sequence length, the linear and lsh models scale linearly.

**Simplified State Space Layers for Sequence Modeling** — arXiv:2208.04933 p.2

![2208.04933](figures/2208.04933_p2.png)

This flowchart illustrates the computational components of an S5 layer, using boxes to represent operations (e.g., "Diagonalize," "Discretize," "Parallel scan") and colored boxes to represent parameters, variables, and messages. The diagram conveys a process where learnable parameters ($A, B, C, \Delta$) are transformed through diagonalization and discretization to enable a parallel scan, which ultimately produces sequence outputs ($x_{1:L}, y_{1:L}$) passed through a non-linearity.

**Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks** — arXiv:2005.11401 p.2

![2005.11401](figures/2005.11401_p2.png)

The figure illustrates a retrieval-augmented generation framework consisting of a Query Encoder, a non-parametric Retriever ($p_{\eta}$), a Document Index, and a parametric Generator ($p_{\theta}$). Arrows depict the flow from an input query ($x$) through the MIPS process to retrieve top-$k$ documents ($z_i$), which are then passed to the generator to produce a marginalized final prediction ($y$). A dashed line indicates end-to-end backpropagation through the query ($q$) and generator parameters ($\theta$).

**Kernel-Smith: A Unified Recipe for Evolutionary Kernel Optimization** — arXiv:2603.28342 p.3

![2603.28342](figures/2603.28342_p3.png)

This line graph plots "Speed Up Score" on the y-axis against "Evolution Step" on the x-axis to compare the performance trajectories of five different models. The figure shows several colored lines representing models like Kernel-Smith-235B-RL and Claude-4.6-Opus, conveying that the Kernel-Smith-235B-RL model achieves a higher peak speedup score by evolution step 40 compared to the other baseline models.

**KernelFoundry: Hardware-aware evolutionary GPU kernel optimization** — arXiv:2603.12440 p.3

![2603.12440](figures/2603.12440_p3.png)

The figure depicts a flowchart of the KernelFoundry pipeline consisting of six interconnected boxes: User Input, Prompt Constructor, Inference: Large Language Model, Evaluation Engine, MAP-Elites Archive Selection & Evolution, and Meta-Prompt Evolution. Arrows indicate a cyclical process where user input is processed into prompts for an LLM, evaluated by an engine, and then used to drive both the selection/evolution of kernels and the co-evolution of meta-prompts.

**On the Relation of State Space Models and Hidden Markov Models** — arXiv:2601.13357 p.4

![2601.13357](figures/2601.13357_p4.png)

The figure depicts a Probabilistic Graphical Model (PGM) consisting of a directed chain of nodes labeled $h_1, h_2, \dots, h_k$ connected by horizontal arrows, with vertical arrows pointing from each $h$ node to corresponding $y$ nodes ($y_1, y_2, \dots, y_k$). This structure conveys the temporal dependency of a hidden state sequence $h$ and its relationship to a sequence of observed variables $y$.

**High-Order Spectral Element Methods for Wave Propagation on ARM Multicore CPU with SME: Optimizations and Implications** — arXiv:2606.12850 p.3

![2606.12850](figures/2606.12850_p3.png)

The figure consists of two identical block diagrams representing the LX2 CPU architecture, each containing labeled boxes for IO, UC (Unified Cache), HBM (High Bandwidth Memory), and core components. The diagrams use arrows and spatial arrangement to convey the connectivity and hierarchical relationship between the input/output interfaces, cache layers, and memory subsystems.

**Kernel Foundry: A Diagnosis-driven Evolutionary Kernel Optimizer with Multi-Experts** — arXiv:2605.30359 p.2

![2605.30359](figures/2605.30359_p2.png)

The figure illustrates the "Kernel Foundry" framework, divided into two main stages: "Expert Initialization" and a "Multi-Island Diagnosis-Driven Evolution Loop." The initialization stage uses PyTorch code, a distilled dataset, and tasks to produce a small expert model and initial candidate codes via a "Cheating Validator," while the evolution loop shows multiple search paths (Islands 1-3) being iteratively refined by a "Code Optimizer" and "Result Analyzer" using feedback and hints from a shared "Experience Library."

**KernelSkill: A Multi-Agent Framework for GPU Kernel Optimization** — arXiv:2603.10085 p.3

![2603.10085](figures/2603.10085_p3.png)

The figure is a flowchart composed of interconnected boxes and arrows representing the KernelSkill framework's multi-agent architecture. It depicts a workflow where specialized agents—including an Extractor, Retriever, Verifier, Profiler, Optimizer, and Repairer—interact through a central loop to perform GPU kernel optimization. The diagram conveys a continuous cycle of extracting features, retrieving knowledge, verifying results, profiling performance, optimizing code, and repairing kernels.
