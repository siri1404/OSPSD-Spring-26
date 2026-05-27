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

  # Local backend for the course project. For production, migrate to a remote backend
  # (Terraform Cloud / S3+DynamoDB / GCS) so state can be shared across CI runs and
  # multiple team members. With a local backend, terraform apply from different machines
  # will diverge — each has its own state file that doesn't sync back to the repo.
  # This is acceptable for HW-3 grading where the single CI pipeline manages state,
  # but MUST be changed before any shared team deployment scenario.
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
    GCP_SERVICE_KEY            = { value = var.GCP_SERVICE_KEY, is_secret = true }
    GCS_BUCKET_NAME            = { value = var.GCS_BUCKET_NAME }
    GOOGLE_CLOUD_PROJECT       = { value = var.GOOGLE_CLOUD_PROJECT }
    GOOGLE_OAUTH_CLIENT_ID     = { value = var.GOOGLE_OAUTH_CLIENT_ID, is_secret = true }
    GOOGLE_OAUTH_CLIENT_SECRET = { value = var.GOOGLE_OAUTH_CLIENT_SECRET, is_secret = true }
    GOOGLE_OAUTH_REDIRECT_URI  = { value = var.GOOGLE_OAUTH_REDIRECT_URI }
    GEMINI_API_KEY             = { value = var.GEMINI_API_KEY, is_secret = true }
    # Peer review #3: env var must be SLACK_BOT_TOKEN (not CHAT_API_KEY) so
    # slack_adapter.py's os.getenv("SLACK_BOT_TOKEN") resolves correctly.
    SLACK_BOT_TOKEN = { value = var.SLACK_BOT_TOKEN, is_secret = true }
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
    # NOTE (Peer Review #8): Render's free-tier networking does NOT support private
    # service-to-service communication within a private network. The PROMETHEUS_SCRAPE_TARGET
    # must be a publicly resolvable hostname, not an internal service name.
    # This is a Render platform limitation. For production, either:
    # 1. Use a paid Render plan with private networking, or
    # 2. Deploy Prometheus externally and scrape the public cloud-storage endpoint.
    # Current target (cloud-storage-service:8000) will NOT work on free plan and
    # the Prometheus dashboard will show as having no scraped metrics.
    # To verify if scraping works: check /metrics endpoint manually via the public URL.
    PROMETHEUS_SCRAPE_TARGET = { value = "cloud-storage-service-mcni.onrender.com" }
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
    GF_SECURITY_ADMIN_PASSWORD = { value = var.GRAFANA_ADMIN_PASSWORD, is_secret = true }
    GF_SERVER_HTTP_PORT        = { value = "3000" }
    # Points Grafana at the Prometheus private service by its Render name.
    # Render resolves http://prometheus:9090 within the team network.
    GF_DATASOURCE_PROMETHEUS_URL = { value = "http://prometheus:9090" }
  }

  depends_on = [render_web_service.prometheus]
}
