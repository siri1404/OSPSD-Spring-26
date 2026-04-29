# outputs.tf — surfaces URLs and IDs the CI pipeline and docs consume.
#
# - `service_url` is written to deploy-output/staging_service_url.txt by the
#   terraform_apply CI job and read back as STAGING_SERVICE_URL by
#   post_deploy_e2e.
# - `grafana_url` is where you log in to view dashboards after a deploy.
# - `cloud_storage_service_id` is used by the check_render_deploy job to
#   poll the Render API for deploy status.

output "service_url" {
  description = "Public URL of the deployed cloud storage service (use as STAGING_SERVICE_URL)."
  value       = render_web_service.cloud_storage.url
}

output "grafana_url" {
  description = "Public URL of the Grafana dashboard."
  value       = render_web_service.grafana.url
}

output "prometheus_service_name" {
  description = "Render name for the Prometheus private service (reachable only from Grafana)."
  value       = render_web_service.prometheus.name
}

output "cloud_storage_service_id" {
  description = "Render service ID for the FastAPI app — needed by the CI deploy-status poller."
  value       = render_web_service.cloud_storage.id
}
