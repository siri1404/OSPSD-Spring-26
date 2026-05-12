# CircleCI Setup

This document explains how to configure CircleCI for the Cloud Storage Client project with GCP, AI, and deployment integration.

## Overview

The pipeline is defined in `.circleci/config.yml` and runs on every branch except `main`. It has nine jobs:

| Job | What it does |
|---|---|
| `build` | Installs `uv`, creates the virtualenv, installs all packages, persists the workspace |
| `lint` | `ruff check .` + `ruff format --check .` |
| `typecheck` | `mypy .` (strict) |
| `unit_test` | `pytest components/` with coverage — must reach 85% |
| `integration_test` | `pytest tests/integration/` — no credentials needed (AI/chat/storage mocked at DI boundary) |
| `mkdocs_build` | `mkdocs build --strict` — validates documentation builds cleanly |
| `terraform_plan` | `terraform init`, `fmt -check`, `validate`, `plan` — IaC validation on every push |
| `check_render_deploy` | Polls Render API to verify deployment succeeded (hw-3 branch only) |
| `post_deploy_e2e` | `pytest tests/e2e/test_e2e_workflow.py` against the live deployed service (hw-3 branch only) |

Note: `terraform_apply` is currently disabled due to a Render free-tier provider limitation. See [deployment.md](deployment.md) for details.

## Pipeline

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

`lint`, `typecheck`, `unit_test`, and `mkdocs_build` all depend on `build` and run in parallel. `integration_test` requires `unit_test`. `terraform_plan` requires `lint`.

On `hw-3` only: `check_render_deploy` runs after `build` + `integration_test`, polls the Render API until the deploy is live, then `post_deploy_e2e` runs E2E tests against the deployed service.

## Quick Setup

### 1. Connect Repository

1. Log in to [CircleCI](https://circleci.com/)
2. Click **Projects** and select your repository
3. CircleCI auto-detects `.circleci/config.yml` in the repo
4. Click **Set Up Project**

### 2. CircleCI Context: render-deploy

Create a context called `render-deploy` in CircleCI (Organization Settings → Contexts) and add these secrets:

| Variable | Description | Consumer |
|---|---|---|
| `RENDER_API_KEY` | Render Personal Access Token | Terraform provider + `check_render_deploy` |
| `RENDER_OWNER_ID` | Render team/user ID (`tea-...` or `usr-...`) | Terraform provider |
| `RENDER_SERVICE_ID` | Cloud storage Render service ID | `check_render_deploy` |
| `RENDER_SERVICE_URL` | Public URL of deployed service | `post_deploy_e2e` |
| `DEV_AUTH_TOKEN` | Bearer token for E2E test auth | `post_deploy_e2e` |
| `GCS_BUCKET_NAME` | GCS bucket for E2E storage ops | `post_deploy_e2e` |
| `TF_VAR_GCP_SERVICE_KEY` | Base64-encoded GCP service account JSON | Terraform |
| `TF_VAR_GCS_BUCKET_NAME` | GCS bucket name | Terraform |
| `TF_VAR_GOOGLE_CLOUD_PROJECT` | GCP project ID | Terraform |
| `TF_VAR_GOOGLE_OAUTH_CLIENT_ID` | OAuth client ID | Terraform |
| `TF_VAR_GOOGLE_OAUTH_CLIENT_SECRET` | OAuth client secret | Terraform |
| `TF_VAR_GEMINI_API_KEY` | Google Gemini API key | Terraform |
| `TF_VAR_SLACK_BOT_TOKEN` | Slack bot token for notifications | Terraform |
| `TF_VAR_CHAT_CHANNEL_ID` | Slack channel ID | Terraform |
| `TF_VAR_GRAFANA_ADMIN_PASSWORD` | Grafana admin password | Terraform |

### 3. GCP Service Key Encoding

```bash
# Linux / macOS
base64 -i service-account-key.json | tr -d '\n'

# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("service-account-key.json"))
```

Paste the output as the `TF_VAR_GCP_SERVICE_KEY` value in the `render-deploy` context.

## Local Development

Install dependencies, then run the same commands CircleCI uses:

```bash
uv sync --all-packages --group dev
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest components/ --cov=components/ --cov-fail-under=85
uv run pytest tests/integration/ -v --no-cov
uv run pytest tests/e2e/ -v --no-cov
uv run mkdocs build --strict
```

See [testing.md](testing.md) for the full list of test commands and marker shortcuts.

## Troubleshooting

**"GCS_BUCKET_NAME not set" or e2e tests skip** — The structural e2e tests still pass; add the env vars to the `render-deploy` context to enable the full workflow tests.

**"Permission denied" in E2E tests** — Ensure the service account has the `Storage Object Admin` role on the test bucket.

**"Cannot find bucket"** — Double-check `GCS_BUCKET_NAME` matches the actual bucket name in GCP Console.

**`ruff format --check .` fails** — Run `uv run ruff format .` locally, commit the result.

**`mypy .` fails** — Mypy runs in strict mode. Fix all reported type errors before pushing.

**Coverage below 85%** — `pytest components/ --cov=components/ --cov-report=term-missing` shows uncovered lines.

**`terraform_apply` fails with "maintenance_mode"** — Known Render free-tier limitation. See [deployment.md](deployment.md).

## Security Notes

- Never commit service account keys to Git
- CircleCI encrypts environment variables at rest
- All secrets go in the `render-deploy` context, not in project-level env vars
- Service account keys should have only `Storage Object Admin` on the test bucket — no broader project permissions
