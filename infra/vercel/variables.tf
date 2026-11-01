variable "backend_url" {
  type        = string
  nullable    = false
  description = "Externally reachable HTTPS backend origin, without credentials, query parameters, or an API path."

  validation {
    condition = (
      can(regex("^https://[A-Za-z0-9][A-Za-z0-9.-]*\\.[A-Za-z]{2,}(:[0-9]{1,5})?/?$", var.backend_url)) &&
      !can(regex("(?i)^https://[^/:]+\\.(localhost|local|internal)(:|/|$)", var.backend_url))
    )
    error_message = "backend_url must be a public HTTPS origin with a DNS hostname, such as https://graphiv-api.example.com. Localhost, IP addresses, credentials, query parameters, and API paths are not supported."
  }
}

variable "project_name" {
  type        = string
  default     = "graphiv"
  nullable    = false
  description = "Name of the Vercel project."

  validation {
    condition = (
      length(var.project_name) <= 100 &&
      can(regex("^[a-z0-9][a-z0-9._-]*$", var.project_name)) &&
      !strcontains(var.project_name, "---")
    )
    error_message = "project_name must be 1–100 lowercase letters, digits, dots, underscores, or hyphens, start with a letter or digit, and contain no triple hyphens."
  }
}

variable "git_repo" {
  type        = string
  default     = "ashesh808/GraphIV"
  nullable    = false
  description = "GitHub repository in owner/repository form; the Vercel GitHub app must be authorized for it."

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.git_repo))
    error_message = "git_repo must use owner/repository form, without a URL or branch."
  }
}

variable "production_branch" {
  type        = string
  default     = "main"
  nullable    = false
  description = "Git branch that Vercel builds as production; it must contain the apps/web frontend."

  validation {
    condition     = length(var.production_branch) > 0 && !can(regex("[[:space:]]", var.production_branch))
    error_message = "production_branch must be a nonempty Git branch name without whitespace."
  }
}

variable "team" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional Vercel team slug or team ID. Null uses the token's default account scope."

  validation {
    condition     = var.team == null ? true : length(trimspace(var.team)) > 0
    error_message = "team must be null or a nonempty Vercel team slug or ID."
  }
}
