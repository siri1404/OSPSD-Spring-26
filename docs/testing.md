# Testing Guide

This document explains the testing strategy and how to run different types of tests for the Cloud Storage Client with GCP implementation.

## Test Markers

The project uses pytest markers to categorize tests based on their requirements and suitable environments:

### Core Test Types
- `unit`: Fast, isolated tests that don't require external dependencies
- `integration`: Tests that verify component interactions
- `e2e`: End-to-end tests that verify the complete application workflow with real GCS

### Environment-Specific Markers
- `circleci`: Tests that can run in CI/CD environments using only environment variables
- `local_credentials`: Tests that require a local service account key file or `GOOGLE_APPLICATION_CREDENTIALS`

## Running Tests

### All Unit Tests (Fast)
```bash
uv run pytest components/ --cov=components --cov-fail-under=85
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
uv run pytest tests/integration/
```

### E2E Tests
```bash
uv run pytest tests/e2e/
```

### Exclude Credential-Dependent Tests
```bash
uv run pytest -m "not local_credentials"
```

## Test Categories by Environment

### Unit Tests (`components/`)
All unit tests live inside each component and use `@pytest.mark.unit`:

| File | What it tests |
|---|---|
| `cloud_storage_client_api/tests/test_client_api.py` | `ObjectInfo` dataclass and `CloudStorageClient` abstract base |
| `cloud_storage_client_api/tests/test_get_client.py` | DI registry — register, get, override, unregister |
| `gcp_client_impl/tests/test_config.py` | `GCPCloudStorageClient` construction and config loading |
| `gcp_client_impl/tests/test_credentials.py` | `_build_credentials()` — service account key parsing |
| `gcp_client_impl/tests/test_object_info.py` | `_blob_to_object_info()` — GCS blob to `ObjectInfo` mapping |
| `gcp_client_impl/tests/test_operations.py` | `upload_bytes`, `upload_file`, `download_bytes`, `list`, `delete`, `head` |
| `gcp_client_impl/tests/test_registration.py` | Auto DI registration when `gcp_client_impl` is imported |
| `gcp_client_impl/tests/test_storage_client.py` | `_build_storage_client()` — auth mode selection |

### Integration Tests (`tests/integration/`)
Tests marked with `@pytest.mark.integration` verify component interactions:
- **Requirements**: No real GCS credentials needed — uses fake clients
- **What they test**:
  - DI registry isolation between tests
  - Thread safety of concurrent `get_client()` calls
  - Named provider registration (`default`, `gcp`)
  - `override_get_client()` context manager behaviour

Example command:
```bash
uv run pytest tests/integration/ -v --no-cov
```

### E2E Tests (`tests/e2e/`)
Tests marked with `@pytest.mark.e2e` run against real GCS infrastructure.
They are further split by credential mode:

#### `@pytest.mark.circleci`
- **Requirements**: `GCS_BUCKET_NAME`, `GOOGLE_CLOUD_PROJECT`, and `GCP_SERVICE_KEY` environment variables
- **What they test**:
  - Full upload / download / delete / list / head workflows against real GCS
  - `main.py` script execution
  - Client initialization from environment variables

Example CircleCI command:
```bash
uv run pytest tests/e2e/ -m circleci --tb=short
```

#### `@pytest.mark.local_credentials`
- **Requirements**: `GOOGLE_APPLICATION_CREDENTIALS` pointing to a local service account key file
- **What they test**:
  - Full workflow with file-based credentials
  - `upload_file()` from a real local path
  - `main.py` integration with local credentials

## Authentication Modes

The GCP client supports three authentication modes:

### File-Based (`GOOGLE_APPLICATION_CREDENTIALS`)
- Points to a downloaded service account JSON key file
- Used for local development
- **Not suitable for CI without securely mounted files**

### Environment Variable (`GCP_SERVICE_KEY`)
- Raw JSON or base64-encoded service account key stored as an env var
- **Required for CircleCI and most CI/CD environments**
- Never requires a file on disk

### Application Default Credentials
- No configuration needed — GCP SDK picks up credentials automatically
- Works with `gcloud auth application-default login` locally
- Works with workload identity in GKE/Cloud Run

## Running Without Credentials

Unit and integration tests always pass — no env vars needed.  E2E tests skip cleanly when `GCP_SERVICE_KEY` / `GCS_BUCKET_NAME` / `GOOGLE_CLOUD_PROJECT` are absent.  See [circleci-setup.md](circleci-setup.md) for how to configure credentials in CI.

---

### Tests Structure

```
tests/
├── integration/          # Cross-component interaction
│   └── test_di.py       # DI registration, provider switching, thread safety
└── e2e/                 # Real GCS workflows
    └── test_e2e.py      # Syntax, imports, full CRUD operations

components/
├── cloud_storage_client_api/tests/
│   ├── test_client_api.py       # ObjectInfo immutability, ABC contract
│   └── test_get_client.py       # DI factory behavior
└── gcp_client_impl/tests/
    ├── test_config.py           # Config precedence, env var fallbacks
    ├── test_credentials.py      # Auth parsing, JSON validation
    ├── test_storage_client.py   # Service account and ADC modes
    ├── test_operations.py       # Upload, download, list, delete, head
    ├── test_object_info.py      # ObjectInfo field validation
    └── test_registration.py     # DI auto-registration on import
```