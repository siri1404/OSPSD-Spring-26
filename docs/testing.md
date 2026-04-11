# Testing Guide

This document explains the testing strategy and how to run tests for the Cloud Storage Client project.

## Test Markers

- `unit` - Fast, isolated, mocked provider calls
- `integration` - Shared contract compliance, component interactions
- `e2e` - Full workflows against real GCS and deployed service
- `circleci` - Runnable in CI without local credential files
- `local_credentials` - Requires local `GOOGLE_APPLICATION_CREDENTIALS` file

## Running Tests

### All Unit Tests (Fast, No Credentials)
```bash
uv run pytest components/ --cov=components --cov-fail-under=85
```

### Integration Tests (No Credentials)
```bash
uv run pytest tests/integration/ -v --no-cov
```

### E2E Tests
```bash
uv run pytest tests/e2e/ -v --no-cov
```

### Full Suite
```bash
uv run pytest --cov --cov-fail-under=85
```

## Test Categories

### Unit Tests (`components/*/tests/`)

| Component | File | What it tests |
|---|---|---|
| `gcp_client_impl` | `test_config.py` | Constructor config precedence, no `bucket_name` in config |
| `gcp_client_impl` | `test_credentials.py` | OAuth token priority, service key parsing, ADC fallback |
| `gcp_client_impl` | `test_object_info.py` | `_blob_to_object_info` maps all 9 shared `ObjectInfo` fields |
| `gcp_client_impl` | `test_operations.py` | All 6 shared methods: `upload_file`, `upload_obj`, `download_file`, `list_files`, `delete_file`, `get_file_info` |
| `gcp_client_impl` | `test_edge_cases.py` | Empty uploads, special characters, missing objects |
| `gcp_client_impl` | `test_storage_client.py` | Service account and ADC client construction |
| `cloud_storage_adapter` | `test_adapter_operations.py` | All 6 shared methods via mocked generated client |
| `cloud_storage_adapter` | `test_adapter_edge_cases.py` | Metadata handling, empty results, idempotent delete |
| `cloud_storage_adapter` | `test_adapter_integration.py` | Live service tests (skipped when service unavailable) |
| `cloud_storage_service` | `test_auth.py` | OAuth login, callback, opaque session tokens, dev token bypass |
| `cloud_storage_service` | `test_storage.py` | All endpoints with mocked storage client |
| `cloud_storage_service` | `test_health.py` | Health endpoint |
| `cloud_storage_service` | `test_service_edge_cases.py` | Auth config, OAuth URL, key/prefix edge cases |

### Integration Tests (`tests/integration/`)

- Verifies shared `cloud_storage_api` has no DI module
- Validates `_FakeClient` implements all 6 shared methods correctly
- Full contract compliance: upload -> get_info -> download -> list -> delete -> verify deleted
- No real GCS credentials needed

### E2E Tests (`tests/e2e/`)

- Full GCS workflows with real credentials (skipped when absent)
- All 6 shared methods tested end-to-end with `container` parameter
- Adapter and GCP implementation interoperability test
- HTTP round-trip via raw `httpx`
- Generated client round-trip
- OAuth login flow
- Deployed service health check (`/health` and `/openapi.json`)
- `main.py` subprocess execution

## Authentication for E2E Tests

Three modes are supported:

| Mode | Env Vars Needed |
|---|---|
| Service account JSON | `GCP_SERVICE_KEY`, `GCS_BUCKET_NAME`, `GOOGLE_CLOUD_PROJECT` |
| Service account file | `GOOGLE_APPLICATION_CREDENTIALS`, `GCS_BUCKET_NAME` |
| ADC (`gcloud` login) | `GCS_BUCKET_NAME` |

E2E tests skip cleanly when credentials are absent, so the pipeline still passes.

## Test Structure

```text
tests/
├── integration/
│   └── test_di.py                          # Shared contract compliance
└── e2e/
    └── test_e2e.py                         # Full workflows

components/
├── gcp_client_impl/tests/
│   ├── test_config.py                      # Config precedence
│   ├── test_credentials.py                 # Auth modes
│   ├── test_edge_cases.py                  # Boundary conditions
│   ├── test_object_info.py                 # ObjectInfo field mapping
│   ├── test_operations.py                  # All 6 shared methods
│   └── test_storage_client.py              # Client construction
├── cloud_storage_adapter/tests/
│   ├── test_adapter_operations.py          # All 6 shared methods (mocked)
│   ├── test_adapter_edge_cases.py          # Metadata, empty results
│   └── test_adapter_integration.py         # Live service (skipped if unavailable)
└── cloud_storage_service/tests/
    ├── test_auth.py                        # OAuth flow, session tokens
    ├── test_storage.py                     # All endpoints
    ├── test_health.py                      # Health endpoint
    └── test_service_edge_cases.py          # Auth config edge cases
```

## Coverage

Coverage threshold is 85% and is enforced in CI via `--cov-fail-under=85`.

Strictly verified in this workspace by running:

```bash
uv run pytest --cov --cov-fail-under=85
```

Result from that run:

- `156 passed, 34 skipped`
- `Total coverage: 91.29%`

See [circleci-setup.md](circleci-setup.md) for CI credential configuration.
