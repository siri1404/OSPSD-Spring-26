# Deployment

How the Cloud Storage service and its monitoring stack get onto Render — and how CI rolls them forward on every push to hw-3.

## What gets deployed

Three Render services, all declared in `infrastructure/main.tf`:

| Service | Type | Purpose |
|---|---|---|
| `cloud-storage-service` | public web service (Docker) | FastAPI app — serves `/upload`, `/download`, `/ai/chat`, `/metrics`, etc. |
| `prometheus` | public web service (Docker) | Scrapes `cloud-storage-service/metrics` every 10s via the public HTTPS URL. |
| `grafana` | public web service (Docker) | Dashboards on top of Prometheus. Connects via the public Prometheus URL. |

The Terraform files in `infrastructure/` are the source of truth for all infrastructure.

## One-time setup

You need a Render account, an API key, and your owner ID.

1. Create a Render account and a team (free tier is fine).
2. Generate a Personal Access Token at <https://dashboard.render.com/account/settings> → **API Keys**. Save it as `RENDER_API_KEY`.
3. Find your owner ID. Go to team settings; the ID in the URL looks like `tea-xxxxxxxxxxxxxxxxxxxx` (or `usr-...` for a personal account). Save it as `RENDER_OWNER_ID`.
4. In CircleCI, create a context called `render-deploy` and add every secret listed in the "Required secrets" table below.

## Local Terraform workflow

Use this when you want to test infrastructure changes before opening a PR. Never commit `terraform.tfvars` — it's in `infrastructure/.gitignore`.

```bash
cd infrastructure

# Copy the template and fill in real values.
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars

# Point the provider at your Render account.
export RENDER_API_KEY="rnd_xxxxxxxxxxxxxxxxxxxx"
export RENDER_OWNER_ID="tea-xxxxxxxxxxxxxxxxxxxx"

# Standard Terraform loop.
terraform init            # downloads the render-oss/render provider
terraform fmt -recursive  # format .tf files
terraform validate        # static syntax + schema check
terraform plan            # shows what would change
terraform apply           # actually creates/updates Render services
```

After `apply` finishes, the outputs you care about are:

```bash
terraform output service_url     # → https://cloud-storage-service-xxxx.onrender.com
terraform output grafana_url     # → https://grafana-xxxx.onrender.com
```

`service_url` is what the e2e test suite consumes as `STAGING_SERVICE_URL` and what the Prometheus scrape config points at.

To tear everything down:

```bash
terraform destroy
```

## Known limitation: terraform_apply on Render free tier

The terraform_apply CI job is currently disabled. The render-oss/render v1.8.0 Terraform provider unconditionally sends maintenance_mode in every update payload. Render's free-tier API rejects requests that include this field — there is no provider version that omits it on free tier.

Code deploys continue to flow via Render's auto_deploy = true setting. The terraform_plan job still validates IaC on every push. Re-enable terraform_apply when the project moves to a paid Render tier or a new provider version omits maintenance_mode on free tier.

For local use, terraform apply works if you import the existing services first:

```bash
terraform import render_web_service.cloud_storage $RENDER_SERVICE_ID
terraform plan -out=tfplan
terraform apply tfplan
```

## CI deploy flow

The pipeline has three groups of jobs. Full graph in `.circleci/config.yml`.

```
build → lint ─────────────────────┐
      - typecheck                 │
      - unit_test → integration_test ──┐
      - mkdocs_build              │    │
              └─ terraform_plan ──┘    │
                                       │
              (hw-3 branch only)       │
                                       ↓
                            check_render_deploy
                                       ↓
                            post_deploy_e2e
```

- **`terraform_plan`** runs on every branch except `main`. It formats, validates, and runs `terraform plan` so reviewers can see the infra diff in the PR.
- **`check_render_deploy`** polls the Render API until the deploy status reports `live` or `succeeded`. Runs only on `hw-3` after `integration_test` passes.
- **`post_deploy_e2e`** runs after `check_render_deploy`. It waits 10s for Render's auto_deploy to settle, then runs `tests/e2e/test_e2e_workflow.py` against the live deployed service. Requires the render-deploy CircleCI context for RENDER_SERVICE_URL, DEV_AUTH_TOKEN, and GCS_BUCKET_NAME.

Note: `terraform_apply` is disabled (see "Known limitation" above). Deployment happens via Render's auto_deploy feature, which triggers a new deploy whenever code is pushed to `hw-3`.

## Required secrets

All of these go in the CircleCI **`render-deploy`** context. Terraform reads the `TF_VAR_*` ones automatically.

| Secret | Consumer | Notes |
|---|---|---|
| `RENDER_API_KEY` | Terraform provider + `check_render_deploy` | Personal access token. |
| `RENDER_OWNER_ID` | Terraform provider | `tea-...` or `usr-...`. |
| `RENDER_SERVICE_ID` | `check_render_deploy` + terraform import | Cloud storage service ID. |
| `RENDER_SERVICE_URL` | `post_deploy_e2e` | Public URL of the deployed service. |
| `DEV_AUTH_TOKEN` | `post_deploy_e2e` | Bearer token for E2E test authentication. |
| `GCS_BUCKET_NAME` | `post_deploy_e2e` | Bucket name for E2E storage operations. |
| `TF_VAR_GCP_SERVICE_KEY` | Terraform | Base64-encoded service account JSON. |
| `TF_VAR_GCS_BUCKET_NAME` | Terraform |  |
| `TF_VAR_GOOGLE_CLOUD_PROJECT` | Terraform |  |
| `TF_VAR_GOOGLE_OAUTH_CLIENT_ID` | Terraform |  |
| `TF_VAR_GOOGLE_OAUTH_CLIENT_SECRET` | Terraform |  |
| `TF_VAR_GEMINI_API_KEY` | Terraform | Google Gemini API key for AI integration. |
| `TF_VAR_SLACK_BOT_TOKEN` | Terraform | Slack bot token for chat notifications. |
| `TF_VAR_CHAT_CHANNEL_ID` | Terraform | Slack channel ID. |
| `TF_VAR_GRAFANA_ADMIN_PASSWORD` | Terraform | Initial Grafana admin password. |

`GOOGLE_OAUTH_REDIRECT_URI` has a default in `variables.tf` and doesn't need to be set unless you move to a new Render URL.

## What happens when the service URL changes

Render domains look like `cloud-storage-service-<hash>.onrender.com`. The hash is stable across redeploys of the same service, but if Terraform creates a new service (e.g., you changed `name`), the URL changes.

If that happens:

1. `terraform output service_url` gives you the new URL.
2. Update `google_oauth_redirect_uri` in your `terraform.tfvars` (or update the GCP Console OAuth config to add the new redirect) and re-apply.
3. Update the hard-coded scrape target in `monitoring/prometheus.yml`.
4. Update the `PROMETHEUS_SCRAPE_TARGET` env var in `infrastructure/main.tf`.

## Troubleshooting

**`terraform init` fails with "could not authenticate"** — `RENDER_API_KEY` isn't set in the shell. The provider accepts it as an env var; double-check with `echo $RENDER_API_KEY`.

**`terraform apply` fails with "maintenance_mode" error** — this is the known Render free-tier limitation. Use auto_deploy instead (see "Known limitation" above).

**`post_deploy_e2e` fails with "connection refused"** — check the Render dashboard for the service's health. Free-tier services sleeping is the most common cause; a Render build failure is the second. `curl https://cloud-storage-service-mcni.onrender.com/health` will tell you quickly.

**Grafana shows "No data"** — verify the Prometheus datasource URL in `monitoring/grafana-datasource.yml` matches the actual Prometheus Render URL (`https://cloud-service-prometheus.onrender.com`). Also verify the Prometheus scrape target in `monitoring/prometheus.yml` matches the service URL.

**Docker build fails with `git: command not found`** — the Dockerfile installs git explicitly because `pyproject.toml` pulls `chat-client-api` as a git dependency. If you see this error, something stripped the `apt-get install git` line.

## Related docs

- [`circleci-setup.md`](circleci-setup.md) — CircleCI project setup and GCP service key encoding.
- [`testing.md`](testing.md) — what each test suite covers and how markers work.
- `observability.md` — what each metric means and how to read the dashboard.