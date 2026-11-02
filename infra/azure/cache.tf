# The share is a rebuildable corpus/model cache; reports remain durable Blob objects.
resource "azurerm_storage_share" "runtime_cache" {
  count = var.runtime_cache_share ? 1 : 0

  name               = "runtime-cache"
  storage_account_id = azurerm_storage_account.data.id
  quota              = 100
  enabled_protocol   = "SMB"
  access_tier        = "TransactionOptimized"
}

# SMB mounts authenticate as the environment identity, not as the API/job identity.
resource "azurerm_user_assigned_identity" "cache" {
  count = var.runtime_cache_share ? 1 : 0

  name                = "id-${local.base_name}-cache"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}

resource "azurerm_role_assignment" "cache_mount" {
  count = var.runtime_cache_share ? 1 : 0

  scope                            = azurerm_storage_account.data.id
  role_definition_name             = "Storage File Data SMB MI Admin"
  principal_id                     = azurerm_user_assigned_identity.cache[0].principal_id
  skip_service_principal_aad_check = true
}

# AzureRM 5.12 does not expose this setting. PATCH only the SMB OAuth field;
# preserve the storage account's other authentication and Kerberos settings.
resource "azapi_update_resource" "cache_smb_oauth" {
  count = var.runtime_cache_share ? 1 : 0

  type        = "Microsoft.Storage/storageAccounts@2025-01-01"
  resource_id = azurerm_storage_account.data.id
  body = {
    properties = {
      azureFilesIdentityBasedAuthentication = {
        smbOAuthSettings = { isSmbOAuthEnabled = true }
      }
    }
  }
}

# Identity-based SMB mounts are exposed in the preview storage API, not in
# AzureRM's account-key-only environment-storage resource or the stable API.
resource "azapi_resource" "cache_storage" {
  count = var.runtime_cache_share ? 1 : 0

  type                      = "Microsoft.App/managedEnvironments/storages@2026-03-02-preview"
  name                      = "runtime-cache"
  parent_id                 = azapi_resource.environment.id
  schema_validation_enabled = false
  body = {
    properties = {
      azureFile = {
        accountName = azurerm_storage_account.data.name
        shareName   = azurerm_storage_share.runtime_cache[0].name
        identity    = azurerm_user_assigned_identity.cache[0].id
        accessMode  = "ReadWrite"
      }
    }
  }

  depends_on = [azapi_update_resource.cache_smb_oauth, azurerm_role_assignment.cache_mount]
}
