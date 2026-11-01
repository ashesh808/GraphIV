locals {
  api_enabled = var.api_image_tag != null

  # Contract for the Blob-capable image; the current Postgres/local-file runtime does not consume these yet.
  api_environment = merge(var.api_environment, {
    AZURE_CLIENT_ID             = azurerm_user_assigned_identity.api.client_id
    PYTHONUNBUFFERED            = "1"
    GRAPHIV_STORAGE_ACCOUNT_URL = azurerm_storage_account.data.primary_blob_endpoint
    GRAPHIV_VECTOR_CONTAINER    = local.containers.vectors
    GRAPHIV_GRAPH_CONTAINER     = local.containers.graphs
    GRAPHIV_METADATA_CONTAINER  = local.containers.metadata
    GRAPHIV_REPORTS_CONTAINER   = local.containers.reports
    GRAPHIV_CACHE_PATH          = "/var/lib/graphiv/cache"
    GRAPHIV_LLM_API_URL         = coalesce(var.llm_api_url, "not-configured")
    GRAPHIV_LLM_MODEL           = coalesce(var.llm_model, "not-configured")
    GRAPHIV_ALLOWED_HOSTS       = "${local.api_name}.${azurerm_container_app_environment.api.default_domain}"
    GRAPHIV_ARXIV_BASE_URL      = "https://arxiv.org"
  })
}

resource "azurerm_container_app" "api" {
  count = local.api_enabled ? 1 : 0

  name                         = local.api_name
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.api.id
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.api.id]
  }

  registry {
    server   = azurerm_container_registry.images.login_server
    identity = azurerm_user_assigned_identity.api.id
  }

  dynamic "secret" {
    for_each = var.llm_api_key_secret_name == null ? [] : [var.llm_api_key_secret_name]
    content {
      name                = "llm-api-key"
      identity            = azurerm_user_assigned_identity.api.id
      key_vault_secret_id = "${azurerm_key_vault.api.vault_uri}secrets/${secret.value}"
    }
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "auto"
    allow_insecure_connections = false

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # MCP rankings are process-local; do not scale out before externalizing session state.
    min_replicas = 1
    max_replicas = 1

    container {
      name    = "graphiv-api"
      image   = "${azurerm_container_registry.images.login_server}/graphiv-api:${var.api_image_tag}"
      cpu     = var.api_resources.cpu
      memory  = var.api_resources.memory
      command = var.api_command

      dynamic "env" {
        for_each = local.api_environment
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.llm_api_key_secret_name == null ? [] : ["llm-api-key"]
        content {
          name        = "GRAPHIV_LLM_API_KEY"
          secret_name = env.value
        }
      }

      # The existing server has no /health endpoint. These only prove that the listener is up.
      startup_probe {
        transport               = "TCP"
        port                    = 8000
        interval_seconds        = 5
        failure_count_threshold = 120
        timeout                 = 3
      }
      readiness_probe {
        transport               = "TCP"
        port                    = 8000
        interval_seconds        = 10
        failure_count_threshold = 3
        success_count_threshold = 1
        timeout                 = 3
      }
      liveness_probe {
        transport               = "TCP"
        port                    = 8000
        interval_seconds        = 30
        failure_count_threshold = 3
        timeout                 = 3
      }

      volume_mounts {
        name = "cache"
        path = "/var/lib/graphiv"
      }
    }

    volume {
      name         = "cache"
      storage_type = "EmptyDir"
    }
  }

  lifecycle {
    precondition {
      condition     = var.llm_api_url != null && var.llm_model != null
      error_message = "Set llm_api_url and llm_model before supplying api_image_tag."
    }
  }

  depends_on = [
    azurerm_role_assignment.image_pull,
    azurerm_role_assignment.vector_reader,
    azurerm_role_assignment.graph_metadata,
    azurerm_role_assignment.report_writer,
    azurerm_role_assignment.report_reader,
    azurerm_role_assignment.secret_reader,
  ]
}
