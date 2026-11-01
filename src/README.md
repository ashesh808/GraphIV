# Reusable Python components

The source packages hold research logic and tool implementations. Import them as
`src.core`, `src.retrieve`, `src.miner`, `src.report`, or `src.mcp`.

| Package | Responsibility |
| --- | --- |
| [`core/`](core/README.md) | Shared types, configuration, graph loading, and external clients |
| [`retrieve/`](retrieve/README.md) | BoundedField retrieval and ranking over the citation graph |
| [`miner/`](miner/README.md) | LeyLine evidence, lineages, disputes, and recent successors |
| [`report/`](report/README.md) | Report composition, method tables, and citation grounding |
| [`mcp/`](mcp/README.md) | MCP tool implementations, research state, and effort settings |
| [`storage/`](storage/README.md) | The boundary for persistence code |
| [`evidence/`](evidence/README.md) | The boundary for evidence handling |

The existing dependency order is `mcp` → `report` → `miner` → `retrieve` → `core`.
Import-linter checks those layers. HTTP transports and application startup live in
[`apps/api/`](../apps/api/README.md); batch workflows live in
[`offline/`](../offline/README.md), and evaluation utilities in
[`research/`](../research/README.md).

Retrieval and mining settings live together in [`retrieval_recipes/`](../retrieval_recipes),
one TOML file per mode. Install the project with `uv sync` before running scripts.
