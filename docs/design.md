# Design Document: Cloud Storage Client Architecture

## Overview

This project implements a provider-agnostic cloud storage system that aligns with the shared `cloud_storage_api` contract (`v1.0.0`) defined by the Cloud Storage vertical (Teams 2, 6, 10). The architecture separates the shared interface from provider-specific implementations, enabling seamless provider switching. HW3 extends the system with AI-powered tool calling (Gemini), cross-vertical chat notifications (Slack via Team 9), Infrastructure as Code (Terraform), and Prometheus/Grafana observability.

## Design Principles

### 1. Shared Contract

The interface is maintained in a cross-team repository and consumed as a git dependency:

```toml
cloud-storage-api = { git = "https://github.com/2SpaceMasterRace/ospsd-cloud-storage.git", tag = "v1.0.0" }
```

The shared `CloudStorageClient` ABC defines 6 methods. All teams implement the same contract: GCP (Team 6), AWS S3 (Teams 2, 10).

### 2. Provider Agnosticism

Consumer code depends only on the shared interface:

```python
from cloud_storage_api import CloudStorageClient, ObjectInfo


def process_files(client: CloudStorageClient, container: str) -> None:
    objects = client.list_files(container=container, prefix="reports/")
    for obj in objects:
        print(f"{obj.object_name}: {obj.size_bytes} bytes")
```

Switching between GCP, AWS, or the HTTP adapter requires changing only which implementation is instantiated. Consumer code stays identical.

### 3. Container Per Method

The bucket/container is passed on every method call rather than configured at construction. This keeps the interface stateless and allows a single client instance to operate across multiple containers.

### 4. No DI in Shared Package

The shared `cloud_storage_api` intentionally has no dependency injection module. Each team wires implementations in their own project. This keeps the contract minimal and avoids cross-team coupling on DI patterns.

## Component Architecture

### External: `cloud_storage_api` (Shared Git Dependency)

Defines the contract all implementations follow:

- `CloudStorageClient` ABC with 6 methods
- `ObjectInfo` frozen dataclass (9 fields: object_name, version_id, data_type, integrity, encryption, storage_tier, size_bytes, updated_at, metadata)
- `DeleteResult` TypedDict (`deleted`, `version_id`, `request_charged`)
- 8 typed domain exceptions inheriting from Python built-ins

### External: `chat_client_api` (Cross-Vertical Git Dependency — Team 9)

The shared chat interface consumed for cross-vertical integration:

```toml
chat-client-api = { git = "https://github.com/HarshithKoriRaj/Shared-API.git", rev = "ebb37e1..." }
```

- `ChatClient` ABC with `send_message`, `get_messages`, `get_channels`, `delete_message`
- `Message` and `Channel` dataclasses
- Domain exceptions: `ChannelNotFoundError`, `MessageNotFoundError`, `MessageDeleteError`

### Component 1: `ai_client_api` (AI Interface)

Abstract interface for AI client implementations:

- `AiClientApi` ABC with `send_message(prompt, context) -> str` and `tools() -> list[ToolDefinition]`
- Framework-free — zero dependencies, no provider SDK leakage
- Shared models: `AIResponse` (text + action_taken + tool_calls + tool_args), `ToolDefinition`, `ToolParameter`
- Design: slim mandatory contract (`send_message -> str`) + opt-in rich contract (`send_message_with_metadata -> AIResponse`) discovered via `getattr()` at runtime

### Component 2: `gemini_ai_client_impl` (AI Implementation)

Concrete AI client using Google's Gemini 2.5 Flash:

- Implements `AiClientApi` with a bounded tool-call loop (max 10 iterations)
- 6 storage tools: `list_files`, `get_file_info`, `delete_file`, `upload_file`, `download_file`, `summarize_file`
- Tool arguments validated via Pydantic models (`ListFilesArgs`, `GetFileInfoArgs`, `DeleteFileArgs`, `UploadFileArgs`, `DownloadFileArgs`, `SummarizeFileArgs`)
- Context injection: if the model omits container from tool args, the client injects it from the request context
- PDF support: `summarize_file` base64-encodes PDF bytes and sends them as a Gemini Part.from_bytes
- `ToolLoopExhaustedError` raised when the model exhausts iterations without producing a final response
- Credentials: `GEMINI_API_KEY` from environment variable

### Component 3: `chat_client_wrapper` (Notification Wrapper)

Cross-vertical notification layer on top of Team 9's `ChatClient`:

- `ChatNotificationWrapper.notify(message)` — sends to a configured Slack channel
- `NotificationMessages` — static formatters for upload, delete, AI action, and error events
- Error resilience: `safe_notify()` in main.py catches and logs transport failures without disrupting storage operations
- Pluggable: accepts any `ChatClient` implementation (Slack, Discord, etc.)

### Component 4: `gcp_client_impl` (Storage Implementation)

Google Cloud Storage implementation of `CloudStorageClient`.

- Every method takes `container` as first argument
- `_validate_container` and `_validate_object_name` on every call
- Separate error mappers: `_raise_read_error` (404 = object not found) and `_raise_write_error` (404 = container not found)
- `_blob_to_object_info` maps GCS blob to shared `ObjectInfo` (all 9 fields)
- `list_files` sorts results by `object_name`
- `get_file_info` raises `ObjectNotFoundError` (not returns `None`)

Authentication resolution order:

1. `oauth_token` / `GCP_OAUTH_TOKEN`
2. `credentials_path` / `GOOGLE_APPLICATION_CREDENTIALS`
3. `service_key` / `GCP_SERVICE_KEY` (raw JSON or base64)
4. Application Default Credentials

### Component 5: `cloud_storage_adapter` (HTTP Adapter)

HTTP adapter implementing `CloudStorageClient` via the generated OpenAPI client.

- All 6 methods proxy to the FastAPI service
- `upload_obj` reads `BinaryIO`, sends raw bytes
- `download_file` writes response content to local file
- Maps HTTP status codes to shared exceptions (401/403 → `AuthenticationError`, 404 → `ObjectNotFoundError` or `ContainerNotFoundError`)
- `list_files` sorts results by `object_name`

### Component 6: `cloud_storage_service` (FastAPI Service)

FastAPI microservice with 12 endpoints:

**Storage:**
- `/upload` (POST) — upload file or binary object
- `/download/{key}` (GET) — download with Content-Disposition header
- `/list` (GET) — list by prefix
- `/delete/{key}` (DELETE) — delete object
- `/head/{key}` (GET) — get metadata

**AI:**
- `/ai/chat` (POST) — natural language → Gemini tool dispatch → structured response

**Auth:**
- `/auth/login` (POST), `/auth/callback` (GET), `/auth/logout` (POST)

**Monitoring:**
- `/metrics` (GET) — Prometheus format
- `/health` (GET), `/` (GET)

Features:
- All storage endpoints use the shared `CloudStorageClient` interface via DI
- AI client injected via `Depends(get_ai_client)`
- Chat notifications injected via `Depends(get_chat_notification)`
- Pydantic response models with `extra="forbid"` to catch contract drift
- OAuth 2.0 with opaque session tokens (provider token stays server-side)

### Component 7: `cloud_storage_service_api_client` (Generated Client)

Auto-generated from `openapi.json` via openapi-python-client. Used internally by the adapter. Not hand-edited (critical patches applied via `scripts/apply_generator_patches.py`).

## AI Integration

### Tool Dispatch Flow

```
POST /ai/chat (prompt, X-Container header)
  - GeminiAiClient._run_send_message()
    - Gemini API returns function_call(name, args)
    - _dispatch_tool(name, args)
      - dispatch_tool_call(name, args, storage_client)
        - Pydantic validation (ListFilesArgs, DeleteFileArgs, etc.)
        - _list_files() / _delete_file() / _upload_file() / ...
          - CloudStorageClient.list_files() / .delete_file() / ...
            - GCPCloudStorageClient (real GCS operations)
    - Tool result → Gemini API (next turn)
  - Final text response
    - ai_tool_calls_total counter incremented (telemetry)
    - ChatNotificationWrapper.notify() (cross-vertical notification)
```

### AI Design Decisions

- **Slim interface contract:** `send_message() -> str` is the ABC requirement. `send_message_with_metadata() -> AIResponse` is an opt-in extension discovered via `getattr()` at runtime. This allows AI providers that don't support tool calling to still satisfy the interface.
- **Storage client injection:** The AI client takes `CloudStorageClient` at construction time. For multi-vertical tool dispatch, a future refactor would accept a `tool_dispatcher: Callable` instead (see Team 5's pattern).
- **Recoverable vs non-recoverable errors:** Tool functions catch `ObjectNotFoundError`, `ContainerNotFoundError`, `LocalFileAccessError` and return "Error: ..." strings so the model can self-correct. `AuthenticationError`, `StorageBackendError`, etc. propagate as `RuntimeError` to the caller.
- **Bounded loop:** `ToolLoopExhaustedError` after 10 iterations prevents runaway tool calls. The `/ai/chat` handler maps this to HTTP 504.

## Cross-Vertical Integration

### Integration Choice

We integrated with Team 9's Chat vertical (Slack). The shared `chat_client_api` provides a `ChatClient` ABC that abstracts platform differences (Slack, Discord, Telegram).

### Integration Architecture

```
cloud_storage_service (FastAPI)
    - safe_notify() — fire-and-forget, swallows errors
        - ChatNotificationWrapper.notify(message)
            - SlackChatClient.send_message(channel_id, text)
                - slack_sdk.WebClient.chat_postMessage()
                    - Slack API
```

### DI Swappability

`ChatNotificationWrapper` accepts any `ChatClient` implementation at its constructor — the wrapper never imports the Slack SDK directly. Swapping Slack → Discord requires changing one import in main.py's `_get_cached_chat_client()`. The wrapper, notification formatters, and all tests are provider-agnostic.

### Why Slack Adapter is Vendored

Team 9's Slack implementation is a uv workspace member in their repo and not independently pip-installable via git URL. We vendored `slack_adapter.py` while depending on their shared `chat_client_api` ABC as a proper git dependency.

## Observability Strategy

### Metrics

Three Prometheus metrics emitted by the telemetry middleware at `/metrics`:

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `storage_service_requests_total` | Counter | endpoint, method, status_code, error_class | Request count with domain/infra error classification |
| `storage_service_request_latency_seconds` | Histogram | endpoint, method | Latency distribution (p50/p95/p99) |
| `storage_service_ai_tool_calls_total` | Counter | tool_name, status | AI tool dispatch tracking |

### Error Classification

The `error_class` label on `requests_total` distinguishes:

- `success` — status < 400
- `domain` — 4xx with a matched route (e.g., `ObjectNotFoundError` → 404)
- `infra` — 5xx or unmatched route

### Cardinality Control

`_get_route_template()` returns the FastAPI route template (e.g., `/download/{key:path}`) instead of the raw URL path. This prevents high-cardinality label explosion from unique object keys.

### Dashboard

Grafana dashboard with 7 panels, auto-provisioned via Docker:

- Request Latency (p50, p95, p99) — timeseries
- Total Requests Over Time — timeseries by endpoint/method
- Error Rate (4xx vs 5xx) — timeseries with color coding
- AI Tool Call Success/Failure Rates — timeseries by tool_name
- Overall Success Rate (2xx) — gauge with SLO thresholds
- AI Tool Success Rate — gauge
- Requests by Endpoint (Last Hour) — pie chart

### Infrastructure

- Prometheus deployed to Render, scrapes the FastAPI `/metrics` endpoint via public HTTPS URL every 10s
- Grafana deployed to Render, connects to Prometheus via public URL, dashboard auto-provisioned at startup
- Both managed via Terraform in `infrastructure/main.tf`

## Error Handling

### Exception Translation at Three Boundaries

**GCP SDK → Domain (gcp_client_impl):**

| GCP Exception | Read Path | Write Path |
|---|---|---|
| Forbidden | `AuthenticationError` | `ContainerNotFoundError` |
| Unauthorized | `AuthenticationError` | `AuthenticationError` |
| NotFound | `ObjectNotFoundError` or `ContainerNotFoundError` | `ContainerNotFoundError` |
| BadRequest | `InvalidObjectNameError` or `InvalidContainerError` | `InvalidObjectNameError` or `InvalidContainerError` |
| Other | `StorageBackendError` | `StorageBackendError` |

**Domain → HTTP (cloud_storage_service):**

| Shared Exception | HTTP Status |
|---|---|
| `AuthenticationError` | 401 |
| `ContainerNotFoundError` | 404 |
| `ObjectNotFoundError` | 404 |
| `InvalidContainerError` | 422 |
| `InvalidObjectNameError` | 422 |
| `InvalidFileObjectError` | 422 |
| `LocalFileAccessError` | 500 |
| `StorageBackendError` | 500 (storage), 502 (AI path) |
| `ToolLoopExhaustedError` | 504 |
| `RuntimeError` (AI) | 500 |

**HTTP → Domain (cloud_storage_adapter):**

| HTTP Status | Shared Exception |
|---|---|
| 401, 403 | `AuthenticationError` |
| 404 (container) | `ContainerNotFoundError` |
| 404 (object) | `ObjectNotFoundError` |
| 422 (key/object_name) | `InvalidObjectNameError` |
| 422 (container) | `InvalidContainerError` |
| Other | `StorageBackendError` |

## Testing Strategy

| Type | Location | What it tests | Mocking Strategy |
|---|---|---|---|
| Unit | `components/*/tests/` | Individual methods, exception paths, field mapping | Provider SDKs mocked. Tests named `*_mock` per peer review. |
| Integration (endpoint) | `tests/integration/` | FastAPI routing, DI wiring, response structure | AI/chat/storage mocked at DI boundary via autouse conftest fixture |
| Integration (boundary) | `components/cloud_storage_service/tests/test_integration_ai_to_chat.py` | Real `GeminiAiClient` tool-call loop, real `ChatNotificationWrapper` | Only network boundary mocked (genai.Client stubbed, storage mocked) |
| E2E (deployed) | `tests/e2e/test_e2e_workflow.py` | Full HTTP workflow against live Render service | No mocks — real HTTP to deployed service |
| E2E (local) | `tests/e2e/test_e2e.py` | Full workflow with subprocess-launched FastAPI server | Real GCS credentials required |
| Contract | `tests/integration/test_di.py` | `_FakeClient` proves shared ABC is implementable | In-memory fake, no mocks |

Coverage threshold: 85% (enforced in CI via `--cov-fail-under=85`).

## Deployment

- **Direct:** Instantiate `GCPCloudStorageClient` and call GCS SDK directly
- **Remote:** Instantiate `CloudStorageAdapter` and call FastAPI service over HTTP
- Both implement the same `CloudStorageClient` interface, so consumer code is identical
- The FastAPI service is deployed to Render with `auto_deploy = true`. CircleCI verifies deployment via the Render API (`check_render_deploy`), then runs E2E tests against the live service (`post_deploy_e2e`).
- Infrastructure managed via Terraform (`infrastructure/main.tf`): 3 Render services (FastAPI, Prometheus, Grafana)
- `terraform_apply` is disabled in CI due to Render free-tier provider bug (see [deployment.md](deployment.md))

## Extending to Other Providers

1. Create `components/new_provider_impl/`
2. Implement all 6 `CloudStorageClient` methods with `container` parameter
3. Map provider exceptions to shared domain exceptions
4. Map provider metadata to shared `ObjectInfo` fields
5. Add tests

No changes are needed to the shared interface, service, or adapter.
