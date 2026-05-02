# main.tf — Render infrastructure
#
# Provisions three services on Render via the render-oss/render provider:
#   - render_web_service.cloud_storage  → FastAPI app (public)
#   - render_web_service.prometheus     → Prometheus scraper
#   - render_web_service.grafana        → Grafana dashboards
#
# CI must attach the `render-deploy` context to `terraform apply` so all
# `TF_VAR_*` env vars resolve. Variables are declared in variables.tf.

terraform {
  required_version = ">= 1.6"

  required_providers {
    render = {
      source  = "render-oss/render"
      version = "~> 1.8"
    }
  }

  # Local backend for the course project. For production, migrate to a remote
  # backend (Terraform Cloud / S3+DynamoDB / GCS) so state can be shared
  # across CI runs.
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "render" {
  # api_key and owner_id are read from RENDER_API_KEY and RENDER_OWNER_ID
  # environment variables, injected by the render-deploy CircleCI context.
  wait_for_deploy_completion = true
}

# ============================================================================
# Cloud Storage FastAPI service
# ============================================================================
resource "render_web_service" "cloud_storage" {
  name              = "cloud-storage-service"
  plan              = "free"
  region            = var.RENDER_REGION
  health_check_path = "/health"

  runtime_source = {
    docker = {
      auto_deploy     = true
      branch          = var.GIT_BRANCH
      repo_url        = var.REPO_URL
      dockerfile_path = "./Dockerfile"
      context         = "."
    }
  }

  env_vars = {
    PORT                       = { value = "8000" }
    ENVIRONMENT                = { value = "production" }
    GCP_SERVICE_KEY            = { value = var.GCP_SERVICE_KEY }
    GCS_BUCKET_NAME            = { value = var.GCS_BUCKET_NAME }
    GOOGLE_CLOUD_PROJECT       = { value = var.GOOGLE_CLOUD_PROJECT }
    GOOGLE_OAUTH_CLIENT_ID     = { value = var.GOOGLE_OAUTH_CLIENT_ID }
    GOOGLE_OAUTH_CLIENT_SECRET = { value = var.GOOGLE_OAUTH_CLIENT_SECRET }
    GOOGLE_OAUTH_REDIRECT_URI  = { value = var.GOOGLE_OAUTH_REDIRECT_URI }
    GEMINI_API_KEY             = { value = var.GEMINI_API_KEY }
    # Peer review #3: env var must be SLACK_BOT_TOKEN (not CHAT_API_KEY) so
    # slack_adapter.py's os.getenv("SLACK_BOT_TOKEN") resolves correctly.
    SLACK_BOT_TOKEN = { value = var.SLACK_BOT_TOKEN }
    CHAT_CHANNEL_ID = { value = var.CHAT_CHANNEL_ID }
  }
}

# ============================================================================
# Prometheus — scrapes /metrics from the cloud_storage service
# ============================================================================
resource "render_web_service" "prometheus" {
  name              = "prometheus"
  plan              = "free"
  region            = var.RENDER_REGION
  health_check_path = "/-/healthy"

  runtime_source = {
    docker = {
      auto_deploy     = true
      branch          = var.GIT_BRANCH
      repo_url        = var.REPO_URL
      dockerfile_path = "./monitoring/Dockerfile.prometheus"
      context         = "./monitoring"
    }
  }

  env_vars = {
    # Use the Render-internal service name; resolved within the team network.
    PROMETHEUS_SCRAPE_TARGET = { value = "cloud-storage-service:8000" }
  }

  depends_on = [render_web_service.cloud_storage]
}

# ============================================================================
# Grafana — dashboards on top of Prometheus
# ============================================================================
resource "render_web_service" "grafana" {
  name              = "grafana"
  plan              = "free"
  region            = var.RENDER_REGION
  health_check_path = "/api/health"

  runtime_source = {
    docker = {
      auto_deploy     = true
      branch          = var.GIT_BRANCH
      repo_url        = var.REPO_URL
      dockerfile_path = "./monitoring/Dockerfile.grafana"
      context         = "./monitoring"
    }
  }

  env_vars = {
    GF_SECURITY_ADMIN_USER     = { value = "admin" }
    GF_SECURITY_ADMIN_PASSWORD = { value = var.GRAFANA_ADMIN_PASSWORD }
    GF_SERVER_HTTP_PORT        = { value = "3000" }
    # Points Grafana at the Prometheus private service by its Render name.
    # Render resolves http://prometheus:9090 within the team network.
    GF_DATASOURCE_PROMETHEUS_URL = { value = "http://prometheus:9090" }
  }

  depends_on = [render_web_service.prometheus]
}
