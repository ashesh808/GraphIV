import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

test("the report evidence note renders as labelled, escaped text and stays absent for older reports", () => {
  // The main tests use the react-server condition for server-only data modules.
  // Render this shared UI in a normal React process, as the browser bundle does.
  const script = `
    import { createElement } from "react";
    import { renderToStaticMarkup } from "react-dom/server";
    import { EvidenceNote } from "./components/evidence-note.ts";
    console.log(JSON.stringify([
      renderToStaticMarkup(createElement(EvidenceNote, { note: 'Citation text unavailable. <script>alert("unsafe")</script>' })),
      renderToStaticMarkup(createElement(EvidenceNote, {}))
    ]));
  `;
  const rendered = spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", script], {
    cwd: new URL("..", import.meta.url), encoding: "utf8",
  });
  assert.equal(rendered.status, 0, rendered.stderr);
  const [qualified, legacy] = JSON.parse(rendered.stdout);
  assert.match(qualified, /aria-label="Evidence availability"/);
  assert.match(qualified, /Citation text unavailable/);
  assert.match(qualified, /&lt;script&gt;/);
  assert.equal(qualified.includes("<script>"), false);
  assert.equal(legacy, "");
});
