# variables.tf — inputs to the Render infrastructure.
#
# All secret values are marked `sensitive = true` so Terraform won't print them
# in plan/apply output or logs. Supply them at apply time via:
#   - a tfvars file NOT committed to git (terraform.tfvars),
#   - -var="key=value" CLI flags, or
#   - TF_VAR_<n> environment variables in CI.
#
# Preferred in CI: TF_VAR_* env vars mapped from CircleCI context secrets.

# Deployment target
variable "REPO_URL" {
  description = "GitHub repo URL Render should deploy from."
  type        = string
  default     = "https://github.com/siri1404/OSPSD-Spring-26"
}

variable "GIT_BRANCH" {
  description = "Branch Render should track for auto-deploys."
  type        = string
  default     = "hw-3"
}

variable "RENDER_REGION" {
  description = "Render region for all services (keep them co-located)."
  type        = string
  default     = "oregon"
}

# GCP / storage secrets
variable "GCP_SERVICE_KEY" {
  description = "Base64-encoded GCP service account JSON key."
  type        = string
  sensitive   = true
}

variable "GCS_BUCKET_NAME" {
  description = "Name of the GCS bucket the service reads and writes to."
  type        = string
}

variable "GOOGLE_CLOUD_PROJECT" {
  description = "GCP project ID."
  type        = string
}

variable "GOOGLE_OAUTH_CLIENT_ID" {
  description = "OAuth client ID for user login flow."
  type        = string
  sensitive   = true
}

variable "GOOGLE_OAUTH_CLIENT_SECRET" {
  description = "OAuth client secret."
  type        = string
  sensitive   = true
}

variable "GOOGLE_OAUTH_REDIRECT_URI" {
  description = "OAuth redirect URI. Must match what's registered in GCP Console."
  type        = string
  default     = "https://cloud-storage-service-mcni.onrender.com/auth/callback"
}

# AI integration
variable "GEMINI_API_KEY" {
  description = "Google Gemini API key — used by POST /ai/chat."
  type        = string
  sensitive   = true
}

# Chat integration
variable "SLACK_BOT_TOKEN" {
  description = "API key / bot token for the chat provider."
  type        = string
  sensitive   = true
}

variable "CHAT_CHANNEL_ID" {
  description = "Channel ID the ChatNotificationWrapper posts to."
  type        = string
}

# Grafana
variable "GRAFANA_ADMIN_PASSWORD" {
  description = "Initial admin password for Grafana. Rotate after first login."
  type        = string
  sensitive   = true
}
