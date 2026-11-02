locals {
  api_enabled = var.api_image_tag != null

  api_environment = merge(var.api_environment, {
    AZURE_CLIENT_ID             = azurerm_user_assigned_identity.api.client_id
    PYTHONUNBUFFERED            = "1"
    GRAPHIV_STORAGE_ACCOUNT_URL = azurerm_storage_account.data.primary_blob_endpoint
    GRAPHIV_VECTOR_CONTAINER    = local.containers.vectors
    GRAPHIV_GRAPH_CONTAINER     = local.containers.graphs
    GRAPHIV_METADATA_CONTAINER  = local.containers.metadata
    GRAPHIV_REPORTS_CONTAINER   = local.containers.reports
    GRAPHIV_CACHE_PATH          = "/var/lib/graphiv/cache"
    GRAPHIV_RUNTIME             = "azure"
    GRAPHIV_STORAGE_BACKEND     = var.corpus_backend
    GRAPHIV_ALLOWED_HOSTS       = "${local.api_name}.${azapi_resource.environment.output.properties.defaultDomain}"
    GRAPHIV_ARXIV_BASE_URL      = "https://arxiv.org"
    }, { for name, value in {
      GRAPHIV_LLM_API_URL   = var.llm_api_url
      GRAPHIV_LLM_MODEL     = var.llm_model
      GRAPHIV_EMBED_API_URL = var.embedding_api_url
      GRAPHIV_EMBED_MODEL   = var.embedding_model
    } : name => value if value != null }
  )

  api_secrets = merge(
    { "api-token" = { env = "GRAPHIV_API_TOKEN", name = var.api_token_secret_name } },
    var.llm_api_key_secret_name == null ? {} : {
      "llm-api-key" = { env = "GRAPHIV_LLM_API_KEY", name = var.llm_api_key_secret_name }
    },
    var.embedding_api_key_secret_name == null ? {} : {
      "embedding-api-key" = { env = "GRAPHIV_EMBED_API_KEY", name = var.embedding_api_key_secret_name }
    },
    var.corpus_backend == "postgres" && var.postgres_dsn_secret_name != null ? {
      "postgres-dsn" = { env = "GRAPHIV_POSTGRES_DSN", name = var.postgres_dsn_secret_name }
    } : {},
  )
}

resource "azurerm_container_app" "api" {
  count = local.api_enabled ? 1 : 0

  lifecycle {
    precondition {
      condition     = var.corpus_backend != "postgres" || var.postgres_dsn_secret_name != null
      error_message = "Set postgres_dsn_secret_name before activating the API with corpus_backend = postgres. The DSN value must stay in Key Vault."
    }
  }

  name                         = local.api_name
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azapi_resource.environment.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
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
    for_each = local.api_secrets
    content {
      name                = secret.key
      identity            = azurerm_user_assigned_identity.api.id
      key_vault_secret_id = "${azurerm_key_vault.api.vault_uri}secrets/${secret.value.name}"
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
        for_each = local.api_secrets
        content {
          name        = env.value.env
          secret_name = env.key
        }
      }

      # Serving saved reports is available before the research corpus/models are configured.
      # /health/ready reports research readiness separately; routing checks the HTTP listener.
      startup_probe {
        transport               = "HTTP"
        path                    = "/health/live"
        port                    = 8000
        interval_seconds        = 5
        failure_count_threshold = 120
        timeout                 = 3
      }
      readiness_probe {
        transport               = "HTTP"
        path                    = "/health/live"
        port                    = 8000
        interval_seconds        = 10
        failure_count_threshold = 3
        success_count_threshold = 1
        timeout                 = 3
      }
      liveness_probe {
        transport               = "HTTP"
        path                    = "/health/live"
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

  depends_on = [
    azurerm_role_assignment.image_pull,
    azurerm_role_assignment.vector_reader,
    azurerm_role_assignment.graph_metadata,
    azurerm_role_assignment.report_writer,
    azurerm_role_assignment.report_reader,
    azurerm_role_assignment.secret_reader,
  ]
}
