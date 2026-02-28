# Testing Guide

This document explains the testing strategy and how to run different types of tests for the Cloud Storage Client with GCP implementation.

## Test Markers

The project uses pytest markers to categorize tests based on their requirements and suitable environments:

### Core Test Types
- `unit`: Fast, isolated tests that don't require external dependencies
- `integration`: Tests that verify component interactions
- `e2e`: End-to-end tests that verify the complete application workflow with real GCS

### Environment-Specific Markers
- `circleci`: Tests that can run in CI/CD environments without local credential files
- `local_credentials`: Tests that require local `credentials.json` or service account key files

## Running Tests

### All Unit Tests (Fast)
```bash
uv run pytest src/ --cov=src --cov-fail-under=80
```

### CircleCI-Compatible Tests Only
```bash
uv run pytest -m circleci
```

### Local Tests Only (Requires Credentials)
```bash
uv run pytest -m local_credentials
```

### Integration Tests
```bash
uv run pytest -m integration
```

### E2E Tests
```bash
uv run pytest -m e2e
```

### Exclude Credential-Dependent Tests
```bash
uv run pytest -m "not local_credentials"
```

## Test Categories by Environment

### CircleCI/CI Environment
Tests marked with `@pytest.mark.circleci` can run in CI environments:
- **Requirements**: Only environment variables (`GOOGLE_APPLICATION_CREDENTIALS`, `GCS_BUCKET_NAME`, `GOOGLE_CLOUD_PROJECT`)
- **What they test**:
  - Code syntax and imports
  - Factory function dependency injection
  - GCP client initialization logic
  - Application structure integrity
  - Non-interactive authentication setup

Example CircleCI command:
```bash
uv run pytest -m circleci --tb=short
```

### Local Development
Tests marked with `@pytest.mark.local_credentials` require local files:
- **Requirements**: `credentials.json` or service account key JSON file
- **What they test**:
  - Real Google Cloud Storage connectivity
  - File upload/download operations
  - Object listing and metadata retrieval
  - Full end-to-end storage workflows

## Environment Variables for CI

Set these environment variables in your CI environment:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
export GCS_BUCKET_NAME="your-test-bucket"
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
```

## Authentication Modes

The GCP Cloud Storage client supports two authentication modes:

### Interactive Mode (Local Development)
- Uses downloaded service account JSON key file
- Requires `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- Used for local development and testing
- **Not suitable for CI/CD without proper setup**

### Non-Interactive Mode (CI/CD)
- Uses environment variables for credentials
- Base64-encoded service account key in `GCP_SERVICE_KEY`
- Never requires user interaction
- **Required for CI/CD environments**
- Fails fast with clear error messages when credentials are missing

## Test Examples

### Running Tests Without Network Calls
```bash
# Only run tests that don't make real API calls
uv run pytest -m "unit or (circleci and not local_credentials)"
```

### Running Full Local Test Suite
```bash
# Run all tests including those requiring real GCS credentials
uv run pytest
```

### Debugging GCS Issues
```bash
# Run only storage-related tests
uv run pytest -k "upload or download or delete" -v
```

## Expected Behavior in Different Environments

### Local Development (with GCS credentials)
- All tests should pass
- Real GCS API calls succeed
- Can upload/download/delete objects

### Local Development (without credentials)
- Unit tests pass
- Integration/E2E tests skip or fail with clear messages
- No hanging or infinite waits

### CircleCI (with environment variables)
- Tests marked `circleci` pass
- Tests marked `local_credentials` are skipped
- No interactive authentication attempts
- Fast execution (no timeouts)

### CircleCI (without environment variables)
- Tests marked `circleci` skip with clear messages
- No test failures due to missing credentials
- Fast execution
