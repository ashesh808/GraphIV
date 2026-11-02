resource "vercel_project" "web" {
  name           = var.project_name
  framework      = "nextjs"
  root_directory = "apps/web"
  node_version   = "22.x"

  git_repository = {
    type              = "github"
    repo              = var.git_repo
    production_branch = var.production_branch
  }
}

resource "vercel_project_environment_variable" "backend_url" {
  project_id = vercel_project.web.id
  key        = "GRAPHIV_API_URL"
  value      = trimsuffix(var.backend_url, "/")
  target     = ["production", "preview", "development"]
  # A backend origin is configuration, not a credential. The application reads
  # this variable only from its server-only data module.
  sensitive = false
  comment   = "HTTPS origin of the GraphIV backend, read by the Next.js server."
}

resource "vercel_project_environment_variable" "api_token" {
  project_id       = vercel_project.web.id
  key              = "GRAPHIV_API_TOKEN"
  value_wo         = var.api_token
  value_wo_version = var.api_token_version
  target           = ["production", "preview", "development"]
  sensitive        = true
  comment          = "Server-only bearer credential matching the GraphIV backend."
}
