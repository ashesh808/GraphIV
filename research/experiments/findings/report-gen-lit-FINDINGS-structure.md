# Citation structure as an input to the writing step

## 1. What each system feeds the writer

1. SurveyG (2510.07733, sec 3.1.2) partitions retrieved papers into Foundation, Development and Frontier by a trending score and a year landmark T, then (sec 3.1.3, Algorithm 1) runs a weighted BFS from each foundation paper down through Development to Frontier and summarizes each traversal into one `T_path`.
2. SurveyG's writer (sec 3.2.1) receives K vertical path summaries plus N horizontal Leiden-community summaries as text, and the outline prompt asks for `proof_ids` drawn "from either taxonomy layer or vertical direction", so the path reaches the writer as prose, not as a structure the writer must respect.
3. HiReview (2410.03761, sec 4.2.1 and 4.2.2) clusters the citation graph hierarchically, names each cluster with a GNN-conditioned PLM, and feeds the writer a taxonomy tree plus the papers in the current cluster (sec 4.3).
4. Explaining Relationships Among Research Papers (2402.13426, sec 3.1) feeds the writer three citation-network features as text: a faceted summary per node, a pairwise relationship per edge, and an "enriched citation intent and usage" field that the paper itself calls "a discursive summary of all edges incident to node B".
5. That system's writer prompt (sec 3.3) explicitly says "You can freely reorder the cited papers to adapt to the main ideas", so the graph constrains content but not order.
6. MVSS (2601.09504, sec 3.1) builds a Hierarchical Knowledge Tree over retrieved papers, refines it, then uses tree plus tables as joint constraints on the outline and the survey text (sec 3.3).
7. GRASP (2607.03709, sec 3.1 to 3.3) builds a Graph of Thoughts over claims extracted from the cited papers, prunes it to a Steiner tree of high-betweenness and consensus nodes, adds an Argument-Counterargument graph of support/contrast/neutral edges, and serializes both layers as JSON node-link into the writer prompt.
8. GRASP's graph is built from the target paper's own reference list and paper text, not from a citation graph, so it is a semantic and argumentative structure rather than a citation structure.
9. Generating Related Work (2104.08668, sec 3.2) generates a depth-2 tree of the cited papers as an explicit content plan before surface realization, supervised by human section-segmentation annotations.
10. GraphRAG (2404.16130, sec 2.4 to 2.6) feeds the writer Leiden community summaries over an LLM-extracted entity graph from source text, which is not a citation graph and carries no temporal direction.
11. HippoRAG (2405.14831, sec 3.3) is a retrieval system only, reporting recall@2, recall@5, EM and F1, and feeds no structure to a writer.
12. Graphs of Research (2605.14790, abstract) turns a 2-hop reference neighborhood into a paper-evolution DAG and uses it as supervised fine-tuning input for research idea generation, which is a generation step but not a review-writing step.
13. RePaGer (2110.06354, sec IV) builds a node-edge weighted Steiner tree over a citation graph and outputs an ordered reading path, with no writer at all.
14. THE-Tree (2506.21763, sec 3.3) builds a technology evolution tree by MCTS with a Think-Verbalize-Cite-Verify step, and feeds it to a verifier and to link-prediction tasks, not to a writer.
15. The Scientific Contribution Graph (2605.15011, abstract) links 2M extracted contributions by 12.5M prerequisite edges and feeds a prediction task, not a writer.
16. SciTraj (2606.22342, sec 2) builds a claim-grounded typed citation graph containing 287M typed trajectories of length at least 3, and feeds link prediction and analysis, not a writer.

## 2. How each one is evaluated, and whether the structure is scored

17. SurveyG (sec 4.1.4) evaluates only outline quality by LLM judge, five content metrics (Coverage, Structure, Relevance, Synthesis, Critical Analysis) and NLI-based citation recall, precision and F1, so the vertical path is never compared to anything.
18. SurveyG's only isolation of the path is an ablation (sec 4.7, Table 6): full model 91.98 / 86.78 / 94.81 / 85.44 / 83.34 against w/o Vertical Traversal 90.51 / 85.05 / 93.91 / 84.92 / 84.28, so removing the path costs 1.7 points of Structure and improves Critical Analysis by 0.94.
19. HiReview (sec 5.2) uses LLMScore over Coverage, Structure and Relevance plus BertScore against human reviews, and the ablation w/o taxonomy (sec 5.3) drops Coverage 0.9163 to 0.8612, Structure 0.9484 to 0.8790 and Relevance 0.9428 to 0.9078, with the tree itself never scored.
20. 2402.13426 evaluates by ROUGE against the human related work section (sec 5, Automatic Evaluation) and an eight-axis human rating covering fluency, organization and coherence, relevance, factuality, usefulness, writing style and overall quality (sec 4.2), and the citation-network features are isolated only by ablating input variants E, F and G (sec 4.3).
21. MVSS (sec 4.2) is the only survey system that gives the structure its own score, a 1 to 5 LLM Likert "TreeQuality" covering hierarchy correctness, branch coverage and clarity of grouping, reported in the appendix as HKT 4.50 / 4.80 / 4.30 / 3.60 against naive generation 3.90 / 4.37 / 4.53 / 2.50.
22. MVSS's TreeQuality is an absolute judge rating, not a comparison against any reference tree, so it measures whether a tree looks good and not whether it is right.
23. GRASP (sec 4.3) is the only related work system with an order-aware automatic metric, edge-connected Jaccard similarity at paragraph level for grouping and Kendall's tau for citation ordering, both computed between the generated text and the target text.
24. GRASP's own numbers (sec 5.5, Table 4) show pruned GRASP at Jaccard 0.847 and tau 0.886 against the L&O baseline at 0.791 and 0.887, and the paper states the baseline used "a simple, and apparently very strong, chronological ordering heuristic", so a date sort ties the graph method on order.
25. 2104.08668 scores its content-plan tree directly by cluster purity against human segmentation annotations (sec 6, Content Planning) and by a 26-class citation-reason classifier at 85% accuracy, which scores grouping only and never order.
26. GraphRAG (sec 3.4) uses head-to-head LLM-judge comparison on comprehensiveness, diversity, empowerment and a directness control, with no metric on the communities.
27. Graphs of Research (2605.14790, abstract) evaluates only by head-to-head LLM-judge tournaments on the generated ideas, so the citation evolution DAG is never scored.
28. ArxivDIGESTables (2410.22360, sec 5.1) does score an intermediate structure directly, defining schema alignment as a featurizer plus scorer, calibrating DecontextEval to 70 to 85% precision against human raters, and bounding it with exact match below and Llama 3 aligners at 37 to 55% precision above.
29. ArxivDIGESTables' structure is a table schema of comparison aspects, not citation structure, but its method of calibrating the aligner against human agreement before reporting recall is the correct template for any structure metric.
30. SurveyForge's SurveyBench (2503.04629, sec 3.3) scores references by SAM-R, the overlap between the generated bibliography and a curated topic reference set, and scores the outline by a single 0 to 100 LLM score, so no structure is compared to a reference structure.
31. Meow (2509.19370, sec 3.5 and 4.2) uses tree edit distance between the generated outline and the human outline both as an RL reward and as a reported metric, which is a genuine structure-against-reference-structure metric, but the structure is a section outline, not citation structure.
32. RWGBench (2606.24894, sec 4.3.1) defines Positioning Structure Similarity as a soft longest-common-subsequence over SciBERT-embedded ordered content blocks, penalizing missing, extra and reordered blocks, and states it is a reference-relative diagnostic because sections can be organized in several defensible ways.

## 3. Who evaluates an extracted lineage or trajectory directly

33. Nobody evaluates an extracted citation-graph lineage that is fed to a writer, because the two literatures do not overlap: the systems that feed a path to a writer score only the text, and the systems that score a path directly do not have a writer.
34. THE-Tree (2506.21763, sec 4.2.1, Table 3) scores its extracted evolution tree against expert-refined ground truth at entity Recall 0.84, Precision 0.67, F1 0.75 and relation Recall 0.78, Precision 0.64, F1 0.70, with an average parent-child year gap of 3.08 against the expert 2.93.
35. THE-Tree's metric definitions (App B.3) are node recall, node precision, edge recall, edge precision, F1 and average temporal interval, and its ground truth (App B.2) is MCTS trees corrected by domain experts, with the underlying paper and concept nodes extracted from curated surveys (App A.2).
36. THE-Tree also scores structure by graph completion, Hit@1 0.7214 for the tree against 0.5854 for a traditional citation graph under Qwen2.5-72b (sec 4.2.2, Table 4), and by future path prediction, entity Hit@1 0.2813 against 0.1831 (sec 4.3, Table 5).
37. SciTraj (2606.22342, sec 6.3) scores trajectory coherence by human Likert, 70% of 70 sampled trajectories rated coherent by 3-annotator majority with mean 3.81 out of 5, and length-3 chains more coherent than length-4 at 73% against 65%.
38. SciTraj (sec 4.2) supplies the falsifiability protocol that any temporal structure metric needs, a year-shuffle with a pre-specified epsilon of 0.05, under which SciTraj-Pair drops AUC 0.914 to 0.626 while every other model moves by at most 0.025.
39. SciTraj (sec 3.5) makes the point explicitly: "A metric that does not drop under shuffling is not measuring temporal information", and reports that silhouette and Calinski-Harabasz are unchanged under shuffle while year-rank coherence and temporal coherence collapse.
40. The Scientific Contribution Graph (2605.15011, abstract) scores its prerequisite edges by temporally filtered backtesting at 0.48 MAP.
41. RePaGer (2110.06354, sec VI-B) scores the reading list as a set against survey reference lists, reaching F1 0.2343 and precision 0.4743 at 30 seed nodes, with reference sets tiered as L1, L2, L3 by how many times the survey cites each paper (sec II-B).
42. RePaGer states plainly (sec II-C) that "it is not accurate to evaluate whether the specific reading path is correct or not with metric evaluation" and that ordering must be judged by humans, and its order is evaluated only by a 16-participant preference study on prerequisite, relevance and completeness (sec VI-C).
43. ACL-rlg (2502.15692, abstract) formally defines reading list generation as a retrieval task, confirming that the field treats a reading path as a set problem.
44. Understanding Main Path Analysis (2512.12355, abstract) evaluates main paths only against network-theoretic criteria on artificial DAGs and over twenty real networks, never against survey ground truth or a narrative, and concludes "We find no advantage in using the traditional main path methods".
45. No paper found measures the ORDER of an extracted citation path against a human survey by an automatic metric.

## 4. Table

| system | structure fed to the writer | form | evaluation | structure itself scored |
| --- | --- | --- | --- | --- |
| SurveyG 2510.07733 | Foundation/Development/Frontier layers plus BFS traversals | K path summaries plus N community summaries, as prose | LLM judge on outline and 5 content metrics, NLI citation P/R/F1 | no, only a downstream ablation, Table 6 |
| HiReview 2410.03761 | hierarchical citation-graph clustering | named taxonomy tree | LLMScore coverage/structure/relevance, BertScore | no, only a w/o taxonomy ablation, Table 2 |
| 2402.13426 | faceted node summaries, pairwise edge relations, per-node edge digest | text fields in the prompt | ROUGE plus 8-axis human rating | no, only input-variant ablations |
| MVSS 2601.09504 | Hierarchical Knowledge Tree plus tables | tree, order not modeled | LLM Likert on survey, tree and tables | yes, absolute 1 to 5 LLM Likert, no reference tree |
| GRASP 2607.03709 | Graph of Thoughts over claims, Steiner-pruned, plus support/contrast graph | JSON node-link | ROUGE/BERTScore, discourse roles, citation importance, Jaccard, Kendall tau | partially, order and grouping of the generated text, not of the structure |
| 2104.08668 | depth-2 grouping tree over cited papers | tree, ordered segments | ROUGE, BertScore, perplexity, human relevance and fluency | yes, cluster purity against segmentation annotations, grouping only |
| GraphRAG 2404.16130 | Leiden communities over an LLM entity graph | community summaries | head-to-head LLM judge on 4 axes | no |
| HippoRAG 2405.14831 | none, retrieval only | n/a | recall@2, recall@5, EM, F1 | no |
| Graphs of Research 2605.14790 | 2-hop reference DAG | structured-text prompt for SFT | LLM-judge tournaments on ideas | no |
| ArxivDIGESTables 2410.22360 | none, schema is the output | table schema | DecontextEval schema recall plus value eval | yes, against a reference schema, calibrated to human raters |
| Meow 2509.19370 | none, outline is the output | section tree | LLM judge plus tree edit distance to human outline | yes, against a reference outline |
| RWGBench 2606.24894 | none, it is a benchmark | ordered content blocks | citation P/R, CSC, TRT, CD, CDB, PSS, CFA | order of the generated text, against the reference text |
| RePaGer 2110.06354 | none, path is the output | Steiner tree, ordered reading path | set P/R/F1 against survey reference lists, human study on order | set yes, order explicitly refused |
| THE-Tree 2506.21763 | none, tree feeds a verifier | evolution tree | node and edge P/R/F1 against expert-refined trees, graph completion, future path | yes, both nodes and edges |
| SciTraj 2606.22342 | none, corpus resource | typed trajectories | typed link prediction AUC, year-shuffle test, human chain coherence | yes, plus a falsifiability null |
| Sci Contribution Graph 2605.15011 | none, resource | prerequisite edges | temporally filtered backtesting, 0.48 MAP | yes |

## 5. Novelty of the claim

46. "Citation structure should be an input to the writing step" is NOT novel and must not be claimed, since SurveyG (sec 3.2.1), HiReview (sec 4.3), MVSS (sec 3.3) and Graphs of Research all already do it.
47. "The structure should be a lineage from foundational papers forward to frontier papers" is NOT novel either, since SurveyG's Algorithm 1 produces exactly a Foundation to Development to Frontier traversal and hands the resulting `T_path` to the writer.
48. LeyLine and SurveyG's vertical traversal are the same object built by different walks, so the design contribution is at most the walk, not the representation.
49. What IS novel is scoring the extracted lineage directly against human surveys with the ORDER included, because no paper found does this.
50. The two halves of that gap are each occupied but never joined: RePaGer scores the set against surveys and explicitly refuses to score the order (sec II-C), and THE-Tree scores nodes and edges against expert-refined trees but has no writer and needs experts.
51. GRASP scores order by Kendall's tau (sec 4.3) but between two texts, so it cannot tell whether a structure was right, only whether a writer reproduced an ordering.
52. The user's specific candidate metric, path precision defined as "when the walk claims X sits on the path from A to F, does the survey also cite X", is already published twice: it is RePaGer's overlapping metric on the reading list (2110.06354, sec VI-B) and SurveyForge's SAM-R (2503.04629, sec 3.3).
53. That metric is also the wrong test for this system, because it scores a set and LeyLine already failed as a set-producing ranker this session, so it would re-run the losing experiment under a new name.
54. The defensible framing is therefore a metric contribution plus whatever result it produces, not an architecture contribution, and the honest prior is weak: the only two published ablations that isolate a path are SurveyG's Table 6, where removing the path costs 1.7 Structure points and gains 0.94 Critical Analysis points, and HiReview's Table 2, which ablates a tree rather than a path.
55. GRASP's L&O baseline reaching Kendall tau 0.887 with a plain chronological heuristic (sec 5.5) is the single most dangerous published number for this claim, since it says a date sort already reproduces human citation order.

## 6. Proposed metric using only data GraphIV has

56. Use the 6,239 survey pairs as endpoint anchors rather than as a reference set, since the pair supplies both an A and an F that are dated and human-selected.
57. For a pair with earlier survey S_old at date t0 and later survey S_new at t1, define A as `refs(S_old) INTERSECT refs(S_new)`, the foundational papers both authors kept, and F as `refs(S_new)` restricted to papers dated after t0.
58. Run LeyLine from A to F with `--set-max-date t1` and `--set-exclude` on both survey ids, which GraphIV already supports, so the walk sees only the world S_new's author saw.
59. M1 interval hit rate, the fraction of the walk's interior nodes that appear in `refs(S_new)`, reported only as a floor and labeled as the published RePaGer and SAM-R metric, never as the headline.
60. M2 order fidelity, Kendall's tau-b between the walk's node order and the order of first in-text mention of those same nodes in S_new's full text, which GraphIV holds in the html store.
61. M2 is the novel measurement, since it scores an extracted structure's order against a human text, whereas GRASP (sec 4.3) scores a generated text's order against a human text.
62. M3 edge precision, the fraction of consecutive walk pairs (X, Y) that carry a real resolved citation edge in `citations` whose intent label is a use or extend class rather than background, which is THE-Tree's edge precision (App B.3) computed without experts because GraphIV owns 72.8M labeled edges.
63. M4 co-mention rate, the fraction of consecutive walk pairs that appear in the same paragraph of S_new, using paragraph rather than sentence granularity because GRASP (sec 4.3) reports sentence co-occurrence yields only two to three edges per section.
64. M5 bridge necessity, the fraction of interior nodes whose deletion disconnects A from F within the same hop budget, which distinguishes a path from a ranked list and directly tests the failure mode already measured for LeyLine as a ranker.
65. Report M2 through M5 as per-pair distributions with bootstrap confidence intervals over the 6,239 pairs, not as means alone, because SurveyG's and HiReview's single-number ablations are exactly the weak evidence this metric is meant to replace.
66. Null N1, date sort: take the same node set the walk returned, order it by publication date, and rescore M2, since GRASP's L&O baseline (sec 5.5, tau 0.887) makes this the null most likely to kill the claim.
67. Null N2, random shortest path: any shortest path from a random member of A to a random member of F, which separates the walk from mere connectivity.
68. Null N3, degree walk: at each step take the most-cited neighbor, which separates the walk from popularity and is the generic-hub failure this repo already documents.
69. Null N4, year shuffle: permute publication dates across the candidate pool, rebuild the walk, and rescore, with epsilon pre-specified at 0.05 following SciTraj (sec 4.2), and discard M2 and M3 before publication if they do not drop by at least epsilon.
70. Null N5, wrong-topic survey: score the walk against a survey drawn from a different topic leaf, which sets the floor for M1 and M4.
71. N1 is the null that decides the claim, since M1 is already published, M4 and M5 are descriptive, and only M2 beating a date sort would show that citation structure carries ordering information that chronology does not.
72. Calibrate any LLM or embedding component of M2's mention-order extraction against human agreement on a sample before reporting the number, following ArxivDIGESTables (sec 5.1), which bounded its aligner between exact match and a 37 to 55% precision LLM aligner before settling on 70 to 85% precision.
