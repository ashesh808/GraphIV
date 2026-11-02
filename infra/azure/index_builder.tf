locals {
  index_builder_enabled = var.index_builder_image_tag != null
  index_builder_environment = local.index_builder_enabled ? {
    AZURE_CLIENT_ID             = azurerm_user_assigned_identity.index_builder[0].client_id
    PYTHONUNBUFFERED            = "1"
    GRAPHIV_STORAGE_ACCOUNT_URL = azurerm_storage_account.data.primary_blob_endpoint
    GRAPHIV_VECTOR_CONTAINER    = local.containers.vectors
    GRAPHIV_GRAPH_CONTAINER     = local.containers.graphs
    GRAPHIV_METADATA_CONTAINER  = local.containers.metadata
    HF_HOME                     = "/var/lib/graphiv/huggingface"
  } : {}
}

resource "azurerm_user_assigned_identity" "index_builder" {
  count = local.index_builder_enabled ? 1 : 0

  name                = "id-${local.base_name}-index-builder"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}

resource "azurerm_role_assignment" "index_builder_publish" {
  for_each = local.index_builder_enabled ? toset(["vectors", "graphs", "metadata"]) : toset([])

  scope                            = azurerm_storage_container.data[each.value].id
  role_definition_name             = "Storage Blob Data Contributor"
  principal_id                     = azurerm_user_assigned_identity.index_builder[0].principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "index_builder_pull" {
  count = local.index_builder_enabled ? 1 : 0

  scope                            = azurerm_container_registry.images.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_user_assigned_identity.index_builder[0].principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "index_builder_hf_token" {
  count = local.index_builder_enabled && var.hf_token_secret_name != null ? 1 : 0

  scope                            = "${azurerm_key_vault.api.id}/secrets/${var.hf_token_secret_name}"
  role_definition_name             = "Key Vault Secrets User"
  principal_id                     = azurerm_user_assigned_identity.index_builder[0].principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_container_app_job" "index_builder" {
  count = local.index_builder_enabled ? 1 : 0

  lifecycle {
    precondition {
      condition     = var.runtime_cache_share
      error_message = "The offline builder requires runtime_cache_share = true; its full corpus cannot fit the Consumption ephemeral disk."
    }
  }

  name                         = "job-${local.base_name}-index-builder"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  container_app_environment_id = azapi_resource.environment.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = 86400
  replica_retry_limit          = 0
  tags                         = local.tags

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.index_builder[0].id]
  }

  registry {
    server   = azurerm_container_registry.images.login_server
    identity = azurerm_user_assigned_identity.index_builder[0].id
  }

  dynamic "secret" {
    for_each = var.hf_token_secret_name == null ? [] : [var.hf_token_secret_name]
    content {
      name                = "hf-token"
      identity            = azurerm_user_assigned_identity.index_builder[0].id
      key_vault_secret_id = "${azurerm_key_vault.api.vault_uri}secrets/${secret.value}"
    }
  }

  template {
    container {
      name    = "index-builder"
      image   = "${azurerm_container_registry.images.login_server}/graphiv-index-builder:${var.index_builder_image_tag}"
      cpu     = 4
      memory  = "8Gi"
      command = var.index_builder_command

      dynamic "env" {
        for_each = local.index_builder_environment
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.hf_token_secret_name == null ? [] : [true]
        content {
          name        = "HF_TOKEN"
          secret_name = "hf-token"
        }
      }

      volume_mounts {
        name = "cache"
        path = "/var/lib/graphiv"
      }
    }

    volume {
      name         = "cache"
      storage_type = "AzureFile"
      storage_name = var.runtime_cache_share ? azapi_resource.cache_storage[0].name : "runtime-cache"
    }
  }

  depends_on = [
    azapi_resource.cache_storage,
    azurerm_role_assignment.index_builder_publish,
    azurerm_role_assignment.index_builder_pull,
    azurerm_role_assignment.index_builder_hf_token,
  ]
}
