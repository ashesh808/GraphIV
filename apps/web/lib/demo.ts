import type { Paper, RunDetail, RunSummary } from "./types";

// Curated interface examples, not generated GraphIV research runs. The questions
// follow the retrieval, frontier, and grounding themes in the repository's docs.
const paper = (
  arxiv_id: string,
  title: string,
  authors: string,
  date: string,
  role: string,
  abstract: string,
): Paper => ({
  arxiv_id, title, authors, date, year: date.slice(0, 4), role, abstract,
  category: "cs.CL", cited: false, retrieved: true, relevance: null, cosine: null, topic: [],
});

const attention = paper(
  "1706.03762", "Attention Is All You Need", "Ashish Vaswani, Noam Shazeer, Niki Parmar et al.", "2017-06-12", "foundational",
  "The Transformer architecture provides context for the language models in this example reading list.",
);
const dpr = paper(
  "2004.04906", "Dense Passage Retrieval for Open-Domain Question Answering", "Vladimir Karpukhin, Barlas Oğuz, Sewon Min et al.", "2020-04-10", "core",
  "A starting point for reading about dense passage retrieval and its role in open-domain question answering.",
);
const rag = paper(
  "2005.11401", "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", "Patrick Lewis, Ethan Perez, Aleksandra Piktus et al.", "2020-05-22", "core",
  "A reference for studying the connection between retrieved passages and language generation.",
);
const realm = paper(
  "2002.08909", "REALM: Retrieval-Augmented Language Model Pre-Training", "Kelvin Guu, Kenton Lee, Zora Tung et al.", "2020-02-20", "foundational",
  "A related approach to incorporating retrieval into language model pre-training.",
);
const specter = paper(
  "2004.07180", "SPECTER: Document-level Representation Learning using Citation-informed Transformers", "Arman Cohan, Sergey Feldman, Iz Beltagy et al.", "2020-04-15", "core",
  "A reference for scientific document representations learned with citation information, also discussed in GraphIV's research notes.",
);
const colbert = paper(
  "2004.12832", "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT", "Omar Khattab, Matei Zaharia", "2020-04-27", "adjacent",
  "A complementary retrieval architecture to compare with single-vector dense retrieval.",
);

interface ExampleSpec {
  slug: string;
  question: string;
  summary: string;
  asked: string;
  mode: string;
  effort: string;
  papers: Paper[];
  answer: string;
  opening: string;
  claims: { title: string; body: string }[];
  openQuestions: string[];
}

function createExample(spec: ExampleSpec): RunDetail {
  const { openQuestions, answer, opening, claims, ...summary } = spec;
  const areas = [{ question: spec.question, seed: "", papers: spec.papers.map((paper) => paper.arxiv_id), unanswered: openQuestions }];
  return {
    ...summary,
    paperCount: spec.papers.length,
    sections: {
      answer, opening, claims, areas, open_questions: openQuestions,
      methods: { table: "", rows: [], columns: [] },
      lineages: [{
        name: "Example reading path", description: "An illustrative reading order, not a mined citation lineage.",
        papers: [...spec.papers].sort((a, b) => a.date.localeCompare(b.date)).map(({ arxiv_id, date, title }) => ({ arxiv_id, date, title })),
      }],
    },
    graph: {
      nodes: spec.papers.map((paper) => ({
        arxiv_id: paper.arxiv_id, title: paper.title, date: paper.date, role: paper.role,
        cited_by: 0, lines: [1], retrieved: true, cosine: null, magnet: null,
      })),
      // These connections demonstrate the map interaction. They are explicitly
      // labeled illustrative in the example report rather than asserted citations.
      edges: spec.papers.slice(1).map((paper, index) => ({
        source: paper.arxiv_id, target: spec.papers[index].arxiv_id, intent: "background",
        sentence: "Illustrative connection in this example reading list; not extracted citation evidence.", walked: false,
      })),
    },
    report: `# ${spec.question}\n\n> Example report. This is a curated interface demonstration, not a completed research run.\n\n${answer}\n\n## Overview\n\n${opening}\n\n${claims.map((claim) => `## ${claim.title}\n\n${claim.body}`).join("\n\n")}\n\n## Open questions\n\n${openQuestions.map((question) => `- ${question}`).join("\n")}\n\n## Reading list\n\n${spec.papers.map((paper) => `- [${paper.title}](https://arxiv.org/abs/${paper.arxiv_id})`).join("\n")}\n`,
    cited: [], counts: {}, seconds: {},
  };
}

export const exampleReports: RunDetail[] = [
  createExample({
    slug: "example-retrieval-augmented-generation",
    question: "How does retrieval change what a language model can answer?",
    summary: "Retrieval-augmented generation, from finding useful passages to grounding the final answer.",
    asked: "2026-10-28", mode: "survey", effort: "standard",
    papers: [rag, dpr, realm, colbert, attention],
    answer: "Separate the question into two parts: how a system finds useful evidence, and how it uses that evidence when writing. This example reading list keeps both parts visible.",
    opening: "Retrieval-augmented systems connect a searchable collection to a generative model. A useful review examines the retrieval method, the information passed to the model, and the evidence attached to its answer.\n\nThe papers below form a small starting list for that comparison. This is an interface example rather than an exhaustive or up-to-date literature review.",
    claims: [
      { title: "Start with the retrieval–generation boundary", body: "Read [Dense Passage Retrieval](https://arxiv.org/abs/2004.04906) alongside [Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401) to distinguish finding relevant passages from using them to produce an answer. The distinction helps make the assumptions in a system easier to inspect." },
      { title: "Compare evidence, not just answers", body: "Keep the retrieved passages, source papers, and answer together. When a result changes, that context helps a reader determine whether the evidence changed or the model interpreted the same evidence differently." },
    ],
    openQuestions: ["Which evaluation separates retrieval failures from answer-generation failures?", "How should a report expose conflicting evidence to the reader?"],
  }),
  createExample({
    slug: "example-citation-aware-search",
    question: "What does the citation graph add to literature search?",
    summary: "Semantic relevance, citation context, and the papers that connect a research field.",
    asked: "2026-10-24", mode: "survey", effort: "deep",
    papers: [specter, dpr, rag, attention],
    answer: "Similarity offers a starting pool. Citation relationships offer another way to inspect how the papers in that pool connect. GraphIV treats those as separate, inspectable steps.",
    opening: "GraphIV's BoundedField combines semantic retrieval with citation-graph ranking. Its recipes make ranking settings explicit, while LeyLine reads the relationships around the selected papers.\n\nThis example introduces that workflow with a short reading list. The map connections are illustrative and are not extracted citations.",
    claims: [
      { title: "Keep representation and query-time ranking distinct", body: "[SPECTER](https://arxiv.org/abs/2004.07180) is a useful reference for citation-informed document representations. GraphIV's research notes distinguish that training-time use of citation pairs from the graph signals applied when ranking a particular question." },
      { title: "Make the route through the field inspectable", body: "A ranked list tells a reader where to start. A graph view can also show which papers connect the list, provided every displayed relationship can be traced back to its evidence." },
    ],
    openQuestions: ["Which graph relationships improve coverage for a narrowly scoped question?", "How should a reader compare a new paper with one that has accumulated years of citations?"],
  }),
  createExample({
    slug: "example-research-frontiers",
    question: "How do we find important papers before they are widely cited?",
    summary: "Recency, citation signals, and the limits of using past attention to find new work.",
    asked: "2026-10-19", mode: "frontier", effort: "standard",
    papers: [{ ...specter, role: "core" }, { ...dpr, role: "adjacent" }, { ...rag, role: "frontier" }],
    answer: "A paper with few citations needs a different inspection path from an established reference. GraphIV's frontier workflow adds papers responding to the current field instead of relying on citation counts alone.",
    opening: "The repository's frontier experiments ask questions at a historical date and then examine what later research cited. That setup makes the limits of citation-based discovery visible.\n\nThis example uses a compact, historical reading list to demonstrate the report layout; its papers are not presented as the current research frontier.",
    claims: [
      { title: "Keep the question date visible", body: "A frontier result only makes sense relative to the date it was produced. Preserve that cutoff with the report so that a future reader can distinguish what the system knew then from what appeared later." },
      { title: "Separate discovery from later validation", body: "Future citation activity can help evaluate an earlier search. It should not be silently included among the signals available to that original search." },
    ],
    openQuestions: ["What evidence can identify a useful new contribution before it receives citations?", "How should frontier evaluation account for differences between fast and slow-moving fields?"],
  }),
  createExample({
    slug: "example-grounded-reviews",
    question: "What makes a literature review easy to verify?",
    summary: "Readable claims, visible sources, and an explicit boundary between evidence and interpretation.",
    asked: "2026-10-12", mode: "ancestry", effort: "quick",
    papers: [attention, realm, rag],
    answer: "Keep each claim close to its sources, preserve the question and settings that produced it, and make missing evidence visible. A readable answer should remain easy to inspect.",
    opening: "GraphIV's report layer composes a review and checks its cited identifiers against the available corpus. Its legacy dashboard keeps the report, papers, graph, and run details together.\n\nThis curated example demonstrates that reading flow. It does not claim that a research run or citation-verification step was performed.",
    claims: [
      { title: "A citation is a starting point for inspection", body: "A paper title and identifier let a reader open the original source. The next step is checking the relevant passage rather than treating the presence of a citation as proof that a claim is supported." },
      { title: "Retain the context of the result", body: "A report belongs to a particular question, corpus date, and search mode. Keep those inputs available as the reader moves between the written answer and the papers behind it." },
    ],
    openQuestions: ["How can a report communicate uncertainty without hiding its useful findings?", "Which claims require full-text evidence rather than an abstract or citation link?"],
  }),
];

export const exampleSummaries: RunSummary[] = exampleReports.map((run) => ({
  slug: run.slug, question: run.question, asked: run.asked, mode: run.mode,
  effort: run.effort, papers: run.papers.length, summary: run.summary,
}));
