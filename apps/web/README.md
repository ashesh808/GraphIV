# GraphIV web

A Next.js reading workspace for saved GraphIV research. The library supports search,
mode filtering, and sorting, with those choices stored in the URL. Each report opens
on Report, Papers, and Graph tabs, with a shared paper inspector, Markdown download,
and light/dark themes. Research submission and workflow orchestration remain future work.

## Run locally

Use Node.js 22.6 or newer. Start the Python read service from the repository root:

```sh
uv run graphiv-serve --http --role frontend
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

The Python `frontend` role exposes the read-only run endpoints this app needs.
The `both` role also exposes them; the `api` role alone serves MCP tools without
the library endpoints. Match `GRAPHIV_API_URL` to the chosen listener's address and port.

With no URL configured, the app tries `http://127.0.0.1:6969` and shows clearly labelled
examples when that local service cannot be reached. An explicitly configured backend
surfaces connection errors instead of substituting examples. Backend requests run only
on the Next.js server, so `GRAPHIV_API_URL` stays server-side and browser access needs
no cross-origin connection to Python.

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
