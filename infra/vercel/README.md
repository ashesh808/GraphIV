# Vercel frontend project

This Terraform root manages the Next.js project in [`apps/web`](../../apps/web/README.md)
and its server-side `GRAPHIV_API_URL` setting. The backend and storage belong to the
separate [`infra/azure`](../azure/README.md) root. Pass Azure's `backend_url` output
here; the two roots do not share Terraform state.

The project uses `apps/web` as its root, Next.js framework detection, Node.js `22.x`,
and the GitHub repository `ashesh808/GraphIV`. The frontend's Node engine range
is limited to compatible Node.js 22 releases. `production_branch` defaults to `main`.
Merge the frontend commit into that branch before enabling builds, or set this variable
to the branch containing `apps/web`, such as `ashesh/refactor-deployment-frontend`.
Build commands remain under Vercel's framework detection and Git integration.

Install Terraform 1.7 or newer. The provider is constrained to Vercel `5.24.x`, with
the selected version and checksums recorded in `.terraform.lock.hcl`.
Before planning against an account, install the
[Vercel GitHub app](https://vercel.com/docs/git/vercel-for-github) and authorize the
repository. Supply an authorized token through `VERCEL_API_TOKEN`; it is read by
the provider rather than stored as a Terraform variable.

```sh
cd infra/vercel
terraform init
cp terraform.tfvars.example terraform.tfvars
# Replace backend_url with the externally reachable Azure backend origin.
# Set VERCEL_API_TOKEN in your shell using your usual credential workflow.
terraform plan -out=tfplan
```

`backend_url` is required and must be an HTTPS DNS origin without credentials or
an API path. It must serve the run-reading endpoints used by the web app.
The optional `team` value accepts a Vercel team slug or ID; omit it for the token's
default scope. The backend origin is set for production, preview, and development.
It uses the server-only `GRAPHIV_API_URL` key, with no `NEXT_PUBLIC_` prefix.

This root configures the project and environment variable; it does not upload
builds or create deployment resources. Subsequent Git pushes drive Vercel builds.
Find actual production and preview URLs in the Vercel dashboard after successful
deployments. Custom domains and deployment-protection settings are not managed here.
Environment changes affect subsequent deployments. State defaults to local storage;
configure your state backend before sharing this root with other operators.

Offline checks use a mocked provider and need neither a token nor cloud access:

```sh
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
terraform test
```

The configuration follows the official
[project schema](https://registry.terraform.io/providers/vercel/vercel/5.24.1/docs/resources/project),
[environment-variable schema](https://registry.terraform.io/providers/vercel/vercel/5.24.1/docs/resources/project_environment_variable),
and [provider authentication](https://registry.terraform.io/providers/vercel/vercel/5.24.1/docs).
