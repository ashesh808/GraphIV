# Azure Terraform

This root defines GraphIV's backend infrastructure. The frontend project is managed
separately in [`infra/vercel`](../vercel/README.md).

With `api_image_tag = null`, the bootstrap creates a resource group, Storage Account,
four private Blob containers, Azure Container Registry, Key Vault, Log Analytics,
Container Apps environment, user-assigned managed identity, and scoped role assignments.
Supplying an image tag adds one externally reachable HTTPS Container App.

The environment is managed by `azapi_resource.environment` using ARM API
`2026-07-01`, explicitly setting `environmentMode = "WorkloadProfiles"` and the
`Consumption` workload profile. AzureRM 5.12 does not expose that mode field.
AzAPI 2.13's embedded schema does not yet include this published API version, so
embedded validation is disabled for the managed-environment and optional preview
storage-definition resources; mock tests assert their required fields.
Express mode cannot use the Key Vault secret references required here; see the
[Express limitations](https://learn.microsoft.com/en-us/azure/container-apps/express-overview#not-supported)
and [managed-environment API schema](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2026-07-01/managedenvironments).
The environment keeps the same `cae-<project>-<environment>` name. Existing state
bindings under `azurerm_container_app_environment.api` must be migrated/imported
to `azapi_resource.environment` by the operator, rather than managing the same
Azure resource through both Terraform addresses. Mode conversion is not assumed
to happen automatically; verify the real environment mode before activation.

The runtime supports PostgreSQL and Azure Blob-backed immutable SQLite/FAISS/GraphExport
snapshots through the same corpus interface. Report reads and writes persist to Blob.
See [storage and snapshot publishing](../../docs/storage.md). Retrieval and LeyLine
algorithms are shared unchanged between adapters.

## Existing PostgreSQL corpus

`corpus_backend` defaults to `azure`, preserving the snapshot-based deployment.
Set it to `postgres` to use an existing PostgreSQL corpus while report reads and
writes continue using Blob storage. This root does not provision a PostgreSQL
server, load its tables, or establish network access to an external database.

Populate a DSN in Key Vault outside Terraform, using the same file-based secret
workflow described below. Set `postgres_dsn_secret_name` to that secret's name.
When the PostgreSQL mode is selected, the API receives `GRAPHIV_POSTGRES_DSN` through
a managed-identity Key Vault reference; the DSN value is never a Terraform input
or output. API activation requires the secret name, but infrastructure-only
bootstrap with `api_image_tag = null` can omit it.

```hcl
corpus_backend          = "postgres"
postgres_dsn_secret_name = "graphiv-postgres-dsn"
api_environment = {
  GRAPHIV_GRAPH_PATH = "/mnt/graphiv/citation_graph_export.npy"
}
```

The PostgreSQL database must contain the expected corpus schema, be reachable
from the Container App, and use the connection security appropriate to that service.
`GRAPHIV_GRAPH_PATH` must name a GraphExport file already present in the image or
a mounted filesystem. Setting this path does not download a Blob or create a mount;
PostgreSQL mode does not run the Azure snapshot downloader. Without the graph and
database, the app remains live but research readiness stays false.

Report storage still follows the Azure runtime's Blob default. Plaintext DSN and
report-backend overrides are rejected in `api_environment`. The existing Key Vault
Secrets User grant permits the PostgreSQL secret reference, with no new role grants.

## Prerequisites and state

Use Terraform 1.12 or newer and authenticate with Azure CLI or the provider's `ARM_*`
environment variables. Set the real `subscription_id` in a local `terraform.tfvars`.
The deploying identity needs resource creation permissions, role assignment permissions,
and `Microsoft.Authorization/roleDefinitions/write` for the custom roles. Contributor
alone does not grant all of these. See Microsoft's
[custom-role requirements](https://learn.microsoft.com/en-us/azure/role-based-access-control/custom-roles).

Automatic resource-provider registration is disabled in `versions.tf`. An authorized
operator must register the required namespaces in the target subscription before provisioning:

```sh
az account set --subscription YOUR_SUBSCRIPTION_ID
for namespace in Microsoft.App Microsoft.Storage Microsoft.ContainerRegistry Microsoft.KeyVault Microsoft.ManagedIdentity Microsoft.OperationalInsights; do
  az provider register --namespace "$namespace" --wait
done
```

Registration requires the provider's `/register/action` permission. See
[resource-provider registration](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types).

Terraform handles secret names and Key Vault URIs, never API, LLM, or embedding credential values.
Provider-computed sensitive properties can still enter Terraform state. For shared use,
configure the supplied [`backend.tf.example`](backend.tf.example) and
[`backend.hcl.example`](backend.hcl.example) against a separately provisioned state
account/container. The state operator needs Blob data access there. The examples use
Microsoft Entra authentication rather than account keys; see the
[AzureRM state backend](https://developer.hashicorp.com/terraform/language/backend/azurerm).

```sh
cd infra/azure
cp backend.tf.example backend.tf
cp backend.hcl.example backend.hcl
# Replace the state account/container details in backend.hcl.
terraform init -backend-config=backend.hcl
```

These backend examples are optional. Without an active backend block, state is local.
Use separate state per environment. Local tfvars, backend configuration, state, and plan
files stay outside version control; the provider lock file is committed.

## Bootstrap and activate

The API can serve the report library before corpus/model configuration is complete.
`/health/live` tests HTTP serving; `/health/ready` reports research readiness.

1. Copy [`terraform.tfvars.example`](terraform.tfvars.example), set the subscription and
   naming inputs, and keep `api_image_tag = null`. Initialize your chosen state backend,
   review a plan, and apply it when ready. `backend_url` remains null during bootstrap.

   ```sh
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -out=bootstrap.tfplan
   terraform apply bootstrap.tfplan
   ```

2. Build and test the runtime image using `docker buildx build --platform linux/amd64 --load -f apps/api/Dockerfile -t graphiv-api:tested .` from the repository root,
   then publish it to the created registry as `graphiv-api:<tag>`. The image publisher
   needs its own ACR push permission; the API identity receives pull permission only.

   ```sh
   registry_name="$(terraform output -raw registry_name)"
   registry_host="$(terraform output -raw registry_login_server)"
   image_tag="replace-with-tested-tag"
   az acr login --name "$registry_name"
   docker tag graphiv-api:tested "${registry_host}/graphiv-api:${image_tag}"
   docker push "${registry_host}/graphiv-api:${image_tag}"
   ```

3. Generate a strong API bearer token outside Terraform and store it as
   `api_token_secret_name` (default `graphiv-api-token`). Also populate independent
   LLM/embedding secrets when their providers require them. Bootstrap grants the deploying
   identity **Key Vault Secrets Officer**. Supply the credential from a file so it does
   not become a shell-history argument:

   ```sh
   az keyvault secret set \
     --vault-name "$(terraform output -raw key_vault_name)" \
     --name llm-api-key \
     --file /path/to/llm-api-key \
     --output none
   ```

   Use the names selected by `llm_api_key_secret_name` and
   `embedding_api_key_secret_name`. Both default to null, omitting model credentials
   until endpoints are configured. Never reuse a key across unrelated providers. The app references a Key Vault URI
   through its managed identity; see
   [Container Apps secret references](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets).

4. Set `api_image_tag`, then review and apply a new plan. For research, publish a
   corpus manifest and set `llm_api_url`, `llm_model`, `embedding_api_url`, and
   `embedding_model` (must match the snapshot).
   Enable `allow_report_reads = true` if the compatible image serves the library or
   `find_runs`; the default report permission is write-only. Size `api_resources` for
   the downloaded indexes and temporary storage.

5. Once the backend works, read `terraform output -raw backend_url` and put that origin
   into `backend_url` in the [Vercel root](../vercel/README.md). Supply the same API
   token via the Vercel root's ephemeral `api_token` variable. It must be reachable
   from Vercel and expose the web app's read endpoints. The default command uses
   `--role both` to serve MCP and library routes; `api` alone omits the library.

## Persistent corpus cache

`runtime_cache_share = false` preserves the original `EmptyDir` mount and creates
no additional storage or identities. Set it to `true` for a corpus that cannot fit
the replica's temporary disk. This adds an SMB share named `runtime-cache` in the
existing Storage Account, with a 100GiB quota, mounted at `/var/lib/graphiv` in the
API and optional builder. Files survive replica replacement. Reports continue to
persist independently in Blob storage; the share holds rebuildable artifacts and
model caches. Removing the share through Terraform also removes its cached files.

The mount uses a separate user-assigned **environment** identity and the
**Storage File Data SMB MI Admin** role at Storage Account scope. The API identity's
Blob permissions remain unchanged. Account-key authentication stays disabled.
The configuration enables only the nested `smbOAuthSettings.isSmbOAuthEnabled`
property through AzAPI and uses the `2026-03-02-preview` environment-storage API's
`azureFile.identity` field. Microsoft documents this managed-identity mount path
as preview. See [Container Apps SMB mount requirements](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts?pivots=aca-arm#azure-files-volume)
and the [preview storage schema](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2026-03-02-preview/managedenvironments/storages).

Before activation, verify that the account's existing SMB security settings allow
Kerberos; enabling SMB OAuth does not change that policy. Allow RBAC grants to
propagate before mounting. This root preserves the existing SMB policy instead
of replacing it; see [Azure Files identity prerequisites](https://learn.microsoft.com/en-us/azure/storage/files/files-managed-identities#prerequisites).

Persistent disk does not increase RAM. A full float32 3.2-million-by-768 flat index
alone needs about 9.2GiB before process overhead and cannot fit an 8GiB Consumption
replica. Use a tested compact index and measured runtime resources for a full
corpus. With the share enabled, `HF_HOME` defaults to `/var/lib/graphiv/huggingface`
for model downloads; `api_environment` can explicitly override that location.

## Manual corpus build

`index_builder_image_tag` defaults to null. Set it only after publishing a tested
offline image as `graphiv-index-builder:<tag>` to this stack's registry, and enable
`runtime_cache_share`. Terraform creates a manually triggered Container Apps Job
in the existing environment; it does not execute the job. No VM, schedule, or new
runtime service is created.

The job uses 4CPU/8Gi, one replica per execution, no retries, and an 86400-second
timeout. Its default command runs `offline.index_build.run_hf` against the pinned
`GraphIV-2026-10-01` revision, with work under `/var/lib/graphiv/build`, builds an
`ivfsq8` snapshot, then publishes its immutable artifacts and manifest without
changing the active runtime manifest. Confirm the command against the tested
image before starting it; `index_builder_command` can override the arguments.
See the [offline builder](../../offline/index_build/README.md).

For a gated or private HF source, populate a read token in Key Vault using the
file-based workflow above, then set `hf_token_secret_name` to its name. The job
receives `HF_TOKEN` through a managed-identity Key Vault reference; Terraform never
reads its value. Public sources can omit it. The separate builder identity receives
ACR pull, Blob Data Contributor only on the three input-artifact containers, and
Key Vault Secrets User only on the selected HF secret. It receives no reports,
API-token, or model-key grant. The shared filesystem mount uses the environment's
cache identity, not the builder identity.

After reviewing and applying the job configuration, explicitly start one execution:

```sh
az containerapp job start \
  --resource-group "$(terraform output -raw resource_group_name)" \
  --name "$(terraform output -raw index_builder_job_name)"
az containerapp job execution list \
  --resource-group "$(terraform output -raw resource_group_name)" \
  --name "$(terraform output -raw index_builder_job_name)" \
  --output table
```

Start only one build execution at a time; replica parallelism does not prevent an
operator from starting another execution. Check the build's source counts,
artifact checksums, and completion result, then run the actual-corpus quality
benchmark against the built snapshot on the shared cache. The benchmark module
can be streamed into the existing API container; no extra infrastructure or
service is required. Keep the published snapshot inactive until the measured
recall, latency, and memory checks pass. After that review, explicitly rerun the
builder for the same verified snapshot with `--publish --activate`; it reuses the
existing local snapshot and updates the active manifest only on that explicit
request. Default builds never activate an unbenchmarked ANN configuration.
Setting `index_builder_image_tag = null` removes the job and its dedicated grants;
keep `runtime_cache_share = true` to retain the cache. Job behavior is defined by
the [Container Apps Jobs model](https://learn.microsoft.com/en-us/azure/container-apps/jobs).

## Permissions

The API identity receives the following scoped grants from [`identity.tf`](identity.tf):

| Scope | Role | Access |
| --- | --- | --- |
| `vector-indexes` container | Storage Blob Data Reader | Read/list vectors; no write/delete |
| `citation-graphs` and `metadata` containers | Custom blob read/write role | Blob read/list, write, and add; no delete |
| `reports` container | Custom report writer | Blob write/add; no blob read/list/delete |
| `reports`, when `allow_report_reads = true` | Additional Storage Blob Data Reader | Adds report read/list |
| Container Registry | AcrPull | Pull API images |
| Key Vault | Key Vault Secrets User | Read secret values for the app |

Both custom roles also grant container-metadata read through
`Microsoft.Storage/storageAccounts/blobServices/containers/read`. Their exact data
actions are `blobs/read` where specified, `blobs/write`, and `blobs/add/action` under
`Microsoft.Storage/storageAccounts/blobServices/containers/`; neither grants deletion.

The optional `publisher_principal_id` receives **Storage Blob Data Contributor** on
the vectors, graphs, and metadata containers, including delete permission. It receives
no reports grant. This Blob-publishing grant does not include registry push permission.
The deploying identity receives **Key Vault Secrets Officer** on the created vault.

Containers reject anonymous access, account-key authentication is disabled, and Blob
access uses Microsoft Entra roles. The Storage endpoint remains publicly reachable;
this root does not create a private network endpoint.

## Runtime settings

[`container_app.tf`](container_app.tf) supplies these settings to the runtime:

| Environment variable | Meaning |
| --- | --- |
| `GRAPHIV_RUNTIME` | `azure`; activates managed identity and Blob report defaults |
| `GRAPHIV_STORAGE_BACKEND` | `corpus_backend`: Azure snapshots or an existing PostgreSQL corpus |
| `GRAPHIV_POSTGRES_DSN` | Optional PostgreSQL DSN from Key Vault, injected only in PostgreSQL mode |
| `GRAPHIV_API_TOKEN` | Key Vault-backed bearer token shared with the Next.js server |
| `GRAPHIV_EMBED_API_URL`, `GRAPHIV_EMBED_MODEL` | Independent embedding endpoint and snapshot-compatible model |
| `GRAPHIV_EMBED_API_KEY` | Optional independent embedding credential from Key Vault |
| `AZURE_CLIENT_ID` | User-assigned identity client ID; select it through the Azure identity SDK |
| `GRAPHIV_STORAGE_ACCOUNT_URL` | Blob service endpoint |
| `GRAPHIV_VECTOR_CONTAINER` | `vector-indexes` |
| `GRAPHIV_GRAPH_CONTAINER` | `citation-graphs` |
| `GRAPHIV_METADATA_CONTAINER` | `metadata` |
| `GRAPHIV_REPORTS_CONTAINER` | `reports` |
| `GRAPHIV_CACHE_PATH` | `/var/lib/graphiv/cache` |
| `GRAPHIV_LLM_API_URL`, `GRAPHIV_LLM_MODEL` | External LLM configuration |
| `GRAPHIV_LLM_API_KEY` | Key Vault-backed secret, when enabled |
| `GRAPHIV_ALLOWED_HOSTS` | Container App hostname |
| `GRAPHIV_ARXIV_BASE_URL` | `https://arxiv.org` |

The image authenticates to Blob through the
[user-assigned managed identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity),
downloads verified indexes/metadata, authenticates external model calls, and uploads
completed report artifacts to Blob. The mounted `/var/lib/graphiv` volume defaults to
replica-scoped `EmptyDir`; its contents disappear when the replica is replaced.
The optional `runtime_cache_share` makes those cache files persistent through an
identity-authenticated Azure Files mount. Reports remain in Blob in either case; see
[Container Apps storage lifetimes](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts).

Ingress is public HTTPS on port 8000. Every route except `/health/live` and
`/health/ready` requires the API bearer token. Startup, liveness, and traffic probes
check `/health/live` so saved reports remain accessible while research is unready. Minimum and maximum replicas are both
one because MCP rankings and sessions remain process-local. A restart or revision
replacement still loses that state; single-replica settings do not make sessions durable.
External LLM endpoints and arXiv require no resources in this Terraform root.

## Local checks

These checks use mock providers and do not provision Azure resources:

```sh
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
terraform test
```
