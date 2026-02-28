# CircleCI Setup

This document explains how to configure CircleCI for the Cloud Storage Client project with GCP.

## Overview

The CI/CD pipeline includes:

- **Build**: Environment setup with `uv`
- **Lint**: Code quality checks with `ruff`
- **Type Check**: Static type validation with `mypy`
- **Unit Tests**: Fast component tests
- **Integration Tests**: Tests that verify component interactions without real GCP (all branches)
- **E2E Tests**: Real GCS integration tests (protected branches only)

## Quick Setup

### 1. Connect Repository

1. Log in to [CircleCI](https://circleci.com/)
2. Click **Projects** and select your repository
3. CircleCI auto-detects `.circleci/config.yml` in the repo
4. Click **Set Up Project**

### 2. Environment Variables

Add these variables in CircleCI **Project Settings** → **Environment Variables**:

| Variable | Description |
|----------|-------------|
| `GCP_SERVICE_KEY` | Base64-encoded GCP service account JSON key |
| `GCS_BUCKET_NAME` | Name of your test GCS bucket (e.g., `my-test-bucket`) |
| `GOOGLE_CLOUD_PROJECT` | Your GCP project ID |

**To get `GCP_SERVICE_KEY`:**
1. Download your service account JSON from GCP Console
2. Encode it: `base64 -i key.json | tr -d '\n'` (Linux/Mac) or use PowerShell on Windows
3. Copy the output into CircleCI

## Workflows

### All Branches

```
build → lint + type_check + unit_tests → integration_tests
```

### Protected Branches (main, develop)

```
build → lint + type_check + unit_tests → integration_tests → e2e_tests
```

The difference: E2E tests run only on `main` and `develop` because they need real GCP credentials.

## Local Development

Run the same checks locally before pushing:

```bash
# Setup
uv sync

# Quality checks
uv run ruff check .              # Lint
uv run mypy src tests            # Type check

# Tests
uv run pytest src/ -v                    # Unit tests
uv run pytest tests/integration/ -v      # Integration tests (no credentials needed)
uv run pytest tests/e2e/ -v              # E2E tests (needs GCP credentials)
```

## Troubleshooting

**"GCP_SERVICE_KEY not set"**: Verify the environment variable is added to CircleCI and is a valid base64 string

**"Permission denied" in E2E tests**: Ensure your service account has `Storage Object Admin` role in GCP

**"Cannot find bucket"**: Double-check `GCS_BUCKET_NAME` matches your actual bucket name in GCP

**Tests fail locally but pass in CI**: Make sure you have the credentials file set up locally (same as CircleCI)

## Security Notes

- Never commit credentials or service account keys to Git
- E2E tests only run on protected branches (`main`, `develop`)
- CircleCI encrypts environment variables automatically
- Service account keys should have minimal required permissions
