output "resource_group_name" {
  description = "Resource group containing GraphIV."
  value       = azurerm_resource_group.main.name
}

output "storage_account_name" {
  value = azurerm_storage_account.data.name
}

output "storage_blob_endpoint" {
  value = azurerm_storage_account.data.primary_blob_endpoint
}

output "storage_containers" {
  description = "Container names keyed by purpose; authentication uses managed identity, never account keys."
  value       = local.containers
}

output "api_identity_client_id" {
  value = azurerm_user_assigned_identity.api.client_id
}

output "registry_name" {
  value = azurerm_container_registry.images.name
}

output "registry_login_server" {
  value = azurerm_container_registry.images.login_server
}

output "key_vault_name" {
  value = azurerm_key_vault.api.name
}

output "llm_api_key_secret_uri" {
  description = "URI only; populate the secret value outside Terraform before activating the API."
  value       = var.llm_api_key_secret_name == null ? null : "${azurerm_key_vault.api.vault_uri}secrets/${var.llm_api_key_secret_name}"
}

output "backend_url" {
  description = "Stable HTTPS backend origin for infra/vercel. Null until api_image_tag activates the API."
  value       = local.api_enabled ? "https://${azurerm_container_app.api[0].ingress[0].fqdn}" : null
}

output "mcp_url" {
  value = local.api_enabled ? "https://${azurerm_container_app.api[0].ingress[0].fqdn}/mcp" : null
}

output "runtime_cache_share_name" {
  description = "Optional persistent corpus/model cache share; reports remain in Blob storage."
  value       = var.runtime_cache_share ? azurerm_storage_share.runtime_cache[0].name : null
}

output "index_builder_job_name" {
  description = "Optional manually triggered offline job. Creating the job does not start an execution."
  value       = local.index_builder_enabled ? azurerm_container_app_job.index_builder[0].name : null
}
