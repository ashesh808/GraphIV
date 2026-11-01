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

The current Python runtime still uses PostgreSQL and local graph/report files. Its Blob
adapters and orchestration are unfinished, and it does not consume the new Azure environment
contract. The existing Docker image alone cannot run this architecture. Follow the
[Azure compatibility requirements](azure/README.md#compatible-image-contract) before activation.
The existing Nix deployment remains in [`legacy/nix`](../legacy/nix/README.md).

Use Terraform 1.12 or newer to work with both roots; Vercel alone supports 1.7 or newer.
Each root has its own lock file and state. Azure includes examples for an existing
Microsoft Entra-authenticated state backend. No cloud deployment has been run.

Local validation uses mocked providers without cloud credentials:

```sh
terraform -chdir=infra/azure init -backend=false
terraform -chdir=infra/azure validate
terraform -chdir=infra/azure test
terraform -chdir=infra/vercel init -backend=false
terraform -chdir=infra/vercel validate
terraform -chdir=infra/vercel test
```
