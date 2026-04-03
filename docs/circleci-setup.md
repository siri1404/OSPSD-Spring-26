# CircleCI Setup

This document explains how to configure CircleCI for the Cloud Storage Client project with GCP.

## Overview

The pipeline is defined in `.circleci/config.yml` and runs on every branch except `main`.  It has six jobs:

| Job | What it does |
|---|---|
| `build` | Installs `uv`, creates the virtualenv, installs all packages, persists the workspace |
| `lint` | `ruff check .` + `ruff format --check .` |
| `typecheck` | `mypy components/` (strict) |
| `unit_test` | `pytest components/` with coverage — must reach 85 % |
| `integration_test` | `pytest tests/integration/` — no credentials needed |
| `e2e_test` | `pytest tests/e2e/` — skips credential-dependent tests when env vars are absent |

## Pipeline

All jobs run sequentially on every non-`main` branch:

```
build → lint ─┐
              ├─ (parallel) → unit_test → integration_test → e2e_test
typecheck ────┘
```

`lint` and `typecheck` both depend on `build` and run in parallel with each other. `unit_test` also depends on `build`.  `integration_test` requires `unit_test`.  `e2e_test` requires `integration_test`.

## Quick Setup

### 1. Connect Repository

1. Log in to [CircleCI](https://circleci.com/)
2. Click **Projects** and select your repository
3. CircleCI auto-detects `.circleci/config.yml` in the repo
4. Click **Set Up Project**

### 2. Environment Variables

Add these in CircleCI **Project Settings** → **Environment Variables**:

| Variable | Description | Required for |
|---|---|---|
| `GCP_SERVICE_KEY` | Base64-encoded GCP service account JSON key | E2E credential tests |
| `GCS_BUCKET_NAME` | Your test GCS bucket name | E2E credential tests |
| `GOOGLE_CLOUD_PROJECT` | Your GCP project ID | E2E credential tests |

E2E tests that need credentials **skip** cleanly when these are not set — the pipeline still passes without them.

**To get `GCP_SERVICE_KEY`:**

```bash
# Linux / macOS
base64 -i service-account-key.json | tr -d '\n'

# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("service-account-key.json"))
```

Paste the output as the `GCP_SERVICE_KEY` value in CircleCI.

## Local Development

Install dependencies, then run the same commands CircleCI uses:

```bash
uv sync --all-packages --group dev
uv run ruff check . && uv run ruff format --check .
uv run mypy components/
uv run pytest components/ --cov=components/ --cov-fail-under=85
uv run pytest tests/integration/ -v --no-cov
uv run pytest tests/e2e/ -v --no-cov
```

See [testing.md](testing.md) for the full list of test commands and marker shortcuts.

## Troubleshooting

**"GCP_SERVICE_KEY not set" or e2e tests skip** — The structural e2e tests still pass; add the three env vars to CircleCI to enable the full workflow tests.

**"Permission denied" in E2E tests** — Ensure the service account has the `Storage Object Admin` role on the test bucket.

**"Cannot find bucket"** — Double-check `GCS_BUCKET_NAME` matches the actual bucket name in GCP Console.

**`ruff format --check .` fails** — Run `uv run ruff format .` locally, commit the result.

**`mypy components/` fails** — Mypy runs in strict mode. Fix all reported type errors before pushing.

**Coverage below 85 %** — `pytest components/ --cov=components/ --cov-report=term-missing` shows uncovered lines.

## Security Notes

- Never commit service account keys to Git
- CircleCI encrypts environment variables at rest
- Service account keys should have only `Storage Object Admin` on the test bucket — no broader project permissions
