# Deployment

How the Cloud Storage service and its monitoring stack get onto Render — and how CI rolls them forward on every push to `hw-3`.

## What gets deployed

Three Render services, all declared in [`infrastructure/main.tf`](../infrastructure/main.tf) and mirrored in [`render.yaml`](../render.yaml):

| Service | Type | Purpose |
|---|---|---|
| `cloud-storage-service` | public web service (Docker) | FastAPI app — serves `/upload`, `/download`, `/ai/chat`, `/metrics`, etc. |
| `prometheus` | private service (Docker) | Scrapes `cloud-storage-service/metrics` every 15s. Reachable only from other services in the same Render team. |
| `grafana` | public web service (Docker) | Dashboards on top of Prometheus. Talks to it as `http://prometheus:9090`. |

`render.yaml` exists so anyone can import the blueprint by hand through the Render dashboard. The Terraform files in `infrastructure/` are the source of truth — CI only runs Terraform, never the YAML blueprint.

## One-time setup

You need a Render account, an API key, and your owner ID.

1. Create a Render account and a team (free tier is fine).
2. Generate a Personal Access Token at <https://dashboard.render.com/account/settings> → **API Keys**. Save it as `RENDER_API_KEY`.
3. Find your owner ID. Go to team settings; the ID in the URL looks like `tea-xxxxxxxxxxxxxxxxxxxx` (or `usr-...` for a personal account). Save it as `RENDER_OWNER_ID`.
4. In CircleCI, create a context called `render-deploy` and add every secret listed in the "Required secrets" table below.

## Local Terraform workflow

Use this when you want to test infrastructure changes before opening a PR. Never commit `terraform.tfvars` — it's in [`infrastructure/.gitignore`](../infrastructure/.gitignore).

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

## CI deploy flow

The pipeline has three groups of jobs. Full graph in [`.circleci/config.yml`](../.circleci/config.yml).

```
build → lint ─┐
              ├─ unit_test → integration_test ──────────────┐
typecheck ────┘                                             │
              └─ terraform_plan ───────────────────────────┤
                                                           │
              (hw-3 branch only)     ┌────────────────────┘
                                     ↓
                          terraform_apply
                                     ↓
                          post_deploy_e2e
                                     ↓
                          check_render_deploy
```

- **`terraform_plan`** runs on every branch except `main`. It formats, validates, and runs `terraform plan`, saving a plan file for later so reviewers can see the infra diff in the PR.
- **`terraform_apply`** runs only on `hw-3`, after `integration_test` passes and `terraform_plan` has a clean plan. It applies the saved plan and writes the resulting `service_url` to `deploy-output/staging_service_url.txt` in the workspace.
- **`post_deploy_e2e`** reads that file into `STAGING_SERVICE_URL` and runs `tests/e2e/` against the freshly deployed service. The e2e suite is skip-by-default when `STAGING_SERVICE_URL` is unset, so it only runs meaningfully here — right after a real deploy — which keeps the "does the deployment itself work?" signal separate from the "does my code work?" signal earlier in the pipeline.
- **`check_render_deploy`** polls the Render API until the deploy status reports `live` or `succeeded`.

## Required secrets

All of these go in the CircleCI **`render-deploy`** context. Terraform reads the `TF_VAR_*` ones automatically — don't prefix them anywhere else.

| Secret | Consumer | Notes |
|---|---|---|
| `RENDER_API_KEY` | Terraform provider + `check_render_deploy` | Personal access token. |
| `RENDER_OWNER_ID` | Terraform provider | `tea-...` or `usr-...`. |
| `RENDER_SERVICE_ID` | `check_render_deploy` | Cloud storage service ID. Get it after the first `terraform apply` with `terraform output cloud_storage_service_id`. |
| `TF_VAR_gcp_service_key` | Terraform | Base64-encoded service account JSON. See [`docs/circleci-setup.md`](circleci-setup.md) for how to encode. |
| `TF_VAR_gcs_bucket_name` | Terraform | |
| `TF_VAR_google_cloud_project` | Terraform | |
| `TF_VAR_google_oauth_client_id` | Terraform | |
| `TF_VAR_google_oauth_client_secret` | Terraform | |
| `TF_VAR_gemini_api_key` | Terraform | Used by the AI integration. |
| `TF_VAR_chat_api_key` | Terraform | Used by the chat integration. |
| `TF_VAR_chat_channel_id` | Terraform | |
| `TF_VAR_grafana_admin_password` | Terraform | Used to log into Grafana after first deploy. |

`GOOGLE_OAUTH_REDIRECT_URI` has a default in `variables.tf` and doesn't need to be set unless you move to a new Render URL.

## What happens when the service URL changes

Render domains look like `cloud-storage-service-<hash>.onrender.com`. The hash is stable across redeploys of the same service, but if Terraform creates a new service (e.g., you changed `name`), the URL changes.

If that happens:

1. `terraform output service_url` gives you the new URL.
2. Update `google_oauth_redirect_uri` in your `terraform.tfvars` (or update the GCP Console OAuth config to add the new redirect) and re-apply.
3. Update the hard-coded scrape target in `monitoring/prometheus.yml`.
4. Update the `PROMETHEUS_SCRAPE_TARGET` env var in `render.yaml` and `infrastructure/main.tf`.

## Troubleshooting

**`terraform init` fails with "could not authenticate"** — `RENDER_API_KEY` isn't set in the shell. The provider accepts it as an env var; double-check with `echo $RENDER_API_KEY`.

**`terraform apply` hangs on "Waiting for deploy to complete"** — free-tier Render services sleep after 15 minutes of inactivity and can take a minute or two to spin up. The provider is waiting on purpose (`wait_for_deploy_completion = true` in `main.tf`). Give it up to 10 minutes before assuming it's stuck.

**`post_deploy_e2e` fails with "connection refused"** — check the Render dashboard for the service's health. Free-tier services sleeping is the most common cause; a Render build failure is the second. `terraform output service_url` + `curl $URL/health` in a local shell will tell you quickly.

**Grafana can't reach Prometheus** — they have to be in the same Render team and region (both set via `var.render_region`, default `oregon`). Grafana resolves `http://prometheus:9090` only when Render's internal DNS finds a service named exactly `prometheus`.

**Docker build fails with `git: command not found`** — the Dockerfile installs git explicitly because `pyproject.toml` pulls `chat-client-api` as a git dependency. If you see this error, something stripped the `apt-get install git` line.

## Related docs

- [`circleci-setup.md`](circleci-setup.md) — CircleCI project setup and GCP service key encoding.
- [`testing.md`](testing.md) — what each test suite covers and how markers work.
- `observability.md` — what each metric means and how to read the dashboard.