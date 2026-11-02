mock_provider "vercel" {}

variables {
  backend_url       = "https://graphiv-api.example.com/"
  api_token         = "test-only-api-token-with-32-characters-minimum"
  api_token_version = 1
  project_name      = "graphiv"
  git_repo          = "ashesh808/GraphIV"
  production_branch = "main"
  team              = null
}

run "frontend_project" {
  command = plan

  assert {
    condition = (
      vercel_project_environment_variable.api_token.key == "GRAPHIV_API_TOKEN" &&
      vercel_project_environment_variable.api_token.sensitive == true &&
      vercel_project_environment_variable.api_token.target == toset(["production", "preview", "development"]) &&
      vercel_project_environment_variable.api_token.value_wo_version == 1 &&
      vercel_project_environment_variable.api_token.value == null
    )
    error_message = "The backend token must be a server-only secret using the write-only provider field."
  }

  assert {
    condition = (
      vercel_project.web.name == "graphiv" &&
      vercel_project.web.framework == "nextjs" &&
      vercel_project.web.root_directory == "apps/web" &&
      vercel_project.web.node_version == "22.x"
    )
    error_message = "The project must build the Next.js frontend from apps/web on Node.js 22."
  }

  assert {
    condition = (
      vercel_project.web.git_repository.type == "github" &&
      vercel_project.web.git_repository.repo == "ashesh808/GraphIV" &&
      vercel_project.web.git_repository.production_branch == "main"
    )
    error_message = "The project must connect to the requested GitHub repository."
  }

  assert {
    condition = (
      vercel_project_environment_variable.backend_url.key == "GRAPHIV_API_URL" &&
      !startswith(vercel_project_environment_variable.backend_url.key, "NEXT_PUBLIC_") &&
      vercel_project_environment_variable.backend_url.value == "https://graphiv-api.example.com" &&
      vercel_project_environment_variable.backend_url.target == toset(["production", "preview", "development"]) &&
      vercel_project_environment_variable.backend_url.sensitive == false
    )
    error_message = "The backend origin must be server-only configuration for every Vercel environment."
  }

  assert {
    condition     = output.git_repository_url == "https://github.com/ashesh808/GraphIV"
    error_message = "The repository output must point to the connected source."
  }
}

run "custom_project_scope" {
  command = plan

  variables {
    project_name      = "graphiv-preview"
    git_repo          = "example/research"
    team              = "example-team"
    production_branch = "ashesh/refactor-deployment-frontend"
  }

  assert {
    condition = (
      vercel_project.web.name == "graphiv-preview" &&
      vercel_project.web.git_repository.repo == "example/research" &&
      vercel_project.web.git_repository.production_branch == "ashesh/refactor-deployment-frontend" &&
      output.production_branch == "ashesh/refactor-deployment-frontend"
    )
    error_message = "Project, repository, and production branch overrides must configure the managed project."
  }
}

run "reject_http_backend" {
  command = plan
  variables {
    backend_url = "http://graphiv-api.example.com"
  }
  expect_failures = [var.backend_url]
}

run "reject_localhost_backend" {
  command = plan
  variables {
    backend_url = "https://localhost:6969"
  }
  expect_failures = [var.backend_url]
}

run "reject_local_dns_backend" {
  command = plan
  variables {
    backend_url = "https://graphiv.localhost"
  }
  expect_failures = [var.backend_url]
}

run "reject_ip_backend" {
  command = plan
  variables {
    backend_url = "https://127.0.0.1"
  }
  expect_failures = [var.backend_url]
}

run "reject_embedded_credentials" {
  command = plan
  variables {
    backend_url = "https://user:password@graphiv-api.example.com"
  }
  expect_failures = [var.backend_url]
}

run "reject_api_path" {
  command = plan
  variables {
    backend_url = "https://graphiv-api.example.com/api"
  }
  expect_failures = [var.backend_url]
}

run "reject_short_api_token" {
  command = plan
  variables {
    api_token = "too-short"
  }
  expect_failures = [var.api_token]
}

run "rotate_api_token" {
  command = plan
  variables {
    api_token         = "test-only-replacement-api-token-over-32-characters"
    api_token_version = 2
  }
  assert {
    condition     = vercel_project_environment_variable.api_token.value_wo_version == 2
    error_message = "Rotating a token must set the write-only value version."
  }
}
