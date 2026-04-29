# main.tf — Render infrastructure
#
# Provisions three services on Render using the official render-oss/render
# provider:
#   - render_web_service.cloud_storage     → FastAPI app (public)
#   - render_private_service.prometheus    → Prometheus scraper (private)
#   - render_web_service.grafana           → Grafana dashboards (public)
#
# Keep this file in sync with ../render.yaml. The YAML blueprint is for
# manual Render dashboard imports; this Terraform is what CI runs.

terraform {
  required_version = ">= 1.6"

  required_providers {
    render = {
      source  = "render-oss/render"
      version = "~> 1.6"
    }
  }

  # Local backend for the course project. For real production, switch this to
  # a remote backend (Terraform Cloud / S3+DynamoDB / GCS) so state can be
  # shared across CI runs.
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "render" {
  # api_key and owner_id are read from RENDER_API_KEY and RENDER_OWNER_ID
  # environment variables. CI injects them from the render-deploy context.
  wait_for_deploy_completion = true
}

# Cloud Storage FastAPI service
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
    GCP_SERVICE_KEY            = { value = var.GCP_SERVICE_KEY }
    GCS_BUCKET_NAME            = { value = var.GCS_BUCKET_NAME }
    GOOGLE_CLOUD_PROJECT       = { value = var.GOOGLE_CLOUD_PROJECT }
    GOOGLE_OAUTH_CLIENT_ID     = { value = var.GOOGLE_OAUTH_CLIENT_ID }
    GOOGLE_OAUTH_CLIENT_SECRET = { value = var.GOOGLE_OAUTH_CLIENT_SECRET }
    GOOGLE_OAUTH_REDIRECT_URI  = { value = var.GOOGLE_OAUTH_REDIRECT_URI }
    GEMINI_API_KEY             = { value = var.GEMINI_API_KEY }
    CHAT_API_KEY               = { value = var.SLACK_BOT_TOKEN }
    CHAT_CHANNEL_ID            = { value = var.CHAT_CHANNEL_ID }
  }
}

# Prometheus — scrapes /metrics from the cloud_storage service
resource "render_private_service" "prometheus" {
  name   = "prometheus"
  plan   = "free"
  region = var.RENDER_REGION

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
    PROMETHEUS_SCRAPE_TARGET = { value = "cloud-storage-service-mcni.onrender.com" }
  }

  # Prometheus is deployed after the app so it has a target to scrape.
  depends_on = [render_web_service.cloud_storage]
}

# Grafana — dashboards on top of Prometheus
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

  depends_on = [render_private_service.prometheus]
}
