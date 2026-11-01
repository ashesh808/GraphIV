# Azure Terraform

This root defines GraphIV's backend infrastructure. The frontend project is managed
separately in [`infra/vercel`](../vercel/README.md). No cloud resources have been applied.

With `api_image_tag = null`, the bootstrap creates a resource group, Storage Account,
four private Blob containers, Azure Container Registry, Key Vault, Log Analytics,
Container Apps environment, user-assigned managed identity, and scoped role assignments.
Supplying an image tag adds one externally reachable HTTPS Container App.

**The current Docker image is not compatible with this storage architecture.**
[`src/mcp/state.py`](../../src/mcp/state.py) still loads a local GraphExport and PostgreSQL
connection. Report storage is local, Blob adapters are unfinished, and
[`apps/api/orchestration.py`](../../apps/api/orchestration.py) is a stub. The current
LLM and embedding clients send no authentication header and do not consume the new
Azure environment variables. Terraform does not migrate this runtime implicitly.

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

Terraform handles secret names and Key Vault URIs, never the LLM credential value.
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

The following is an operator procedure, not a deployment already performed.

1. Copy [`terraform.tfvars.example`](terraform.tfvars.example), set the subscription and
   naming inputs, and keep `api_image_tag = null`. Initialize your chosen state backend,
   review a plan, and apply it when ready. `backend_url` remains null during bootstrap.

   ```sh
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -out=bootstrap.tfplan
   terraform apply bootstrap.tfplan
   ```

2. Build and test an image implementing the [contract below](#compatible-image-contract),
   then publish it to the created registry as `graphiv-api:<tag>`. The image publisher
   needs its own ACR push permission; the API identity receives pull permission only.

   ```sh
   registry_name="$(terraform output -raw registry_name)"
   registry_host="$(terraform output -raw registry_login_server)"
   image_tag="replace-with-tested-tag"
   az acr login --name "$registry_name"
   docker tag your-compatible-image:tested "${registry_host}/graphiv-api:${image_tag}"
   docker push "${registry_host}/graphiv-api:${image_tag}"
   ```

3. Populate the configured LLM secret outside Terraform. Bootstrap grants the deploying
   identity **Key Vault Secrets Officer**. Supply the credential from a file so it does
   not become a shell-history argument:

   ```sh
   az keyvault secret set \
     --vault-name "$(terraform output -raw key_vault_name)" \
     --name llm-api-key \
     --file /path/to/llm-api-key \
     --output none
   ```

   Use the name selected by `llm_api_key_secret_name`. Set that variable to null only
   when the external endpoint needs no API key. The app references a Key Vault URI
   through its managed identity; see
   [Container Apps secret references](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets).

4. Set `api_image_tag`, `llm_api_url`, and `llm_model`, then review and apply a new plan.
   Enable `allow_report_reads = true` if the compatible image serves the library or
   `find_runs`; the default report permission is write-only. Size `api_resources` for
   the downloaded indexes and temporary storage.

5. Once the backend works, read `terraform output -raw backend_url` and put that origin
   into `backend_url` in the [Vercel root](../vercel/README.md). It must be reachable
   from Vercel and expose the web app's read endpoints. The default command uses
   `--role both` to serve MCP and library routes; `api` alone omits the library.

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

## Compatible image contract

[`container_app.tf`](container_app.tf) supplies the following settings for a future
Blob-capable image. The current runtime does not consume this contract.

| Environment variable | Meaning |
| --- | --- |
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

The image must authenticate to Blob through the
[user-assigned managed identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity),
load indexes/metadata, implement authenticated LLM and embedding calls, and upload
report artifacts to Blob. The mounted `/var/lib/graphiv` volume is replica-scoped
`EmptyDir`, suitable for a rebuildable index cache, not persistent reports. Its contents
disappear when the replica is replaced; see
[Container Apps storage lifetimes](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts).

Ingress is public HTTPS on port 8000. The image must protect authenticated/write APIs
before activation; Terraform does not add application authentication. Probes only
check TCP reachability, not dataset readiness. Minimum and maximum replicas are both
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
