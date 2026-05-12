# Testing Guide

This document explains the testing strategy and how to run tests for the Cloud Storage Client project.

## Test Markers

- `unit` - Fast, isolated, mocked provider calls
- `integration` - Shared contract compliance, component interactions
- `e2e` - Full workflows against real GCS and deployed service
- `slack_integration` - Tests requiring Slack integration (real or mocked Slack SDK)
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

## Test Categories

### Unit Tests (`components/*/tests/`)

| Component | File | What it tests |
|---|---|---|
| `ai_client_api` | `test_ai_client_api.py` | Abstract interface contract, `send_message()` and `tools()` methods |
| `gemini_ai_client_impl` | `test_gemini_client.py` | Gemini client initialization, `send_message()` with tool calling, `send_message_with_metadata()` |
| `gemini_ai_client_impl` | `test_tools.py` | 6 storage tool Pydantic models validation, tool dispatch, context injection |
| `chat_client_wrapper` | `test_wrapper.py` | `ChatNotificationWrapper.notify()`, message formatters, error resilience |
| `gcp_client_impl` | `test_config.py` | Constructor config precedence, no `bucket_name` in config |
| `gcp_client_impl` | `test_error_mapping.py` | GCP exception → domain exception translation (read/write paths) |
| `gcp_client_impl` | `test_object_info.py` | `_blob_to_object_info` maps all 9 shared `ObjectInfo` fields |
| `gcp_client_impl` | `test_edge_cases.py` | Empty uploads, special characters, missing objects |
| `gcp_client_impl` | `test_storage_client.py` | Service account and ADC client construction |
| `cloud_storage_adapter` | `test_adapter_operations.py` | All 6 shared methods via mocked generated client |
| `cloud_storage_adapter` | `test_adapter_edge_cases.py` | Metadata handling, empty results, idempotent delete |
| `cloud_storage_adapter` | `test_adapter_integration.py` | Live service tests (skipped when service unavailable) |
| `cloud_storage_service` | `test_auth.py` | OAuth login, callback, opaque session tokens, dev token bypass |
| `cloud_storage_service` | `test_storage.py` | All storage endpoints with mocked storage client |
| `cloud_storage_service` | `test_ai_chat.py` | `/ai/chat` endpoint, tool calling, error handling |
| `cloud_storage_service` | `test_health.py` | Health endpoint |
| `cloud_storage_service` | `test_service_edge_cases.py` | Auth config, OAuth URL, key/prefix edge cases |
| `cloud_storage_service` | `test_slack_adapter.py` | SlackChatClient implementation, notification dispatch |

### Integration Tests (`tests/integration/`)

| Test File | What it tests |
|---|---|
| `test_di.py` | Shared `cloud_storage_api` contract compliance via `_FakeClient` |
| `test_ai_storage_flow.py` | AI client → storage client tool dispatch flow |
| `test_ai_chat_flow.py` | AI client → chat client notification flow |

Full contract compliance workflow: upload → get_info → download → list → delete → verify deleted. No real GCS credentials needed.

### E2E Tests (`tests/e2e/`)

| Test File | What it tests |
|---|---|
| `test_e2e.py` | Full GCS workflows with real credentials, all 6 shared methods, adapter/GCP interoperability, OAuth, health checks |
| `test_e2e_workflow.py` | Post-deployment E2E against live Render service (hw-3 branch only) |

Tests skip cleanly when credentials are absent, so the pipeline still passes.

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
├── mocks/                                      # Shared test fixtures
│   ├── mock_ai_client.py                       # MockAiClient for storage tests
│   └── mock_chat_client.py                     # MockChatClient for service tests
├── integration/
│   ├── conftest.py                             # Integration test fixtures
│   ├── test_di.py                              # Shared contract compliance
│   ├── test_ai_storage_flow.py                 # AI → storage tool dispatch
│   └── test_ai_chat_flow.py                    # AI → chat notification flow
└── e2e/
    ├── test_e2e.py                             # Full workflows (real GCS)
    └── test_e2e_workflow.py                    # Post-deploy (Render service)

components/
├── ai_client_api/tests/
│   └── test_ai_client_api.py                   # Interface contract
├── gemini_ai_client_impl/tests/
│   ├── test_gemini_client.py                   # Client initialization + send_message
│   └── test_tools.py                           # Tool validation + dispatch
├── chat_client_wrapper/tests/
│   └── test_wrapper.py                         # ChatNotificationWrapper + formatters
├── gcp_client_impl/tests/
│   ├── test_config.py                          # Config precedence
│   ├── test_error_mapping.py                   # Exception translation
│   ├── test_edge_cases.py                      # Boundary conditions
│   ├── test_object_info.py                     # ObjectInfo field mapping
│   └── test_storage_client.py                  # Client construction
├── cloud_storage_adapter/tests/
│   ├── test_adapter_operations.py              # All 6 shared methods (mocked)
│   ├── test_adapter_edge_cases.py              # Metadata, empty results
│   └── test_adapter_integration.py             # Live service (skipped if unavailable)
└── cloud_storage_service/tests/
    ├── conftest.py                             # Service test fixtures
    ├── test_auth.py                            # OAuth flow, session tokens
    ├── test_storage.py                         # Storage endpoints
    ├── test_ai_chat.py                         # AI chat endpoint
    ├── test_health.py                          # Health endpoint
    ├── test_service_edge_cases.py              # Auth config edge cases
    ├── test_slack_adapter.py                   # SlackChatClient
    ├── test_integration_ai_storage.py          # AI + storage integration
    ├── test_integration_ai_chat.py             # AI + chat integration
    └── test_integration_ai_to_chat.py          # AI tool call → chat notification
```

## Coverage

Coverage threshold is 85% and is enforced both in `pyproject.toml` (`fail_under = 85`) and in the CircleCI `unit_test` job (`--cov-fail-under=85`).

Run locally to verify:

```bash
uv run pytest --cov --cov-fail-under=85
```

The workspace maintains 85%+ coverage with 250+ tests.

See [circleci-setup.md](circleci-setup.md) for CI credential configuration.
