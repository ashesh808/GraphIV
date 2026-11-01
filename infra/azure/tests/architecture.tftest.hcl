# These tests plan the real module with entirely mocked providers: no Azure
# credentials, network calls to Azure, state writes, or apply operations.
mock_provider "azurerm" {
  override_during = plan

  mock_data "azurerm_client_config" {
    defaults = {
      subscription_id = "11111111-1111-4111-8111-111111111111"
      tenant_id       = "22222222-2222-4222-8222-222222222222"
      object_id       = "33333333-3333-4333-8333-333333333333"
      client_id       = "55555555-5555-4555-8555-555555555555"
    }
  }

  mock_resource "azurerm_resource_group" {
    defaults = {
      id = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev"
    }
  }

  mock_resource "azurerm_storage_account" {
    defaults = {
      id                    = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.Storage/storageAccounts/graphivdevabc123"
      primary_blob_endpoint = "https://graphivdevabc123.blob.core.windows.net/"
    }
  }

  mock_resource "azurerm_container_registry" {
    defaults = {
      id           = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.ContainerRegistry/registries/graphivdevacrabc123"
      login_server = "graphivdevacrabc123.azurecr.io"
    }
  }

  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-graphiv-dev-api"
      client_id    = "55555555-5555-4555-8555-555555555555"
      principal_id = "44444444-4444-4444-8444-444444444444"
      tenant_id    = "22222222-2222-4222-8222-222222222222"
    }
  }

  mock_resource "azurerm_key_vault" {
    defaults = {
      id        = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.KeyVault/vaults/graphiv-dev-kv-abc123"
      vault_uri = "https://graphiv-dev-kv-abc123.vault.azure.net/"
    }
  }

  mock_resource "azurerm_log_analytics_workspace" {
    defaults = {
      id = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.OperationalInsights/workspaces/log-graphiv-dev"
    }
  }

  mock_resource "azurerm_container_app_environment" {
    defaults = {
      id             = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.App/managedEnvironments/cae-graphiv-dev"
      default_domain = "graphiv-test.westus2.azurecontainerapps.io"
    }
  }

  mock_resource "azurerm_container_app" {
    defaults = {
      id = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.App/containerApps/ca-graphiv-dev-api"
      ingress = {
        fqdn = "ca-graphiv-dev-api.graphiv-test.westus2.azurecontainerapps.io"
      }
    }
  }
}

mock_provider "random" {
  override_during = plan

  mock_resource "random_string" {
    defaults = { result = "abc123" }
  }
}

# Distinct container IDs make permission-scope regressions visible. Reusing one
# fake ID for every instance could falsely pass an account-wide grant test.
override_resource {
  override_during = plan
  target          = azurerm_storage_container.data["vectors"]
  values = {
    id = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.Storage/storageAccounts/graphivdevabc123/blobServices/default/containers/vector-indexes"
  }
}

override_resource {
  override_during = plan
  target          = azurerm_storage_container.data["graphs"]
  values = {
    id = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.Storage/storageAccounts/graphivdevabc123/blobServices/default/containers/citation-graphs"
  }
}

override_resource {
  override_during = plan
  target          = azurerm_storage_container.data["metadata"]
  values = {
    id = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.Storage/storageAccounts/graphivdevabc123/blobServices/default/containers/metadata"
  }
}

override_resource {
  override_during = plan
  target          = azurerm_storage_container.data["reports"]
  values = {
    id = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.Storage/storageAccounts/graphivdevabc123/blobServices/default/containers/reports"
  }
}

override_resource {
  override_during = plan
  target          = azurerm_role_definition.blob_read_write
  values = {
    id                          = "/subscriptions/11111111-1111-4111-8111-111111111111/providers/Microsoft.Authorization/roleDefinitions/66666666-6666-4666-8666-666666666666"
    role_definition_id          = "66666666-6666-4666-8666-666666666666"
    role_definition_resource_id = "/subscriptions/11111111-1111-4111-8111-111111111111/providers/Microsoft.Authorization/roleDefinitions/66666666-6666-4666-8666-666666666666"
  }
}

override_resource {
  override_during = plan
  target          = azurerm_role_definition.report_writer
  values = {
    id                          = "/subscriptions/11111111-1111-4111-8111-111111111111/providers/Microsoft.Authorization/roleDefinitions/77777777-7777-4777-8777-777777777777"
    role_definition_id          = "77777777-7777-4777-8777-777777777777"
    role_definition_resource_id = "/subscriptions/11111111-1111-4111-8111-111111111111/providers/Microsoft.Authorization/roleDefinitions/77777777-7777-4777-8777-777777777777"
  }
}

variables {
  subscription_id = "11111111-1111-4111-8111-111111111111"
}

run "default_provisions_private_storage_without_starting_an_image" {
  command = plan

  assert {
    condition     = length(azurerm_container_app.api) == 0 && output.backend_url == null && output.mcp_url == null
    error_message = "Infrastructure bootstrap must not start a placeholder image or advertise a nonexistent API."
  }

  assert {
    condition = toset([for container in azurerm_storage_container.data : container.name]) == toset([
      "vector-indexes", "citation-graphs", "metadata", "reports"
    ]) && alltrue([for container in azurerm_storage_container.data : container.container_access_type == "private"])
    error_message = "The four architecture data containers must exist and remain private."
  }

  assert {
    condition = (
      !azurerm_storage_account.data.shared_access_key_enabled &&
      azurerm_storage_account.data.default_to_oauth_authentication &&
      azurerm_storage_account.data.https_traffic_only_enabled &&
      azurerm_storage_account.data.min_tls_version == "TLS1_2" &&
      !azurerm_storage_account.data.allow_nested_items_to_be_public
    )
    error_message = "Storage must use Entra authentication, HTTPS/TLS1.2, and reject public blob access."
  }

  assert {
    condition = (
      azurerm_role_assignment.vector_reader.scope == azurerm_storage_container.data["vectors"].id &&
      azurerm_role_assignment.vector_reader.role_definition_name == "Storage Blob Data Reader" &&
      azurerm_role_assignment.vector_reader.principal_id == azurerm_user_assigned_identity.api.principal_id &&
      azurerm_role_assignment.vector_reader.scope != azurerm_storage_account.data.id
    )
    error_message = "The API may read vector artifacts only at their container scope."
  }

  assert {
    condition = (
      toset([for grant in azurerm_role_assignment.graph_metadata : grant.scope]) == toset([
        azurerm_storage_container.data["graphs"].id,
        azurerm_storage_container.data["metadata"].id,
      ]) &&
      alltrue([for grant in azurerm_role_assignment.graph_metadata :
        grant.role_definition_id == azurerm_role_definition.blob_read_write.role_definition_resource_id &&
        grant.principal_id == azurerm_user_assigned_identity.api.principal_id
      ]) &&
      toset(one(azurerm_role_definition.blob_read_write.permissions).data_actions) == toset([
        "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read",
        "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write",
        "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/add/action",
      ]) &&
      toset(one(azurerm_role_definition.blob_read_write.permissions).actions) == toset([
        "Microsoft.Storage/storageAccounts/blobServices/containers/read",
      ])
    )
    error_message = "Graph/metadata access must allow read/write only on their two containers, with no delete or wildcard grants."
  }

  assert {
    condition = (
      azurerm_role_assignment.report_writer.scope == azurerm_storage_container.data["reports"].id &&
      azurerm_role_assignment.report_writer.role_definition_id == azurerm_role_definition.report_writer.role_definition_resource_id &&
      azurerm_role_assignment.report_writer.principal_id == azurerm_user_assigned_identity.api.principal_id &&
      toset(one(azurerm_role_definition.report_writer.permissions).data_actions) == toset([
        "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write",
        "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/add/action",
      ]) &&
      toset(one(azurerm_role_definition.report_writer.permissions).actions) == toset([
        "Microsoft.Storage/storageAccounts/blobServices/containers/read",
      ]) &&
      length(azurerm_role_assignment.report_reader) == 0 &&
      length(azurerm_role_assignment.artifact_publisher) == 0
    )
    error_message = "Default report access must remain write-only, without read/list/delete or publisher grants."
  }
}

run "report_reads_require_an_explicit_separate_grant" {
  command = plan
  variables { allow_report_reads = true }

  assert {
    condition = (
      length(azurerm_role_assignment.report_reader) == 1 &&
      azurerm_role_assignment.report_reader[0].scope == azurerm_storage_container.data["reports"].id &&
      azurerm_role_assignment.report_reader[0].role_definition_name == "Storage Blob Data Reader" &&
      azurerm_role_assignment.report_reader[0].principal_id == azurerm_user_assigned_identity.api.principal_id &&
      !contains(one(azurerm_role_definition.report_writer.permissions).data_actions, "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read")
    )
    error_message = "Report-read opt-in must add a reader only on reports, without broadening the writer role."
  }
}

run "offline_publisher_cannot_access_reports" {
  command = plan
  variables { publisher_principal_id = "88888888-8888-4888-8888-888888888888" }

  assert {
    condition = (
      toset(keys(azurerm_role_assignment.artifact_publisher)) == toset(["vectors", "graphs", "metadata"]) &&
      alltrue([for purpose, grant in azurerm_role_assignment.artifact_publisher :
        grant.scope == azurerm_storage_container.data[purpose].id &&
        grant.scope != azurerm_storage_container.data["reports"].id &&
        grant.principal_id == var.publisher_principal_id &&
        grant.role_definition_name == "Storage Blob Data Contributor"
      ])
    )
    error_message = "An opted-in publisher may update only the three input-artifact containers, not reports."
  }
}

run "compatible_image_activates_a_single_replica_api_with_secret_references" {
  command = plan
  variables {
    api_image_tag   = "runtime-verified"
    llm_api_url     = "https://models.example.test/v1"
    llm_model       = "review-model"
    api_resources   = { cpu = 2, memory = "4Gi" }
    api_environment = { GRAPHIV_LOG_LEVEL = "info" }
  }

  assert {
    condition = (
      length(azurerm_container_app.api) == 1 &&
      azurerm_container_app.api[0].revision_mode == "Single" &&
      azurerm_container_app.api[0].template[0].min_replicas == 1 &&
      azurerm_container_app.api[0].template[0].max_replicas == 1
    )
    error_message = "Process-local MCP session state requires exactly one replica and a single active revision."
  }

  assert {
    condition = (
      azurerm_container_app.api[0].ingress[0].external_enabled &&
      !azurerm_container_app.api[0].ingress[0].allow_insecure_connections &&
      azurerm_container_app.api[0].ingress[0].target_port == 8000 &&
      azurerm_container_app.api[0].ingress[0].traffic_weight[0].latest_revision &&
      azurerm_container_app.api[0].ingress[0].traffic_weight[0].percentage == 100 &&
      azurerm_container_app.api[0].template[0].container[0].command == tolist([
        "graphiv-serve", "--http", "--role", "both", "--host", "0.0.0.0", "--port", "8000"
      ])
    )
    error_message = "HTTPS ingress must reach port8000 and serve both MCP and the report library."
  }

  assert {
    condition = (
      azurerm_container_app.api[0].template[0].container[0].image == "${azurerm_container_registry.images.login_server}/graphiv-api:runtime-verified" &&
      azurerm_container_app.api[0].template[0].container[0].cpu == 2 &&
      azurerm_container_app.api[0].template[0].container[0].memory == "4Gi" &&
      azurerm_container_app.api[0].identity[0].type == "UserAssigned" &&
      azurerm_container_app.api[0].identity[0].identity_ids == toset([azurerm_user_assigned_identity.api.id]) &&
      azurerm_container_app.api[0].registry[0].identity == azurerm_user_assigned_identity.api.id &&
      azurerm_role_assignment.image_pull.scope == azurerm_container_registry.images.id &&
      azurerm_role_assignment.image_pull.principal_id == azurerm_user_assigned_identity.api.principal_id &&
      azurerm_role_assignment.image_pull.role_definition_name == "AcrPull" &&
      azurerm_container_registry.images.role_assignment_mode == "LegacyRegistryPermissions" &&
      !azurerm_container_registry.images.admin_enabled
    )
    error_message = "The opted-in image/resources and identity-based ACR pull must reach the actual app definition."
  }

  assert {
    condition = (
      one(azurerm_container_app.api[0].secret).key_vault_secret_id == "${azurerm_key_vault.api.vault_uri}secrets/llm-api-key" &&
      one(azurerm_container_app.api[0].secret).identity == azurerm_user_assigned_identity.api.id &&
      one(azurerm_container_app.api[0].secret).value == null &&
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_LLM_API_KEY"]).secret_name == "llm-api-key" &&
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_LLM_API_KEY"]).value == null &&
      azurerm_role_assignment.secret_reader.scope == azurerm_key_vault.api.id &&
      azurerm_role_assignment.secret_reader.role_definition_name == "Key Vault Secrets User" &&
      azurerm_role_assignment.secret_reader.principal_id == azurerm_user_assigned_identity.api.principal_id
    )
    error_message = "LLM credentials must use a managed-identity Key Vault reference, never a plaintext Terraform value."
  }

  assert {
    condition = alltrue([for name, value in {
      AZURE_CLIENT_ID             = azurerm_user_assigned_identity.api.client_id
      GRAPHIV_STORAGE_ACCOUNT_URL = azurerm_storage_account.data.primary_blob_endpoint
      GRAPHIV_VECTOR_CONTAINER    = azurerm_storage_container.data["vectors"].name
      GRAPHIV_GRAPH_CONTAINER     = azurerm_storage_container.data["graphs"].name
      GRAPHIV_METADATA_CONTAINER  = azurerm_storage_container.data["metadata"].name
      GRAPHIV_REPORTS_CONTAINER   = azurerm_storage_container.data["reports"].name
      GRAPHIV_LLM_API_URL         = "https://models.example.test/v1"
      GRAPHIV_LLM_MODEL           = "review-model"
      GRAPHIV_LOG_LEVEL           = "info"
      GRAPHIV_ARXIV_BASE_URL      = "https://arxiv.org"
      GRAPHIV_ALLOWED_HOSTS       = "ca-graphiv-dev-api.${azurerm_container_app_environment.api.default_domain}"
      } : try(one([for env in azurerm_container_app.api[0].template[0].container[0].env : env.value if env.name == name]) == value, false)
    ])
    error_message = "The app must receive its concrete identity, artifact locations, LLM endpoint, allowed host and extra non-secret environment."
  }

  assert {
    condition = (
      output.backend_url == "https://ca-graphiv-dev-api.graphiv-test.westus2.azurecontainerapps.io" &&
      output.mcp_url == "${output.backend_url}/mcp"
    )
    error_message = "Frontend outputs must identify the activated app's HTTPS origin and MCP endpoint."
  }
}

run "keyless_llm_endpoint_omits_the_secret_reference" {
  command = plan
  variables {
    api_image_tag           = "runtime-verified"
    llm_api_url             = "https://models.example.test/v1"
    llm_model               = "review-model"
    llm_api_key_secret_name = null
  }

  assert {
    condition = (
      length(azurerm_container_app.api[0].secret) == 0 &&
      length([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_LLM_API_KEY"]) == 0 &&
      output.llm_api_key_secret_uri == null
    )
    error_message = "A keyless external endpoint must not leave an unresolved Key Vault secret reference in the app."
  }
}

run "activation_without_llm_configuration_is_rejected" {
  command = plan
  variables { api_image_tag = "runtime-verified" }
  expect_failures = [azurerm_container_app.api]
}

run "invalid_consumption_resource_pair_is_rejected" {
  command = plan
  variables { api_resources = { cpu = 1, memory = "4Gi" } }
  expect_failures = [var.api_resources]
}

run "reserved_credential_environment_override_is_rejected" {
  command = plan
  variables { api_environment = { GRAPHIV_LLM_API_KEY = "must-not-enter-terraform" } }
  expect_failures = [var.api_environment]
}

run "credential_bearing_llm_url_is_rejected" {
  command = plan
  variables { llm_api_url = "https://user:password@models.example.test/v1" }
  expect_failures = [var.llm_api_url]
}

run "invalid_subscription_uuid_is_rejected" {
  command = plan
  variables { subscription_id = "------------------------------------" }
  expect_failures = [var.subscription_id]
}
