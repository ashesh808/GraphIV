import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

test("saved research paths render dated inspector links, legacy arXiv fallbacks, and qualified predictions", () => {
  const script = `
    import { createElement } from "react";
    import { renderToStaticMarkup } from "react-dom/server";
    import { ResearchPaths } from "./components/research-paths.ts";
    const paper = { arxiv_id: "1706.03762v2", date: "2017-06-12", title: "Known <em>source</em>" };
    const props = {
      lineages: [{ name: "A saved lineage", description: "Actual saved lineage description", papers: [paper] }],
      successors: [{ arxiv_id: "hep-th/9901001", date: "1999-01-02", title: "A legacy follow-up", reach: 2, intents: ["extends", "critiques"], sentence: "This must not become a quote" }],
      papers: [{ arxiv_id: "1706.03762" }],
      onSelectId: () => { throw new Error("Rendering cannot open an inspector"); }
    };
    console.log(JSON.stringify([
      renderToStaticMarkup(createElement(ResearchPaths, props)),
      renderToStaticMarkup(createElement(ResearchPaths, { lineages: [], papers: [], onSelectId: () => {} }))
    ]));
  `;
  const rendered = spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", script], {
    cwd: new URL("..", import.meta.url), encoding: "utf8",
  });
  assert.equal(rendered.status, 0, rendered.stderr);
  const [paths, legacy] = JSON.parse(rendered.stdout);
  assert.match(paths, /id="report-lineages"/);
  assert.match(paths, /id="report-successors"/);
  assert.match(paths, /Actual saved lineage description/);
  assert.match(paths, /<time dateTime="2017-06-12">2017-06-12<\/time>/);
  assert.match(paths, /<button[^>]+aria-label="Inspect Known &lt;em&gt;source&lt;\/em&gt;"/);
  assert.match(paths, /href="https:\/\/arxiv.org\/abs\/hep-th\/9901001"/);
  assert.match(paths, /Precomputed citation-intent labels are predictions, not quotations/);
  assert.match(paths, /Predicted intents: extends, critiques · Cites 2 papers in this review/);
  assert.equal(paths.includes("This must not become a quote"), false);
  assert.equal(paths.includes("<blockquote>"), false);
  assert.equal(paths.includes("<em>"), false);
  assert.equal(legacy, "");
});
