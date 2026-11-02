# GraphIV web

A Next.js workspace for asking research questions and reading saved GraphIV reports. Submit
a question with a research mode and depth, follow queued/running progress, and open the
completed report. The library refreshes when a run finishes and supports search,
mode filtering, and sorting, with those choices stored in the URL. Each report opens
on Report, Papers, and Graph tabs, with a shared paper inspector, Markdown download,
and light/dark themes. Saved research lineages and follow-up papers appear in the Report
view, with dated paper links and precomputed intent labels identified as predictions.
Runs continue on the backend when you leave the page; the current
browser tab remembers its latest job. Failed status checks can be retried without
submitting the question again. There is no cancellation control because the backend
does not offer cancellation.

## Run locally

Use Node.js 22.x (22.6 or newer). Start the Python research and read service from the repository root:

```sh
uv run graphiv-serve --http --role both
```

In another terminal:

```sh
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Open `http://127.0.0.1:3000`. To require a backend connection, uncomment
`GRAPHIV_API_URL=http://127.0.0.1:6969` in `.env.local`. See
[`.env.example`](.env.example) for the connection settings.

The Python `both` role exposes research submission, job status, and saved reports.
The `frontend` role supports saved reports only; the `api` role supports research and
MCP tools without the library endpoints. Match `GRAPHIV_API_URL` to the chosen listener's
address and port. Research requires a configured corpus, matching embedding model,
and LLM; the UI shows the backend's readiness reasons when these are missing.

With no URL configured, the app tries `http://127.0.0.1:6969` and shows clearly labelled
examples when that local service cannot be reached. An explicitly configured backend
surfaces connection errors instead of substituting examples. Backend requests run only
on the Next.js server, so `GRAPHIV_API_URL` stays server-side and browser access needs
no cross-origin connection to Python. Set `GRAPHIV_API_TOKEN` when the backend requires
bearer authentication. Same-origin Next.js routes forward only validated research
inputs and job IDs; the token and backend address are never sent to the browser.
Submission never uses example data.

## Checks and production build

Run these commands from `apps/web`:

```sh
npm test
npm run typecheck
npm run build
npm start
```

`npm test` uses Node's experimental TypeScript stripping.

For Vercel, set the project's root directory to `apps/web` and use Next.js framework
autodetection. Set `GRAPHIV_API_URL` to a backend reachable from the deployed Next.js
server; the localhost default is for local development. Deployment and a backend
hosting environment are configured separately.

The retained static dashboard remains under
[`legacy/research-webui`](../../legacy/research-webui/README.md). Reusable algorithms
and tool implementations live in [`src`](../../src/README.md).
