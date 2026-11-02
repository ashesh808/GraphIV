# Infrastructure

Two independent Terraform roots configure the hosting services:

| Root | Manages | Handoff |
| --- | --- | --- |
| [`azure/`](azure/README.md) | Blob containers, registry, Key Vault, logging, managed identity, and an optional Container App | Its `backend_url` output becomes the Vercel input |
| [`vercel/`](vercel/README.md) | Next.js project, GitHub connection, and server-only `GRAPHIV_API_URL` | Git integration performs frontend builds and deployments |

Bootstrap Azure with `api_image_tag = null`. This creates supporting resources without
starting an API. Publish a compatible backend image, populate its external LLM credential
in Key Vault, and then enable the Container App. Pass the resulting backend origin into
the separate Vercel root. LLM services and arXiv are external services, not Terraform resources.

The Python runtime supports local PostgreSQL and Azure-backed immutable FAISS/SQLite/graph
snapshots, with Blob-persisted report artifacts. It consumes the deployment environment
contract, authenticates backend and external-model requests, and runs serialized research
jobs. Health endpoints remain available while corpus preparation is pending. Publish a
coherent corpus manifest and configure matching embedding/LLM endpoints before expecting
research readiness; an empty library remains empty. See the
[runtime contract](azure/README.md#runtime-settings).
The existing Nix deployment remains in [`legacy/nix`](../legacy/nix/README.md).

Use Terraform 1.12 or newer for both roots, including ephemeral write-only credentials.
Each root has its own lock file and state. Azure includes examples for an existing
Microsoft Entra-authenticated state backend. The procedures below describe configuration
and checks; deployed URLs and readiness should be verified separately.

Local validation uses mocked providers without cloud credentials:

```sh
terraform -chdir=infra/azure init -backend=false
terraform -chdir=infra/azure validate
terraform -chdir=infra/azure test
terraform -chdir=infra/vercel init -backend=false
terraform -chdir=infra/vercel validate
terraform -chdir=infra/vercel test
```
