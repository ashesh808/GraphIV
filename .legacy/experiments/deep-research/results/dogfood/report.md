*deep research · 1 round(s) · 120 landmarks · frontier≥2024: 56 · 2 full-PDF critiques · grounded 43 · off-digest 0*

# Leveraging Citation Networks for Automated Scientific Synthesis: A Review of Graph-Augmented Retrieval-Augmented Generation

The rapid expansion of scientific publishing has made manual literature synthesis an increasingly insurmountable task for researchers, necessitating advanced computational approaches to knowledge integration. While standard Retrieval-Augmented Generation (RAG) has demonstrated success in answering discrete queries, these models often struggle with the complex, interconnected nature of scientific discourse. Traditional textual retrieval methods frequently overlook the structural dependencies that define scholarly progress, failing to capture the nuanced relationships between seminal works and subsequent developments. To address these limitations, there is a critical need to move beyond isolated text chunks toward architectures that can navigate the multidimensionality of scientific knowledge through the lens of citation networks.

This review traces the technological evolution of these systems, beginning with the foundational principles of retrieval-augmented generation and the core mechanisms of knowledge integration. We examine the transition from purely textual retrieval to more sophisticated graph-based architectures, specifically focusing on how citation-aware retrieval and structural reasoning can be leveraged to navigate complex scientific contexts. The discussion then shifts to the practical application of these models: the synthesis of long-form scientific reviews and the facilitation of automated idea generation. Because the utility of these models depends on their reliability, we critically address the methods used for ensuring grounding, attribution, and citation accuracy. Finally, we explore the current frontier of the field, investigating how agentic workflows and advanced graph-augmented frameworks are paving the way for autonomous scientific discovery.

## Foundations of Retrieval-Augmented Generation and Knowledge Integration

The foundation of Retrieval-Augmented Generation (RAG) lies in the integration of external knowledge to enhance the performance of models on knowledge-intensive tasks (arXiv:2312.10997, arXiv:2407.13193). Early architectural developments established distinct methodologies for retrieval, synthesis, and grounding. For instance, arXiv:2005.11401 introduced a dense retrieval method using document encoders and a MIPS index built with FAISS and HNSW approximation. This work proposed two specific synthesis techniques: RAG-Sequence, which utilizes the same document for all target tokens, and RAG-Token, which allows for different documents to be used for each target token, grounding the generator in a top-K truncated distribution of retrieved passages. In contrast, arXiv:2002.08909 focused on Open-QA and masked language modeling through a latent knowledge retriever that attends over documents from large corpora, such as Wikipedia. While arXiv:2005.11401 emphasizes the distinction between sequence and token-level synthesis, arXiv:2002.08909 utilizes a retrieve-then-predict generative process and evaluates success through exact match with reference answers.

As the field matured, research shifted from specific architectural implementations toward broader taxonomical frameworks. arXiv:2312.10997 provides a comprehensive categorization of RAG evolution, dividing research into Naive, Advanced, and Modular paradigms based on the tripartite foundation of Retrieval, Generation, and Augmentation. This survey offers significant empirical depth, providing a detailed taxonomy of 84 RAG methods and a systematic review of 26 tasks and 50 datasets. However, the utility of this taxonomy is limited by its descriptive nature; the survey lacks a critical comparative performance analysis or a unified metric to determine which specific "Modular" components actually outperform "Advanced" ones in practical applications.

The scope of evaluation and the complexity of knowledge integration have also expanded. While early foundational work relied on metrics like exact match (arXiv:2002.08909), broader surveys of Large Language Models (LLMs) suggest that evaluation must encompass language generation, knowledge utilization, and complex reasoning (arXiv:2303.18223). Recent literature continues to explore the intersection of RAG and LLMs (arXiv:2405.06211) and the use of retrieval fusions to leverage external knowledge databases (arXiv:2407.13193). Collectively, these works demonstrate a transition from specialized retrieval-synthesis mechanisms toward a complex, modular ecosystem of knowledge-augmented generation.

## From Textual to Graph-Based Retrieval Architectures

The evolution of Retrieval-Augmented Generation (RAG) has increasingly shifted from purely textual retrieval toward architectures that leverage structured graph data to enhance reasoning and grounding. Recent surveys characterize this transition by categorizing various GraphRAG frameworks, domain-specific techniques, and the necessary benchmark datasets required to support them arXiv:2501.00309. While traditional RAG focuses on unstructured text, graph-based approaches attempt to capture complex relational dependencies that text alone may obscure.

A primary distinction in these architectures lies in how graph topology is utilized for retrieval and synthesis. For instance, G-Retriever addresses graph question answering (GraphQA) by employing Personalized PageRank-based Subgraph Tokenization (PCST) to identify relevant graph segments arXiv:2402.07630. This method is paired with a Graph Attention Network (GAT) as a graph encoder to process structure, ultimately using a Llama2-7b model to provide textual replies and highlights grounded in the retrieved graph components arXiv:2402.07630. In contrast, the GRAG framework approaches multi-hop reasoning by retrieving all $k$-hop ego-graphs, subsequently applying a soft pruning operation to mitigate redundancy among entities arXiv:2405.16506. GRAG further distinguishes itself by using a novel prompting method that converts textual subgraphs into hierarchical descriptions, effectively merging textual content with topological information to anchor generation to approximately optimal subgraph structures arXiv:2405.16506.

The literature also reveals a tension between specialized graph understanding and broader customization. While G-Retriever focuses on the specific task of textual graph understanding and question answering arXiv:2402.07630, other research explores the broader utility of GraphRAG for customizing Large Language Models (LLMs) more generally arXiv:2501.13958. This distinction is critical: one path optimizes for structural reasoning within a graph, while the other seeks to integrate graph knowledge to refine the model's general capabilities.

Comprehensive surveys further synthesize these developments, mapping the landscape of graph-based functionalities and their integration into RAG pipelines arXiv:2408.08921, arXiv:2504.10499. These surveys highlight that the move toward graph-based retrieval is not merely a change in data format but a fundamental shift in how models interact with relational context, moving from simple semantic similarity to structured, topological grounding. However, the effectiveness of these methods remains dependent on the specific retrieval mechanism—whether through PCST-based tokenization arXiv:2402.07630 or ego-graph pruning arXiv:2405.16506—and the ability of the model to synthesize hierarchical textual-topological descriptions.

## Citation-Aware Retrieval and Structural Reasoning for Scientific Contexts

Recent advancements in retrieval-augmented generation (RAG) for scientific literature demonstrate a significant shift from simple vector-based retrieval toward sophisticated graph-aware architectures that leverage both citation topology and document structure. Traditional approaches, such as the framework presented in arXiv:2412.15404, rely on standard vector database searches where embedded user queries identify relevant document chunks to be fed into a language model. While this method facilitates academic literature navigation by providing contextually relevant resources, it lacks the structural depth required to capture the interconnected nature of scientific discourse.

In contrast, more recent models integrate graph-based reasoning to better represent the relationships between scientific entities. arXiv:2501.15067 introduces CG-RAG, which utilizes Lexical-Semantic Graph Retrieval (LeSeGR) to combine discrete sparse and continuous dense signals. This method employs a contextual citation graph that captures chunk-level cross-relationships by surrounding each chunk with relevant context and utilizing a graph encoder for structured context. This represents a move toward more granular, chunk-level reasoning compared to the document-level retrieval seen in arXiv:2412.15404. Similarly, arXiv:2603.22633 advances this structural awareness through "graph-aware late chunking" specifically for biomedical literature. Unlike the general semantic retrieval in CG-RAG, arXiv:2603.22633 utilizes a complex document structure graph with diverse node types (sections, subsections, paragraphs, and citations) and multiple edge types (hierarchical, sequential, and cross-reference). This allows for sophisticated chunk boundary detection and retrieval re-ranking, providing a more rigorous grounding mechanism through KG-infused retrieval.

A distinct paradigm is found in LitFM (arXiv:2409.12177), which moves beyond retrieval for answering questions toward a foundation model approach for generating entire scientific components, such as related works sections. While CG-RAG and arXiv:2603.22633 focus on retrieval effectiveness and efficiency for question answering, LitFM utilizes citation graphs where edges are annotated with citing sentences and local context. This allows the model to anchor synthesis—such as title generation or abstract completion—directly to node attributes like titles and abstracts. While arXiv:2409.12177 evaluates its performance via ROUGE scores and statistical alignment with ground-truth related-work sections, the structural models like arXiv:2603.22633 prioritize metrics such as Mean Reciprocal Rank (MRR) and section diversity.

Furthermore, the integrity of these retrieval systems depends on the underlying network quality. arXiv:2605.12263 addresses the challenge of fragmented citation networks by proposing a hybrid framework that integrates citation topology with LLM-based text similarity. By adding semantic edges to disconnected components and using the Leiden algorithm for cluster detection, this approach seeks to preserve disciplinary homogeneity, providing a necessary foundation for the graph-based retrieval methods discussed in arXiv:2501.15067 and arXiv:2409.12177.

## Synthesizing Long-Form Scientific Reviews and Idea Generation

The evolution of automated scientific synthesis reflects a transition from simple text-based retrieval to complex, graph-structured reasoning. Early approaches to automated literature reviews utilized Retrieval-Augmented Generation (RAG) with models such as GPT-3.5-turbo, evaluating performance through textual overlap metrics like ROUGE-1 (achieving a score of 0.364) [arXiv:2411.18583]. However, more recent frameworks have moved toward highly controlled synthesis. For instance, Citegeist [arXiv:2503.23229] introduces dynamic RAG using Milvus vector databases and BERTopic, allowing for synthesis governed by specific hyperparameters for breadth, depth, and diversity. This represents a shift in evaluation methodology as well; while early work relied on ROUGE [arXiv:2411.18583], Citegeist employs an "LLM-as-a-judge" approach to score source relevance and writing quality [arXiv:2503.23229].

As the task shifts from reviewing existing literature to generating new research ideas, the role of graph topology becomes central. Research has progressed from evaluating the efficacy of VectorRAG versus GraphRAG in scientific chatbots [arXiv:2602.17856] to utilizing specific graph structures for creative inspiration. One approach utilizes an author–paper bipartite graph to facilitate both "exploitation" (adjacent hops) and "exploration" (random hops) to generate research ideas [arXiv:2602.22215]. In contrast, other methods leverage the temporal nature of science, such as using citation-evolution Directed Acyclic Graphs (DAGs) to provide structural cues for the supervised fine-tuning of models like Qwen2.5-7B-Instruct-1M [arXiv:2605.14790].

The most sophisticated synthesis techniques involve transforming unstructured text into structured relational contexts. Graph2Idea [arXiv:2606.09105] exemplifies this by extracting knowledge triples $(h, r, t)$ to construct a target-centered working graph, moving beyond the "flat" textual RAG used in earlier studies. This method demonstrates significant empirical advantages, specifically improving novelty scores from 0.45 to 0.52 and feasibility from 0.22 to 0.28 compared to existing baselines [arXiv:2606.09105]. 

Despite these advancements, the reliance on structured knowledge introduces new vulnerabilities. While Graph2Idea [arXiv:2606.09105] achieves superior performance through explicit knowledge recombination, its effectiveness is heavily contingent on the quality of LLM-extracted triples, which may be compromised by sparse or heterogeneous abstracts [arXiv:2606.09105]. Furthermore, while models like Citegeist [arXiv:2503.23229] and Graph2Idea [arXiv:2606.09105] utilize LLM-based or automated scoring, there remains a critical gap in the literature regarding the use of human expert validation to confirm the practical utility of generated ideas [arXiv:2606.09105].

## Ensuring Grounding, Attribution, and Citation Accuracy

The literature reveals a progression from basic in-context prompting to sophisticated, multi-stage mechanisms designed to ensure that generated text is strictly grounded in retrieved evidence. Early approaches to self-supported question answering (SQA) focused on conditional language modeling, where models were taught to inline specific quotes or evidence directly into the answer string using structured templates (arXiv:2203.11147). This method relies on autoregressive factorization to link answers to context, though it often necessitates human evaluation due to the absence of ground-truth targets (arXiv:2203.11147). Building on these foundations, arXiv:2305.14627 expanded the scope by using dense retrievers (GTR, DPR) and BM25 to retrieve up to 999 passages, employing in-context learning to prompt models to synthesize and cite evidence. While this approach improves factual correctness and verifiability, it serves as a baseline that subsequent works seek to refine through more granular or corrective architectures.

A significant shift in the literature is the move toward fine-grained, sentence-level attribution. Rather than treating an entire response as a single unit of evidence, arXiv:2407.01796 proposes an interleaved reference-claim generation technique using Chain-of-Thought (CoT). This mechanism ensures that every individual claim $c_i$ is substantiated by a corresponding reference $r_i$, providing a higher degree of precision in long-form question answering than broader in-line citation patterns (arXiv:2407.01796). Similarly, arXiv:2510.11394 utilizes a few-shot instruction template to guide citation patterns, where each answer statement cites a specific set of retrieved passages to ensure reliability (arXiv:2510.11394).

Despite these advancements in generation, the literature also identifies the need for post-hoc correction and rigorous verification to mitigate errors. arXiv:2504.15629 introduces CiteFix, a streaming-compatible post-processing technique that operates on the LLM's response during generation. By splitting responses into distinct "factual points," CiteFix improves source attribution and addresses the limitations of earlier methods, such as arXiv:2305.14627 and arXiv:1904.09675, which may suffer from citation inaccuracies (arXiv:2504.15629). The efficacy of such corrections is measured through specialized metrics like Mean Question-Level Accuracy (MQLA) and Relevancy URL (arXiv:2504.15629). This emphasis on accuracy is echoed in the work of arXiv:2510.11394, which prioritizes answer accuracy and citation quality through rigorous verification (arXiv:2510.11394). Collectively, these works demonstrate a transition from simple template-based inlining (arXiv:2203.11147) to complex, interleaved, and post-processed systems designed to maximize the verifiability of scientific synthesis.

## Agentic Workflows and Advanced Graph-Augmented Frontiers

Recent advancements in retrieval-augmented generation (RAG) have shifted from simple vector lookups toward agentic workflows and sophisticated graph-based architectures designed to handle the complexities of scientific literature. A primary trend in this frontier is the transition toward agentic pipelines that dynamically manage retrieval strategies. For instance, arXiv:2508.05660 proposes an open-source agentic hybrid RAG framework that utilizes an AI tool agent to select between Cypher-based graph queries and vector searches, specifically targeting the automated gathering of insights from academic literature. Similarly, arXiv:2509.22009 introduces "GraphSearch," an agentic deep searching workflow that employs dual-channel retrieval to facilitate multi-hop question answering (QA) through pre-constructed structural graph data.

While these agentic approaches focus on the *process* of retrieval, other research focuses on the *granularity* of the graph topology to improve grounding. arXiv:2605.30966 advances this by moving beyond simple entity links to a "typed claim network." By reifying cross-document references as typed claims—encoding source, target, text, and stance labels—this method provides a more nuanced representation of scientific discourse than standard knowledge graphs. This contrasts with the more structural approach of arXiv:2603.24925, which utilizes "GraphER" to incorporate proximity information via foreign-key relationships and graph edges to enhance the retrieval of tables and chunked documents through an offline enrichment and online reranking process.

The challenge of grounding remains a central theme, particularly regarding the mitigation of hallucinations in long-form synthesis. arXiv:2604.04359 addresses this through a "Grounded Knowledge Graph Index" specifically designed for long-document QA, aiming to anchor generation directly to source text. A more complex implementation of this concept is found in arXiv:2606.01613, which introduces "TechGraphRAG." This framework employs an autonomous, evidence-gated pipeline for technical literature reasoning, combining hybrid text retrieval (FAISS and BM25) with multimodal query rewrites. Unlike the purely structural or index-based grounding seen in arXiv:2604.04359, TechGraphRAG incorporates an agentic retry mechanism and evaluates success through evidence sufficiency scoring and end-to-end citation grounding.

The evolution of these methods demonstrates a clear trajectory: from improving retrieval efficiency through graph-based reranking (arXiv:2603.24925) to developing highly autonomous, multimodal agentic systems (arXiv:2606.01613) that can reason across complex technical domains. While arXiv:2508.05660 and arXiv:2509.22009 lay the groundwork for agentic graph-RAG, the more recent works suggest that the future of the field lies in the integration of semantic stance (arXiv:2605.30966) and rigorous, evidence-gated verification (arXiv:2606.01613) to ensure the reliability of synthesized scientific reviews.

## Tensions and Open Problems

A primary tension in the evolution of retrieval architectures concerns the structural granularity of the retrieved context. Early paradigms focused on standardizing retrieval through large-scale pre-training and few-shot prompting, as seen in the foundational work of arXiv:2112.04426 and arXiv:2208.03299. However, these methods are increasingly viewed as insufficient for complex reasoning. For instance, arXiv:2212.10509 argues that simply retrieving documents is inadequate, advocating instead for the interleaving of retrieval with chain-of-thought reasoning to bridge the gap between raw data and logical deduction. This debate extends into the structural domain, where arXiv:2404.16130 proposes a "local-to-global" graph approach to capture community-level information, whereas arXiv:2410.11001 suggests that a "Graph of Records" approach provides a more robust mechanism for boosting RAG performance by structuring retrieval around specific, high-fidelity data points.

A second significant debate centers on the reliability and evaluation of retrieved content, specifically regarding the mitigation of hallucinations. While some research suggests that retrieval inherently stabilizes language models, as argued in arXiv:2104.07567, others maintain that the presence of external data does not fundamentally solve the underlying mechanics of hallucination, a concern highlighted in the survey by arXiv:2202.03629. This skepticism is further compounded by the limitations of current evaluation metrics; arXiv:2504.15629 critiques the reliance on semantic similarity metrics like BERTScore (arXiv:1904.09675), arguing that they fail to capture the precision required for citation accuracy. Instead, newer frameworks suggest that post-processing citation verification is essential to ensure that the generated text remains grounded in the retrieved evidence.

Finally, there is a growing disagreement regarding the complexity of the retrieval agent. Traditional RAG systems often rely on a linear "retrieve-then-read" pipeline, but recent critiques suggest this is too simplistic for multi-hop reasoning or technical domains. For example, arXiv:2401.15391 identifies significant performance gaps in standard benchmarks when faced with multi-hop queries, suggesting that existing RAG evaluations are too shallow. This has led to a shift toward more sophisticated, agentic frameworks. While some models focus on efficient enrichment and reranking, such as the methods in arXiv:2603.24925, others, like the TechGraphRAG framework in arXiv:2606.01613, argue for a fully agentic approach that can autonomously navigate complex technical graphs to perform deep reasoning.

### Outlook

The frontier of RAG is moving away from simple vector similarity toward "knowledge-aware" synthesis. We are seeing a convergence of graph structures and semantic reasoning, where the goal is no longer just to find relevant text, but to reconstruct the underlying logic of scientific and technical domains. The next generation of systems will likely be defined by their ability to navigate heterogeneous networks—integrating co-author graphs, citation evolution, and typed claim networks—to move beyond mere information retrieval toward true scientific idea generation and autonomous technical reasoning.

---

## Key Figures

**Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks** — arXiv:2005.11401 p.2

![2005.11401](figures/2005.11401_p2.png)

The figure illustrates a retrieval-augmented generation architecture consisting of a Query Encoder, a Non-Parametric Retriever ($p_\eta$), a Document Index, and a Parametric Generator ($p_\theta$). Arrows show the flow from a query ($x$) through the MIPS process to retrieve top-$K$ documents ($z_i$), which are then passed to the generator to produce a marginalized final prediction ($y$). A dashed line indicates end-to-end backpropagation through the query ($q$) and generator ($\theta$) parameters.

**Retrieval-Augmented Generation for Large Language Models: A Survey** — arXiv:2312.10997 p.2

![2312.10997](figures/2312.10997_p2.png)

This figure is a "technology tree" diagram that uses a branching structure of colored nodes and lines to map the evolution of Retrieval-Augmented Generation (RAG) research. The branches are categorized into three augmentation stages—Fine-tuning (teal), Pre-training (orange), and Inference (blue)—and are organized chronologically along a vertical axis spanning from 2020 to 2024. The diagram conveys how RAG research has expanded from early models like GPT-3 and ChatGPT into specialized techniques across different stages of the LLM lifecycle.

**Dense Passage Retrieval for Open-Domain Question Answering** — arXiv:2004.04906 p.5

![2004.04906](figures/2004.04906_p5.png)

This line graph plots top-$k$ accuracy (%) on the y-axis against the number of retrieved passages ($k$) on the x-axis. Multiple colored lines represent the performance of the BM25 retriever compared to the DPR retriever trained on varying amounts of data (1k, 10k, 20k, 40k, and 59k training examples). The figure conveys that the DPR retriever outperforms BM25 across all values of $k$, even when trained on only 1,000 examples.

**From Local to Global: A Graph RAG Approach to Query-Focused
  Summarization** — arXiv:2404.16130 p.4

![2404.16130](figures/2404.16130_p4.png)

The figure depicts a two-stage pipeline consisting of "Indexing Time" and "Query Time" stages, connected by a "community detection" arrow. The indexing stage flows from "Source Documents" through "Text Chunks" and "Entities & Relationships" to create a "Knowledge Graph," which is then used to identify "Graph Communities." The query stage flows upward from these communities through "Community Summaries," "Community Answers," and finally to a "Global Answer" via successive rounds of domain-tailored and query-focused summarization.

**REALM: Retrieval-Augmented Language Model Pre-Training** — arXiv:2002.08909 p.1

![2002.08909](figures/2002.08909_p1.png)

The figure is a flowchart consisting of several shaded boxes connected by downward arrows, representing a data processing pipeline from unlabeled text to an answer. It illustrates the REALM architecture, showing how a neural knowledge retriever selects a document ($z$) from a textual corpus ($\mathcal{Z}$) based on input text ($x$), which is then combined with the query to feed into a knowledge-augmented encoder to predict a masked answer ($y$). A vertical dashed arrow on the right labeled "End-to-end backpropagation" indicates that training signals flow from the final answer prediction back through the entire system, including the retriever.

**GPT-4 Technical Report** — arXiv:2303.08774 p.3

![2303.08774](figures/2303.08774_p3.png)

This scatter plot shows the relationship between compute (x-axis, log scale) and bits per word (y-axis) for next-word prediction on an OpenAI codebase. Gray dots represent observed performance for smaller models, a dashed gray line shows a power law fit to those observations, and a single green dot represents GPT-4's performance. The figure conveys that GPT-4's loss follows the same scaling trend established by smaller models.

**Graph Retrieval-Augmented Generation: A Survey** — arXiv:2408.08921 p.3

![2408.08921](figures/2408.08921_p3.png)

The figure uses three parallel flowcharts to compare Direct LLM, RAG, and GraphRAG approaches, each starting with the same text query and ending with a response. Each flowchart uses boxes for components (LLMs, Retriever, Response) and arrows to indicate the process flow, with the GraphRAG section specifically illustrating the retrieval of "Retrieved Triplets" from a graph structure. The figure conveys that while Direct LLM and RAG provide varying levels of specificity, GraphRAG provides a more precise and comprehensive response by leveraging structured entity-relationship information.

**Llama 2: Open Foundation and Fine-Tuned Chat Models** — arXiv:2307.09288 p.3

![2307.09288](figures/2307.09288_p3.png)

This horizontal bar chart compares the win rates of various Llama 2 chat models against different baseline models (such as ChatGPT-0301 and PaLM-Bison) across three categories: Win, Tie, and Loss. Each bar represents a specific model comparison, with the x-axis measuring the percentage win rate from 0 to 100. The figure conveys the relative helpfulness of Llama 2 models compared to other open-source and closed-source models based on human evaluation.

**Enhancing Scientific Literature Chatbots with Retrieval-Augmented Generation: A Performance Evaluation of Vector and Graph-Based Systems** — arXiv:2602.17856 p.3

![2602.17856](figures/2602.17856_p3.png)

The figure is a flowchart consisting of boxes, arrows, and icons representing the workflow of a vector-based Retrieval-Augmented Generation (RAG) system. It illustrates two main processes: an "Indexing" stage where context chunks are processed by an embedding model to be stored in a vector database, and a "Retrieval" stage where a user question is embedded and used to perform a similarity search against the database to provide context for a Large Language Model (LLM).

**Graph2Idea:Retrieval-Augmented Scientific Idea Generation with Graph-Structured Contexts** — arXiv:2606.09105 p.5

![2606.09105](figures/2606.09105_p5.png)

The figure illustrates the Graph2Idea framework, a two-stage process consisting of "Direction Generation" and "Idea Generation." The first stage (Stage 1) depicts a workflow where an input paper is processed into a query, which is then used for retrieval and expansion to construct a knowledge graph through triple extraction, ultimately yielding graph-derived contexts such as subgraphs. The second stage (Stage 2) shows these subgraphs being processed through prompt strategies (exploration and modification) to populate a direction pool, which then guides the final generation of scientific ideas.

**Graphs of Research: Citation Evolution Graphs as Supervision for Research Idea Generation** — arXiv:2605.14790 p.2

![2605.14790](figures/2605.14790_p2.png)

This figure compares the "Old Paradigm" of research idea generation, the proposed "Graph of Research (GoR)" method, and the "Human Thinking" process. The "Old Paradigm" shows a linear flow from literature retrieval and complex prompts to an LLM/Generator resulting in "weak ideas," while the "GoR" section illustrates a graph-based structure of interconnected nodes and structural signals (such as temporal order and idea fields) that feeds into a "Graph-Aware Idea Generator." The "Human Thinking" panel outlines a five-step cognitive process—Read & Extract, Track time, Assess importance, Absorb inspiration, and Synthesize—which serves as the inspiration for the proposed model.

**Retrieval Augmented Generation of Literature-derived Polymer Knowledge: The Example of a Biodegradable Polymer Expert System** — arXiv:2602.16650 p.4

![2602.16650](figures/2602.16650_p4.png)

The figure displays three numbered examples of user queries (contained in boxes on the left) paired with their corresponding model-generated responses (contained in larger boxes on the right). Blue arrows connect each query to its respective answer, illustrating how specific questions about PHB properties, thermal stability, and crystallization strategies are addressed by the system.

**Reconnecting Fragmented Citation Networks with Semantic Augmentation** — arXiv:2605.12263 p.3

![2605.12263](figures/2605.12263_p3.png)

This bar chart, titled "Paper Distribution," displays the number of papers (on a log scale) assigned to 33 different clusters. Each bar represents a cluster, with the specific paper count labeled above each bar, illustrating a highly skewed distribution where the first two clusters contain the vast majority of papers.

**Graph-Aware Late Chunking for Retrieval-Augmented Generation in Biomedical Literature** — arXiv:2603.22633 p.5

![2603.22633](figures/2603.22633_p5.png)

This flowchart illustrates the five-stage GraLC-RAG framework architecture, beginning with a biomedical document input that undergoes document parsing and graph construction. The process flows through full-document encoding, knowledge graph infusion via a GAT attention layer, structure-aware chunk boundary detection using three signal types, and concludes with graph-guided hybrid retrieval that combines dense similarity and KG proximity to rank chunks.
