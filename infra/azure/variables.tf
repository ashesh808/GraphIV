variable "subscription_id" {
  description = "Azure subscription to provision. Authenticate through Azure CLI or ARM_* environment variables."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "subscription_id must be an Azure subscription UUID."
  }
}

variable "project_name" {
  description = "Lowercase resource prefix, 3–10 characters."
  type        = string
  default     = "graphiv"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,8}[a-z0-9]$", var.project_name)) && !strcontains(var.project_name, "--")
    error_message = "Use 3–10 lowercase letters, numbers or single hyphens; start with a letter and end with a letter or number."
  }
}

variable "environment" {
  description = "Environment name, such as dev or prod. Use separate Terraform state per environment."
  type        = string
  default     = "dev"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,5}$", var.environment))
    error_message = "environment must have 2–6 lowercase letters or numbers, starting with a letter."
  }
}

variable "location" {
  description = "Azure region supporting Container Apps."
  type        = string
  default     = "westus2"
  nullable    = false
}

variable "tags" {
  description = "Additional Azure resource tags."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "storage_replication_type" {
  description = "Blob storage redundancy; choose a value supported in location."
  type        = string
  default     = "LRS"
  nullable    = false

  validation {
    condition     = contains(["LRS", "ZRS", "GRS", "RAGRS", "GZRS", "RAGZRS"], var.storage_replication_type)
    error_message = "Choose a supported Azure Storage replication type."
  }
}

variable "allow_report_reads" {
  description = "Grant the API additional read/list access to reports. False preserves the requested write-only access; the report library requires this capability once Blob adapters exist."
  type        = bool
  default     = false
  nullable    = false
}

variable "corpus_backend" {
  description = "Research corpus backend: immutable Azure snapshots or an existing external PostgreSQL database. Reports remain in Blob storage in both modes."
  type        = string
  default     = "azure"
  nullable    = false

  validation {
    condition     = contains(["azure", "postgres"], var.corpus_backend)
    error_message = "corpus_backend must be azure or postgres."
  }
}

variable "postgres_dsn_secret_name" {
  description = "Optional Key Vault secret name containing the external PostgreSQL DSN. Required when activating a postgres corpus; populate its value outside Terraform."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.postgres_dsn_secret_name == null ? true : can(regex("^[A-Za-z0-9-]{1,127}$", var.postgres_dsn_secret_name))
    error_message = "postgres_dsn_secret_name must be null or a valid Key Vault secret name."
  }
}

variable "publisher_principal_id" {
  description = "Optional Entra object ID of an offline publishing pipeline; grants Blob Data Contributor on vectors, graphs and metadata, excluding reports."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.publisher_principal_id == null ? true : can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.publisher_principal_id))
    error_message = "publisher_principal_id must be null or an Entra object UUID."
  }
}

variable "api_image_tag" {
  description = "Published graphiv-api image tag in this stack's ACR. Null provisions infrastructure only. Supply a tested Blob-capable image to activate the API."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.api_image_tag == null ? true : can(regex("^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$", var.api_image_tag))
    error_message = "api_image_tag must be null or a valid container image tag."
  }
}

variable "api_resources" {
  description = "Consumption CPU/memory pair. One CPU and 2Gi is the default; size for the downloaded vector index."
  type = object({
    cpu    = number
    memory = string
  })
  default  = { cpu = 1, memory = "2Gi" }
  nullable = false

  validation {
    condition     = var.api_resources.cpu >= 0.25 && var.api_resources.cpu <= 4 && floor(var.api_resources.cpu * 4) == var.api_resources.cpu * 4 && var.api_resources.memory == format("%gGi", var.api_resources.cpu * 2)
    error_message = "Consumption resources require CPU in 0.25 steps from 0.25 to 4, and memory equal to twice CPU in Gi (for example 1 / 2Gi)."
  }
}

variable "runtime_cache_share" {
  description = "Mount a 100GiB managed-identity Azure Files share at /var/lib/graphiv for corpus/model caches and offline builds. False preserves EmptyDir and creates no share or cache identity."
  type        = bool
  default     = false
  nullable    = false
}

variable "index_builder_image_tag" {
  description = "Optional published graphiv-index-builder image tag in this stack's ACR. Creates a manual job only; Terraform never starts a build. Requires runtime_cache_share."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.index_builder_image_tag == null ? true : can(regex("^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$", var.index_builder_image_tag))
    error_message = "index_builder_image_tag must be null or a valid container image tag."
  }
}

variable "index_builder_command" {
  description = "Command for the manually triggered offline image. Defaults to publishing an inactive snapshot; add --activate only after actual-corpus quality checks pass. Pin the HF revision and snapshot ID; no credentials belong in arguments."
  type        = list(string)
  default = [
    "python", "-m", "offline.index_build.run_hf",
    "--workdir", "/var/lib/graphiv/build",
    "--revision", "GraphIV-2026-10-01",
    "--snapshot-id", "graphiv-2026-10-01-nomic-sq8",
    "--index-kind", "ivfsq8", "--publish",
  ]
  nullable = false

  validation {
    condition     = length(var.index_builder_command) > 0 && alltrue([for value in var.index_builder_command : length(value) > 0])
    error_message = "index_builder_command must contain a nonempty executable and nonempty arguments."
  }
}

variable "hf_token_secret_name" {
  description = "Optional Key Vault secret name containing an HF read token for the builder job. Populate outside Terraform; only a managed-identity secret reference is stored."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.hf_token_secret_name == null ? true : can(regex("^[A-Za-z0-9-]{1,127}$", var.hf_token_secret_name))
    error_message = "hf_token_secret_name must be null or a valid Key Vault secret name."
  }
}

variable "api_command" {
  description = "Command for a compatible API image. Both mounts MCP and the HTTP library consumed by Next.js. Set null to use the image's own entrypoint/CMD."
  type        = list(string)
  default     = ["graphiv-serve", "--http", "--role", "both", "--host", "0.0.0.0", "--port", "8000"]
  nullable    = true
}

variable "api_environment" {
  description = "Additional non-secret environment variables for the compatible image. Reserved infrastructure and credential names cannot be overridden."
  type        = map(string)
  default     = {}
  nullable    = false

  validation {
    condition = alltrue([
      for name in keys(var.api_environment) :
      can(regex("^[A-Z_][A-Z0-9_]*$", name)) &&
      !contains(["AZURE_CLIENT_ID", "PYTHONUNBUFFERED", "GRAPHIV_STORAGE_ACCOUNT_URL", "GRAPHIV_VECTOR_CONTAINER", "GRAPHIV_GRAPH_CONTAINER", "GRAPHIV_METADATA_CONTAINER", "GRAPHIV_REPORTS_CONTAINER", "GRAPHIV_REPORT_STORAGE_BACKEND", "GRAPHIV_CACHE_PATH", "GRAPHIV_LLM_API_URL", "GRAPHIV_LLM_MODEL", "GRAPHIV_LLM_API_KEY", "GRAPHIV_EMBED_API_URL", "GRAPHIV_EMBED_MODEL", "GRAPHIV_EMBED_API_KEY", "GRAPHIV_RUNTIME", "GRAPHIV_STORAGE_BACKEND", "GRAPHIV_POSTGRES_DSN", "GRAPHIV_API_TOKEN", "GRAPHIV_REQUIRE_AUTH", "GRAPHIV_ALLOWED_HOSTS", "GRAPHIV_ARXIV_BASE_URL"], name)
    ])
    error_message = "Environment variable names must be uppercase identifiers and must not replace reserved infrastructure/credential settings."
  }
}

variable "llm_api_url" {
  description = "External LLM API base URL. Omit to serve saved reports while research remains unready."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.llm_api_url == null ? true : can(regex("^https://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]{1,5})?(/[^?#[:space:]]*)?$", var.llm_api_url))
    error_message = "llm_api_url must be null or an HTTPS base URL without user credentials, query parameters or a fragment."
  }
}

variable "llm_model" {
  description = "Model identifier understood by the external LLM API. Needed for research readiness."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.llm_model == null ? true : length(trimspace(var.llm_model)) > 0
    error_message = "llm_model must be null or a nonempty model identifier."
  }
}

variable "llm_api_key_secret_name" {
  description = "Name of a secret populated out-of-band in the created Key Vault. Null omits API-key injection for endpoints that do not need it. Terraform never reads the secret value."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.llm_api_key_secret_name == null ? true : can(regex("^[A-Za-z0-9-]{1,127}$", var.llm_api_key_secret_name))
    error_message = "Use null or a valid Key Vault secret name."
  }
}

variable "api_token_secret_name" {
  description = "Key Vault secret containing the API bearer token. Populate outside Terraform before activating the API."
  type        = string
  default     = "graphiv-api-token"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9-]{1,127}$", var.api_token_secret_name))
    error_message = "Use a valid Key Vault secret name."
  }
}

variable "embedding_api_url" {
  description = "Independent OpenAI-compatible embedding API URL; the model must match the published snapshot."
  type        = string
  default     = null

  validation {
    condition     = var.embedding_api_url == null ? true : can(regex("^https://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]{1,5})?(/[^?#[:space:]]*)?$", var.embedding_api_url))
    error_message = "embedding_api_url must be null or an HTTPS base URL without credentials, query or fragment."
  }
}

variable "embedding_model" {
  description = "Embedding model identifier; must match the artifact manifest."
  type        = string
  default     = null

  validation {
    condition     = var.embedding_model == null ? true : length(trimspace(var.embedding_model)) > 0
    error_message = "embedding_model must be null or a nonempty identifier."
  }
}

variable "embedding_api_key_secret_name" {
  description = "Optional independent embedding credential in Key Vault. Never implicitly reuses the LLM credential."
  type        = string
  default     = null

  validation {
    condition     = var.embedding_api_key_secret_name == null ? true : can(regex("^[A-Za-z0-9-]{1,127}$", var.embedding_api_key_secret_name))
    error_message = "Use null or a valid Key Vault secret name."
  }
}
