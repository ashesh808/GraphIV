# How people fold a list of papers into something with a shape

Read 2026-09-19 from three runs of this system at effort 5, plus web search for the products that
publish nothing. The runs are `answers/narrative_structure_5.md`, `answers/survey_outline_5.md` and
`answers/claim_structure_5.md`.

## The six shapes in use

| shape | what the structure is | who does it |
| --- | --- | --- |
| outline first, then fill | a table of contents drafted from the retrieved set, sections written in parallel against it | AutoSurvey, AutoSurvey2 `2510.26012`, SurveyForge `2503.04629`, STRUCTSURVEY `2607.01243`, OUTLINEFORGE `2601.09858` |
| taxonomy induction | a tree of concepts clustered out of the retrieved set, which becomes the sections | TaxoAlign `2510.17263`, SC-Taxo `2605.00620`, `2509.19125`, Term-Centric Hierarchy Induction `2606.26963` |
| citation graph as the spine | the graph's own layers order the papers before anything is written | SurveyG `2510.07733`, Local-to-Global sentence graph reranking `2608.30525` |
| contribution or method graph | nodes are contributions or methods, edges are prerequisite or lineage | Scientific Contribution Graph `2605.15011`, Intern-Atlas `2604.28158`, HGNet `2603.23136` |
| typed-edge trajectories | chains of typed citation relations, each edge carrying its claim sentence | SciTraj `2606.22342` |
| the extraction table | a matrix of papers by field, every cell backed by a supporting quote | Elicit, ComProScanner `2510.20362`, `2604.07584`, LitCurate `2608.27629` |

## What the products do, none of which publish

| product | what it is | scale it claims |
| --- | --- | --- |
| Elicit | the extraction table as the whole product, columns chosen by the user, every cell backed by a quote from the paper, including from tables and figures | claims 94% screening and 94 to 99% extraction accuracy, and up to 80% time saved |
| scite | every citation statement classified supporting, contrasting or mentioning, shown with the sentence | 1.4B citation statements over 38M papers |
| Consensus | search plus a synthesis line and the Consensus Meter | 200M+ papers |

**scite is 19x our labeled citation scale.** 1.4B classified statements over 38M papers against our
73.8M over 3.13M. My earlier claim that we hold the largest intent-labeled citation set was wrong.
What is still ours there is six intents against their three, an open corpus against a paid API, and
the fact that nothing is built on top of theirs.

## What nobody joins up

| gap | why it is open |
| --- | --- |
| stance edges plus an extraction table | Elicit extracts from papers you hand it and has no citation graph. scite has the stance and builds no document. Neither knows which pairs are worth comparing |
| a number checked against a second source | every extraction table quotes the paper about itself, which is the paper's own claim. A number reported about X by a paper that benchmarks against X is independent, and the `compares` edges say exactly where those live |
| structure derived rather than drafted | outline-first systems are graded on outline quality against human surveys, which measures writing. A spine taken from typed edges is a measurement, not a draft |

## What this implies for the ten minute level

1) Do not draft an outline and do not induce a taxonomy. Both are the model inventing structure.
   The lineage from Leyline is already a spine and it came out of the data.
2) The table is the deliverable, and the `compares` edges choose its rows and columns rather than a
   schema the model invents per question. That is the fix for the 0.17 to 0.29 extraction recall the
   old key-value schema hit.
3) Every cell carries who reported it. Where two independent sources give the same cell, agreement
   is a free metric on generated output, which is the first one this project would have.
4) Keep quoting sentences. Elicit's supporting quote and scite's citation statement are both the
   same admission: a reader does not trust a generated cell unless the source text is next to it.

## Sources

- Elicit systematic review, https://elicit.com/solutions/systematic-review
- How we evaluated Elicit Systematic Review, https://elicit.com/blog/how-we-evaluated-elicit-systematic-review
- scite smart citations, https://scite.ai/features
- scite in Quantitative Science Studies, https://direct.mit.edu/qss/article/2/3/882/102990/
- SurveyForge, https://arxiv.org/abs/2503.04629
- SurveyBench, https://arxiv.org/html/2510.03120
