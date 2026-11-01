output "project_id" {
  value       = vercel_project.web.id
  description = "Vercel project ID; project creation alone does not establish a deployed frontend URL."
}

output "project_name" {
  value       = vercel_project.web.name
  description = "Name of the managed Vercel project."
}

output "backend_url" {
  value       = trimsuffix(var.backend_url, "/")
  description = "Configured backend origin used for production, preview, and development."
}

output "production_branch" {
  value       = var.production_branch
  description = "Git branch configured for production builds."
}

output "git_repository_url" {
  value       = "https://github.com/${var.git_repo}"
  description = "Git repository connected to Vercel's build and deployment integration."
}

output "vercel_dashboard_url" {
  value       = "https://vercel.com/dashboard"
  description = "Find the project's production and preview deployment URLs here after Git integration builds succeed."
}
