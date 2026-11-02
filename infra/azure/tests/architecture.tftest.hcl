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
      id                 = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.OperationalInsights/workspaces/log-graphiv-dev"
      workspace_id       = "99999999-9999-4999-8999-999999999999"
      primary_shared_key = "mock-workspace-key"
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

mock_provider "azapi" {
  override_during = plan
}

override_resource {
  override_during = plan
  target          = azapi_resource.environment
  values = {
    id = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.App/managedEnvironments/cae-graphiv-dev"
    output = {
      properties = {
        defaultDomain     = "graphiv-test.westus2.azurecontainerapps.io"
        provisioningState = "Succeeded"
        environmentMode   = "WorkloadProfiles"
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
  environment                   = "dev"
  allow_report_reads            = false
  publisher_principal_id        = null
  subscription_id               = "11111111-1111-4111-8111-111111111111"
  api_image_tag                 = null
  runtime_cache_share           = false
  index_builder_image_tag       = null
  hf_token_secret_name          = null
  corpus_backend                = "azure"
  postgres_dsn_secret_name      = null
  llm_api_url                   = null
  llm_model                     = null
  llm_api_key_secret_name       = null
  embedding_api_url             = null
  embedding_model               = null
  embedding_api_key_secret_name = null
  api_environment               = {}
}

run "default_cache_and_builder_are_absent" {
  command = plan
  variables { api_image_tag = "runtime-verified" }

  assert {
    condition = (
      length(azurerm_storage_share.runtime_cache) == 0 &&
      length(azapi_update_resource.cache_smb_oauth) == 0 &&
      length(azapi_resource.cache_storage) == 0 &&
      length(azurerm_user_assigned_identity.cache) == 0 &&
      length(azurerm_role_assignment.cache_mount) == 0 &&
      length(azapi_resource.environment.identity) == 0 &&
      one(azurerm_container_app.api[0].template[0].volume).storage_type == "EmptyDir" &&
      one(azurerm_container_app.api[0].template[0].volume).storage_name == null &&
      length(azurerm_container_app_job.index_builder) == 0 &&
      length(azurerm_user_assigned_identity.index_builder) == 0 &&
      length(azurerm_role_assignment.index_builder_publish) == 0 &&
      length(azurerm_role_assignment.index_builder_pull) == 0 &&
      length(azurerm_role_assignment.index_builder_hf_token) == 0 &&
      output.runtime_cache_share_name == null && output.index_builder_job_name == null
    )
    error_message = "Defaults must retain EmptyDir without creating persistent storage, identities, grants, or a builder job."
  }
}

run "persistent_cache_uses_environment_identity_without_account_keys" {
  command = plan
  variables {
    api_image_tag       = "runtime-verified"
    runtime_cache_share = true
  }

  override_resource {
    override_during = plan
    target          = azurerm_user_assigned_identity.cache[0]
    values = {
      id           = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-graphiv-dev-cache"
      principal_id = "66666666-6666-4666-8666-666666666666"
    }
  }

  assert {
    condition = (
      azurerm_storage_share.runtime_cache[0].storage_account_id == azurerm_storage_account.data.id &&
      azurerm_storage_share.runtime_cache[0].quota == 100 &&
      azurerm_storage_share.runtime_cache[0].enabled_protocol == "SMB" &&
      !azurerm_storage_account.data.shared_access_key_enabled &&
      one(azapi_resource.environment.identity).type == "UserAssigned" &&
      one(azapi_resource.environment.identity).identity_ids == tolist([azurerm_user_assigned_identity.cache[0].id]) &&
      azurerm_role_assignment.cache_mount[0].scope == azurerm_storage_account.data.id &&
      azurerm_role_assignment.cache_mount[0].role_definition_name == "Storage File Data SMB MI Admin" &&
      azurerm_role_assignment.cache_mount[0].principal_id == azurerm_user_assigned_identity.cache[0].principal_id &&
      azurerm_role_assignment.cache_mount[0].principal_id != azurerm_user_assigned_identity.api.principal_id
    )
    error_message = "The 100GiB SMB share must use a distinct environment mount identity and preserve disabled shared keys."
  }

  assert {
    condition = (
      azapi_update_resource.cache_smb_oauth[0].body.properties.azureFilesIdentityBasedAuthentication.smbOAuthSettings.isSmbOAuthEnabled &&
      toset(keys(azapi_update_resource.cache_smb_oauth[0].body.properties.azureFilesIdentityBasedAuthentication)) == toset(["smbOAuthSettings"]) &&
      azapi_resource.cache_storage[0].type == "Microsoft.App/managedEnvironments/storages@2026-03-02-preview" &&
      azapi_resource.cache_storage[0].parent_id == azapi_resource.environment.id &&
      azapi_resource.cache_storage[0].body.properties.azureFile.accountName == azurerm_storage_account.data.name &&
      azapi_resource.cache_storage[0].body.properties.azureFile.shareName == azurerm_storage_share.runtime_cache[0].name &&
      azapi_resource.cache_storage[0].body.properties.azureFile.identity == azurerm_user_assigned_identity.cache[0].id &&
      azapi_resource.cache_storage[0].body.properties.azureFile.accessMode == "ReadWrite" &&
      toset(keys(azapi_resource.cache_storage[0].body.properties.azureFile)) == toset(["accountName", "shareName", "identity", "accessMode"])
    )
    error_message = "SMB OAuth must update only its nested property; mount configuration must contain the environment identity and no account keys."
  }

  assert {
    condition = (
      one(azurerm_container_app.api[0].template[0].volume).storage_type == "AzureFile" &&
      one(azurerm_container_app.api[0].template[0].volume).storage_name == azapi_resource.cache_storage[0].name &&
      one(azurerm_container_app.api[0].template[0].container[0].volume_mounts).path == "/var/lib/graphiv" &&
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env.value if env.name == "HF_HOME"]) == "/var/lib/graphiv/huggingface" &&
      output.runtime_cache_share_name == "runtime-cache"
    )
    error_message = "Opting in must attach the persistent share at the existing runtime cache mount."
  }
}

run "manual_builder_has_separate_identity_and_scoped_publish_access" {
  command = plan
  variables {
    runtime_cache_share     = true
    index_builder_image_tag = "builder-verified"
    hf_token_secret_name    = "hf-read-token"
  }

  override_resource {
    override_during = plan
    target          = azurerm_user_assigned_identity.index_builder[0]
    values = {
      id           = "/subscriptions/11111111-1111-4111-8111-111111111111/resourceGroups/rg-graphiv-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-graphiv-dev-index-builder"
      principal_id = "77777777-7777-4777-8777-777777777777"
      client_id    = "88888888-8888-4888-8888-888888888888"
    }
  }

  assert {
    condition = (
      length(azurerm_container_app_job.index_builder) == 1 &&
      azurerm_container_app_job.index_builder[0].replica_timeout_in_seconds == 86400 &&
      azurerm_container_app_job.index_builder[0].replica_retry_limit == 0 &&
      one(azurerm_container_app_job.index_builder[0].manual_trigger_config).parallelism == 1 &&
      one(azurerm_container_app_job.index_builder[0].manual_trigger_config).replica_completion_count == 1 &&
      length(azurerm_container_app_job.index_builder[0].event_trigger_config) == 0 &&
      length(azurerm_container_app_job.index_builder[0].schedule_trigger_config) == 0 &&
      azurerm_container_app_job.index_builder[0].template[0].container[0].cpu == 4 &&
      azurerm_container_app_job.index_builder[0].template[0].container[0].memory == "8Gi" &&
      azurerm_container_app_job.index_builder[0].template[0].container[0].image == "${azurerm_container_registry.images.login_server}/graphiv-index-builder:builder-verified" &&
      azurerm_container_app_job.index_builder[0].template[0].container[0].command == var.index_builder_command &&
      contains(azurerm_container_app_job.index_builder[0].template[0].container[0].command, "--publish") &&
      !contains(azurerm_container_app_job.index_builder[0].template[0].container[0].command, "--activate") &&
      one(azurerm_container_app_job.index_builder[0].template[0].volume).storage_type == "AzureFile" &&
      one(azurerm_container_app_job.index_builder[0].template[0].volume).storage_name == azapi_resource.cache_storage[0].name &&
      one(azurerm_container_app_job.index_builder[0].template[0].container[0].volume_mounts).path == "/var/lib/graphiv"
    )
    error_message = "The optional builder must remain a manual, single-replica, no-retry 4CPU/8Gi job with a 24h limit and the persistent cache mount; default publication must leave the snapshot inactive."
  }

  assert {
    condition = (
      one(azurerm_container_app_job.index_builder[0].identity).identity_ids == toset([azurerm_user_assigned_identity.index_builder[0].id]) &&
      one(azurerm_container_app_job.index_builder[0].registry).identity == azurerm_user_assigned_identity.index_builder[0].id &&
      azurerm_role_assignment.index_builder_pull[0].scope == azurerm_container_registry.images.id &&
      azurerm_role_assignment.index_builder_pull[0].role_definition_name == "AcrPull" &&
      toset(keys(azurerm_role_assignment.index_builder_publish)) == toset(["vectors", "graphs", "metadata"]) &&
      alltrue([for purpose, grant in azurerm_role_assignment.index_builder_publish :
        grant.scope == azurerm_storage_container.data[purpose].id &&
        grant.scope != azurerm_storage_container.data["reports"].id &&
        grant.role_definition_name == "Storage Blob Data Contributor" &&
        grant.principal_id == azurerm_user_assigned_identity.index_builder[0].principal_id &&
        grant.principal_id != azurerm_user_assigned_identity.api.principal_id
      ]) &&
      one([for env in azurerm_container_app_job.index_builder[0].template[0].container[0].env : env.value if env.name == "AZURE_CLIENT_ID"]) == azurerm_user_assigned_identity.index_builder[0].client_id &&
      length([for env in azurerm_container_app_job.index_builder[0].template[0].container[0].env : env if env.name == "GRAPHIV_REPORTS_CONTAINER" || env.name == "GRAPHIV_API_TOKEN" || env.name == "GRAPHIV_LLM_API_KEY"]) == 0
    )
    error_message = "The builder must use its own identity and container-scoped publishing grants, with no reports or runtime credential access."
  }

  assert {
    condition = (
      one(azurerm_container_app_job.index_builder[0].secret).key_vault_secret_id == "${azurerm_key_vault.api.vault_uri}secrets/hf-read-token" &&
      one(azurerm_container_app_job.index_builder[0].secret).identity == azurerm_user_assigned_identity.index_builder[0].id &&
      one(azurerm_container_app_job.index_builder[0].secret).value == null &&
      one([for env in azurerm_container_app_job.index_builder[0].template[0].container[0].env : env if env.name == "HF_TOKEN"]).secret_name == "hf-token" &&
      azurerm_role_assignment.index_builder_hf_token[0].scope == "${azurerm_key_vault.api.id}/secrets/hf-read-token" &&
      azurerm_role_assignment.index_builder_hf_token[0].role_definition_name == "Key Vault Secrets User"
    )
    error_message = "The optional HF token must use only a Key Vault reference and a secret-scoped reader grant."
  }
}

run "public_dataset_builder_can_omit_an_hf_secret" {
  command = plan
  variables {
    runtime_cache_share     = true
    index_builder_image_tag = "builder-verified"
  }
  assert {
    condition = (
      length(azurerm_container_app_job.index_builder[0].secret) == 0 &&
      length(azurerm_role_assignment.index_builder_hf_token) == 0 &&
      length([for env in azurerm_container_app_job.index_builder[0].template[0].container[0].env : env if env.name == "HF_TOKEN"]) == 0
    )
    error_message = "Public-dataset builds must not create unresolved secret references or vault grants."
  }
}

run "activation_requires_an_explicit_reviewed_command_override" {
  command = plan
  variables {
    runtime_cache_share     = true
    index_builder_image_tag = "builder-verified"
    index_builder_command = [
      "python", "-m", "offline.index_build.run_hf",
      "--workdir", "/var/lib/graphiv/build",
      "--revision", "GraphIV-2026-10-01",
      "--snapshot-id", "quality-reviewed-snapshot",
      "--index-kind", "ivfsq8", "--publish", "--activate",
    ]
  }
  assert {
    condition = (
      azurerm_container_app_job.index_builder[0].template[0].container[0].command == var.index_builder_command &&
      contains(azurerm_container_app_job.index_builder[0].template[0].container[0].command, "--activate") &&
      length(azurerm_container_app_job.index_builder[0].schedule_trigger_config) == 0
    )
    error_message = "After an operator reviews actual-corpus quality, explicit activation arguments must reach the existing manual job without creating a scheduled service."
  }
}

run "builder_requires_persistent_cache" {
  command = plan
  variables { index_builder_image_tag = "builder-verified" }
  expect_failures = [azurerm_container_app_job.index_builder]
}

run "builder_hf_secret_must_be_a_name_not_a_url" {
  command = plan
  variables { hf_token_secret_name = "https://vault.example/secrets/token" }
  expect_failures = [var.hf_token_secret_name]
}

run "builder_image_tag_cannot_inject_another_registry" {
  command = plan
  variables { index_builder_image_tag = "other.example/image:latest" }
  expect_failures = [var.index_builder_image_tag]
}

run "default_provisions_private_storage_without_starting_an_image" {
  command = plan

  assert {
    condition = (
      azapi_resource.environment.type == "Microsoft.App/managedEnvironments@2026-07-01" &&
      azapi_resource.environment.body.properties.environmentMode == "WorkloadProfiles" &&
      one(azapi_resource.environment.body.properties.workloadProfiles).name == "Consumption" &&
      one(azapi_resource.environment.body.properties.workloadProfiles).workloadProfileType == "Consumption" &&
      azapi_resource.environment.body.properties.appLogsConfiguration.destination == "log-analytics" &&
      azapi_resource.environment.body.properties.appLogsConfiguration.logAnalyticsConfiguration.customerId == azurerm_log_analytics_workspace.api.workspace_id
    )
    error_message = "The environment must explicitly select WorkloadProfiles mode with Consumption compute and workspace logging; Express cannot resolve Key Vault secrets."
  }

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
    api_image_tag                 = "runtime-verified"
    llm_api_url                   = "https://models.example.test/v1"
    llm_model                     = "review-model"
    llm_api_key_secret_name       = "llm-api-key"
    embedding_api_url             = "https://embeddings.example.test/v1"
    embedding_model               = "matching-embedding-model"
    embedding_api_key_secret_name = "embedding-api-key"
    api_resources                 = { cpu = 2, memory = "4Gi" }
    api_environment               = { GRAPHIV_LOG_LEVEL = "info" }
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
      one([for secret in azurerm_container_app.api[0].secret : secret if secret.name == "llm-api-key"]).key_vault_secret_id == "${azurerm_key_vault.api.vault_uri}secrets/llm-api-key" &&
      one([for secret in azurerm_container_app.api[0].secret : secret if secret.name == "llm-api-key"]).identity == azurerm_user_assigned_identity.api.id &&
      one([for secret in azurerm_container_app.api[0].secret : secret if secret.name == "llm-api-key"]).value == null &&
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
      GRAPHIV_ALLOWED_HOSTS       = "ca-graphiv-dev-api.${azapi_resource.environment.output.properties.defaultDomain}"
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
      length(azurerm_container_app.api[0].secret) == 1 &&
      one(azurerm_container_app.api[0].secret).name == "api-token" &&
      length([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_LLM_API_KEY"]) == 0 &&
      output.llm_api_key_secret_uri == null
    )
    error_message = "A keyless external endpoint must not leave an unresolved Key Vault secret reference in the app."
  }
}

run "saved_reports_start_before_research_configuration" {
  command = plan
  variables { api_image_tag = "runtime-verified" }
  assert {
    condition = length(azurerm_container_app.api) == 1 && length([
      for env in azurerm_container_app.api[0].template[0].container[0].env : env
      if env.name == "GRAPHIV_LLM_API_URL" || env.name == "GRAPHIV_EMBED_API_URL"
    ]) == 0
    error_message = "Absent research services must not turn into fabricated endpoints."
  }
  assert {
    condition     = one(azurerm_container_app.api[0].secret).name == "api-token" && one(azurerm_container_app.api[0].secret).value == null
    error_message = "The API token must use a Key Vault reference, never a plaintext value."
  }
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

run "azure_corpus_does_not_inject_an_unused_postgres_secret" {
  command = plan
  variables {
    api_image_tag            = "runtime-verified"
    postgres_dsn_secret_name = "unused-postgres-dsn"
  }
  assert {
    condition = (
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env.value if env.name == "GRAPHIV_STORAGE_BACKEND"]) == "azure" &&
      length([for secret in azurerm_container_app.api[0].secret : secret if secret.name == "postgres-dsn"]) == 0 &&
      length([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_POSTGRES_DSN"]) == 0 &&
      length([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_REPORT_STORAGE_BACKEND"]) == 0
    )
    error_message = "The Azure default must not add PostgreSQL credentials or change the existing implicit Blob report-storage setting."
  }
}

run "postgres_corpus_uses_a_managed_identity_secret_reference" {
  command = plan
  variables {
    api_image_tag            = "runtime-verified"
    corpus_backend           = "postgres"
    postgres_dsn_secret_name = "graphiv-postgres-dsn"
    api_environment          = { GRAPHIV_GRAPH_PATH = "/mnt/graphiv/citation_graph_export.npy" }
  }
  assert {
    condition = (
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env.value if env.name == "GRAPHIV_STORAGE_BACKEND"]) == "postgres" &&
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env.value if env.name == "GRAPHIV_RUNTIME"]) == "azure" &&
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env.value if env.name == "GRAPHIV_GRAPH_PATH"]) == "/mnt/graphiv/citation_graph_export.npy" &&
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_POSTGRES_DSN"]).secret_name == "postgres-dsn" &&
      one([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_POSTGRES_DSN"]).value == null &&
      one([for secret in azurerm_container_app.api[0].secret : secret if secret.name == "postgres-dsn"]).key_vault_secret_id == "${azurerm_key_vault.api.vault_uri}secrets/graphiv-postgres-dsn" &&
      one([for secret in azurerm_container_app.api[0].secret : secret if secret.name == "postgres-dsn"]).identity == azurerm_user_assigned_identity.api.id &&
      one([for secret in azurerm_container_app.api[0].secret : secret if secret.name == "postgres-dsn"]).value == null &&
      length([for env in azurerm_container_app.api[0].template[0].container[0].env : env if env.name == "GRAPHIV_REPORT_STORAGE_BACKEND"]) == 0
    )
    error_message = "PostgreSQL mode must use the existing external graph path and a Key Vault DSN reference, retaining Azure report-storage defaults."
  }
}

run "postgres_bootstrap_can_omit_the_dsn_before_api_activation" {
  command = plan
  variables {
    corpus_backend = "postgres"
  }
  assert {
    condition     = length(azurerm_container_app.api) == 0
    error_message = "Infrastructure-only bootstrap must remain possible before PostgreSQL credentials exist."
  }
}

run "postgres_api_activation_requires_a_dsn_secret_name" {
  command = plan
  variables {
    corpus_backend = "postgres"
    api_image_tag  = "runtime-verified"
  }
  expect_failures = [azurerm_container_app.api]
}

run "plaintext_postgres_dsn_override_is_rejected" {
  command = plan
  variables { api_environment = { GRAPHIV_POSTGRES_DSN = "must-not-enter-terraform" } }
  expect_failures = [var.api_environment]
}

run "report_backend_override_is_rejected" {
  command = plan
  variables { api_environment = { GRAPHIV_REPORT_STORAGE_BACKEND = "local" } }
  expect_failures = [var.api_environment]
}

run "unsupported_corpus_backend_is_rejected" {
  command = plan
  variables { corpus_backend = "sqlite" }
  expect_failures = [var.corpus_backend]
}

run "postgres_secret_name_cannot_be_a_uri" {
  command = plan
  variables { postgres_dsn_secret_name = "https://vault.example/secrets/pg" }
  expect_failures = [var.postgres_dsn_secret_name]
}
