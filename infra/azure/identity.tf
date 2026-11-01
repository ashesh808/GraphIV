resource "azurerm_role_assignment" "image_pull" {
  scope                            = azurerm_container_registry.images.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_user_assigned_identity.api.principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "vector_reader" {
  scope                            = azurerm_storage_container.data["vectors"].id
  role_definition_name             = "Storage Blob Data Reader"
  principal_id                     = azurerm_user_assigned_identity.api.principal_id
  skip_service_principal_aad_check = true
}

# Built-in Blob Data Contributor also permits deletion. These roles deliberately do not.
resource "azurerm_role_definition" "blob_read_write" {
  name        = "${local.base_name}-blob-read-write-${random_string.suffix.result}"
  scope       = azurerm_resource_group.main.id
  description = "Read, create and overwrite graph/metadata blobs without deleting them."

  permissions {
    actions = ["Microsoft.Storage/storageAccounts/blobServices/containers/read"]
    data_actions = [
      "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read",
      "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write",
      "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/add/action",
    ]
  }
  assignable_scopes = [azurerm_resource_group.main.id]
}

resource "azurerm_role_assignment" "graph_metadata" {
  for_each = toset(["graphs", "metadata"])

  scope                            = azurerm_storage_container.data[each.value].id
  role_definition_id               = azurerm_role_definition.blob_read_write.role_definition_resource_id
  principal_id                     = azurerm_user_assigned_identity.api.principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_definition" "report_writer" {
  name        = "${local.base_name}-report-writer-${random_string.suffix.result}"
  scope       = azurerm_resource_group.main.id
  description = "Create and overwrite report blobs without reading, listing or deleting them."

  permissions {
    actions = ["Microsoft.Storage/storageAccounts/blobServices/containers/read"]
    data_actions = [
      "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write",
      "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/add/action",
    ]
  }
  assignable_scopes = [azurerm_resource_group.main.id]
}

resource "azurerm_role_assignment" "report_writer" {
  scope                            = azurerm_storage_container.data["reports"].id
  role_definition_id               = azurerm_role_definition.report_writer.role_definition_resource_id
  principal_id                     = azurerm_user_assigned_identity.api.principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "report_reader" {
  count = var.allow_report_reads ? 1 : 0

  scope                            = azurerm_storage_container.data["reports"].id
  role_definition_name             = "Storage Blob Data Reader"
  principal_id                     = azurerm_user_assigned_identity.api.principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "artifact_publisher" {
  for_each = var.publisher_principal_id == null ? toset([]) : toset(["vectors", "graphs", "metadata"])

  scope                = azurerm_storage_container.data[each.value].id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.publisher_principal_id
}

resource "azurerm_role_assignment" "secret_reader" {
  scope                            = azurerm_key_vault.api.id
  role_definition_name             = "Key Vault Secrets User"
  principal_id                     = azurerm_user_assigned_identity.api.principal_id
  skip_service_principal_aad_check = true
}

# The deploying identity can populate keys with Azure CLI; Terraform never handles their values.
resource "azurerm_role_assignment" "secret_operator" {
  scope                = azurerm_key_vault.api.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}
