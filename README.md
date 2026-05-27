# OSPSD Spring '26 - Cloud Storage Client


[![CircleCI](https://dl.circleci.com/status-badge/img/gh/siri1404/OSPSD-Spring-26/tree/hw-3.svg?style=shield)](https://dl.circleci.com/status-badge/redirect/gh/siri1404/OSPSD-Spring-26/tree/hw-3)
![Coverage](https://img.shields.io/badge/coverage-85%25%2B-brightgreen)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-brightgreen)

## Team Members

1. Pooja Gayathri Kanala
2. Harshitha Jonnagaddala
3. Rahul Mallidi
4. Apoorva Menon
5. Aditya Nagdekar

---

## Purpose

This project implements a **provider-agnostic cloud storage client** with modular architecture. It separates the abstract storage interface from concrete provider implementations, allowing applications to switch between cloud providers (GCP, AWS, Azure) without changing business logic.

The project demonstrates clean architectural patterns through:
- Abstract Base Classes for interface contracts
- Shared API contracts across teams via pinned git dependency
- AI-powered natural language interface with tool calling
- Cross-vertical integration with Team 9's chat service
- Infrastructure as Code with Terraform and Prometheus/Grafana observability
- Comprehensive testing strategy (unit, integration, E2E)
- CI/CD automation with CircleCI

---

## Architecture Overview

```mermaid
flowchart LR
  %% Layer 1: Users
  User["Users"]
  
  %% Layer 2: FastAPI Service (core)
  Service["cloud_storage_service<br/>FastAPI"]
  
  %% Layer 3: Abstract Interfaces (Contracts)
  CloudStorageAPI["cloud_storage_api<br/>CloudStorageClient"]
  AiAPI["ai_client_api<br/>AiClientApi"]
  ChatAPI["chat_client_api<br/>ChatClient"]
  
  %% Layer 4: Implementations
  GCPImpl["gcp_client_impl<br/>GCP Storage"]
  AdapterImpl["cloud_storage_adapter<br/>HTTP Adapter"]
  GeminiImpl["gemini_ai_client_impl<br/>Gemini AI"]
  ChatImpl["chat_client_wrapper<br/>Slack"]
  
  %% Layer 5: Generated Code
  APIClient["cloud_storage_service_api_client<br/>OpenAPI Client"]
  
  %% Layer 6: External Services
  GCS["Google Cloud Storage"]
  GeminiAPI["Gemini API"]
  SlackAPI["Slack API"]
  
  %% Layer 7: Observability & Deployment
  Prometheus["Prometheus"]
  Grafana["Grafana"]
  CircleCI["CircleCI"]
  Terraform["Terraform"]
  Render["Render"]
  
  %% Connections: User → Service
  User -->|REST calls| Service
  
  %% Connections: Service → Abstractions
  Service -->|depends on| CloudStorageAPI
  Service -->|depends on| AiAPI
  Service -->|depends on| ChatAPI
  
  %% Connections: Abstractions → Implementations
  CloudStorageAPI -->|implemented by| GCPImpl
  CloudStorageAPI -->|implemented by| AdapterImpl
  AiAPI -->|implemented by| GeminiImpl
  ChatAPI -->|wrapped by| ChatImpl
  
  %% Connections: Implementations → External
  GCPImpl -->|reads/writes| GCS
  GeminiImpl -->|calls| GeminiAPI
  ChatImpl -->|sends to| SlackAPI
  
  %% Connections: Adapter flow
  AdapterImpl -->|uses| APIClient
  APIClient -->|calls| Service
  
  %% Connections: Observability
  Service -->|emits metrics| Prometheus
  Prometheus -->|scraped by| Grafana
  
  %% Connections: Deployment
  Terraform -->|provisions| Render
  CircleCI -->|deploys| Render
  Render -->|hosts| Service
  Render -->|hosts| Prometheus
  Render -->|hosts| Grafana
  
  %% Styling
  classDef interface fill:#e1f5ff,stroke:#0277bd,stroke-width:2px
  classDef implementation fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
  classDef external fill:#fff3e0,stroke:#e65100,stroke-width:2px
  classDef service fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
  classDef infra fill:#fce4ec,stroke:#c2185b,stroke-width:2px
  
  class CloudStorageAPI,AiAPI,ChatAPI interface
  class GCPImpl,AdapterImpl,GeminiImpl,ChatImpl,APIClient implementation
  class GCS,GeminiAPI,SlackAPI external
  class Service service
  class Prometheus,Grafana,CircleCI,Terraform,Render infra
```

This repository contains seven local components plus two external shared API dependencies:

### External Shared APIs

**cloud_storage_api** (Git Dependency)

The provider-agnostic storage contract is maintained in the cross-team repository and consumed here via `uv` git source pinning (`tag = "v1.0.0"`).

**Key Features:**
- Abstract `CloudStorageClient` base class with 6 methods
- `ObjectInfo` dataclass for metadata representation
- Shared exception taxonomy (`ObjectNotFoundError`, `StorageBackendError`, etc.)
- Stable contract reused by implementation, adapter, and service layers

**Source of truth:** `cloud-storage-api = { git = "https://github.com/2SpaceMasterRace/ospsd-cloud-storage.git", tag = "v1.0.0" }`

**Vertical Memo:** [Cloud Storage API Contract (Teams 2, 6, 10)](https://docs.google.com/document/d/1WaYBeOeIb4Jyiz9BlNqNhisPJOL4cgBe-BK9VLG_RVQ/edit?tab=t.0)


**chat_client_api** (Git Dependency - Team 9)

The cross-team chat interface from Team 9. Enables pluggable chat integrations (Slack, Teams, Discord, etc.) without tying storage logic to a specific chat provider.

**Key Features:**
- Abstract `ChatClient` base class with send/fetch/delete message methods
- `Message` dataclass for message metadata
- `Channel` dataclass for channel information
- Shared exception taxonomy (`ChannelNotFoundError`, `MessageNotFoundError`, etc.)

**Source of truth:** `chat-client-api = { git = "https://github.com/HarshithKoriRaj/Shared-API.git", rev = "ebb37e189065760f2090f1488d376485b7b56b20" }`

### Component 1: ai_client_api (AI Interface)

Abstract interface for AI client implementations with tool calling support.

**Key Features:**
- `AiClientApi` ABC with `send_message(prompt, context) -> str` and `tools() -> list[ToolDefinition]`
- Framework-free — no provider SDK leakage into the interface package
- Shared models: `AIResponse` (text + telemetry), `ToolDefinition`, `ToolParameter`
- Same interface/impl separation pattern as the storage vertical

### Component 2: gemini_ai_client_impl (AI Implementation)

Concrete AI client using Google's Gemini API with tool calling for cloud storage operations.

**Key Features:**
- Implements `AiClientApi` against Gemini 2.5 Flash
- 6 storage tools: `list_files`, `get_file_info`, `delete_file`, `upload_file`, `download_file`, `summarize_file`
- Pydantic-validated tool arguments (`ListFilesArgs`, `DeleteFileArgs`, etc.)
- Bounded tool-call loop (max 10 iterations) with `ToolLoopExhaustedError`
- PDF summarization via base64-encoded binary payloads
- `send_message_with_metadata()` returns `AIResponse` with full telemetry

### Component 3: chat_client_wrapper (Notification Formatter)

Wrapper providing a simple notification interface on top of Team 9's `ChatClient` abstraction.

**Key Features:**
- `ChatNotificationWrapper.notify(message)` method for one-liner event notifications
- Pre-formatted messages for storage events (upload, delete, AI actions) via `NotificationMessages` utility
- Configurable channel ID (constructor or `CHAT_CHANNEL_ID` env var)
- Error resilience: notifications fail gracefully without disrupting storage operations
- Pluggable: works with any team that implements the shared `ChatClient` interface

### Component 4: gcp_client_impl (Storage Implementation)

Google Cloud Storage implementation of the abstract interface.

**Key Features:**
- Full GCS operations: upload, download, list, delete, metadata retrieval
- Multiple authentication modes: OAuth token, service account file, base64-encoded JSON, Application Default Credentials
- Configuration via environment variables with constructor argument overrides
- Comprehensive error handling with read/write path distinction

### Component 5: cloud_storage_adapter (HTTP Adapter)

HTTP wrapper implementing `CloudStorageClient` by proxying requests to the cloud storage service via OpenAPI client.

**Key Features:**
- Wraps service endpoints as `CloudStorageClient` operations
- Type-safe synchronous HTTP communication with generated OpenAPI client
- Proper HTTP status code handling (200, 204, 404, 400, 500, 507)
- Container-not-found vs object-not-found disambiguation on 404
- Configurable service base URL (default: local service)

### Component 6: cloud_storage_service (FastAPI Service)

FastAPI microservice exposing cloud storage operations via REST endpoints with OAuth 2.0 authentication.

**Key Features:**
- 12 REST endpoints: `/health`, `/`, `/auth/login`, `/auth/callback`, `/auth/logout`, `/upload`, `/download/{key}`, `/list`, `/delete/{key}`, `/head/{key}`, `/ai/chat`, `/metrics`
- OAuth 2.0 authentication flow with CSRF state management
- AI-powered natural language interface at `/ai/chat` with tool calling
- Prometheus telemetry middleware with latency, success/failure, and AI tool metrics
- Chat notifications via Slack on storage events and AI actions
- Pydantic models for request/response validation (`extra="forbid"`)

### Component 7: cloud_storage_service_api_client (Generated API Client)

Type-safe OpenAPI-generated HTTP client for the cloud storage service.

**Key Features:**
- Auto-generated from service OpenAPI schema
- Pydantic models for all operations
- Used by cloud_storage_adapter to communicate with service

---

## AI Integration: Gemini Tool Calling

The service integrates Google's Gemini API via two new HW3 components:

- **ai_client_api** — Abstract interface (`AiClientApi` ABC) with `send_message(prompt, context) -> str` and `tools() -> list[ToolDefinition]`. Framework-free; no provider SDK leakage.
- **gemini_ai_client_impl** — Concrete implementation using `google-genai`. Supports 6 storage tools (`list_files`, `get_file_info`, `delete_file`, `upload_file`, `download_file`, `summarize_file`) with Pydantic-validated arguments.

The AI client is injected into the FastAPI service via `Depends(get_ai_client)`. The `/ai/chat` endpoint accepts natural-language prompts, dispatches tool calls to the storage client, and returns structured responses with telemetry (`action_taken`, `tool_calls`).

### AI Tool Dispatch Graph

```
POST /ai/chat (prompt)
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
    - ai_tool_calls_total counter incremented
    - ChatNotificationWrapper.notify() (cross-vertical)
```

---

## Quick Start Example

```python
from io import BytesIO

from gcp_client_impl.client import GCPCloudStorageClient

# Create client (reads auth config from environment variables)
client = GCPCloudStorageClient()
container = "your-bucket-name"
remote_path = "greeting.txt"

# Upload file-like object
info = client.upload_obj(
  container=container,
  file_obj=BytesIO(b"Hello, World!"),
  remote_path=remote_path,
)
print(f"Uploaded: {info.object_name}, Size: {info.size_bytes} bytes")

# Download to local file path, then read bytes
downloaded_info = client.download_file(
  container=container,
  object_name=remote_path,
  file_name="downloaded_greeting.txt",
)
content = open("downloaded_greeting.txt", "rb").read()
print(f"Downloaded: {downloaded_info.object_name} -> {content.decode()}")

# List objects
objects = client.list_files(container=container, prefix="greet")
for obj in objects:
  print(f"  {obj.object_name} ({obj.size_bytes} bytes, modified: {obj.updated_at})")

# Check metadata without downloading
meta = client.get_file_info(container=container, object_name=remote_path)
print(f"Integrity: {meta.integrity}, Data type: {meta.data_type}")

# Delete object
client.delete_file(container=container, object_name=remote_path)
```

---

## Installation & Setup

### Prerequisites

- Python 3.12 or higher
- `uv` package manager (installation: https://github.com/astral-sh/uv)
- Git
- GCP account with Cloud Storage enabled (for E2E tests)

### Step 1: Clone Repository

```bash
git clone https://github.com/siri1404/OSPSD-Spring-26.git
cd OSPSD-Spring-26
```

### Step 2: Install Dependencies

```bash
uv sync --all-packages
```

This command:
- Creates a virtual environment
- Installs all workspace packages and the shared `cloud-storage-api` git dependency
- Installs development tools (pytest, ruff, mypy, etc.)

### Step 3: Configure Environment Variables

Create a `.env` file in the repository root with one of the following authentication methods:

**Option A: Service Account File (Local Development)**
```bash
GCS_BUCKET_NAME=your-test-bucket-name
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

**Option B: Base64-Encoded JSON (CI/CD)**
```bash
GCS_BUCKET_NAME=your-test-bucket-name
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GCP_SERVICE_KEY=<base64-encoded-service-account-json>
```

**Option C: Application Default Credentials (gcloud login)**
```bash
GCS_BUCKET_NAME=your-test-bucket-name
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
# No credentials_path needed; uses: gcloud auth application-default login
```

Load environment variables before running tests:
```bash
# Linux/Mac
source .env

# Windows PowerShell
Get-Content .env | ForEach-Object {
    if ($_ -and -not $_.StartsWith('#')) {
        $key, $value = $_ -split '=', 2
        [Environment]::SetEnvironmentVariable($key, $value)
    }
}
```

## Environment Variables

The application has a small number of runtime variables and a few test/deployment variables. These are the ones the code actually reads.

### Runtime and Local Development

| Variable | Used By | Required | Purpose |
|---|---|---:|---|
| `GCS_BUCKET_NAME` | `cloud_storage_service` | Yes | Default storage bucket/container. |
| `GOOGLE_CLOUD_PROJECT` | `gcp_client_impl` | No | GCP project ID used by the storage client. |
| `GOOGLE_APPLICATION_CREDENTIALS` | `gcp_client_impl` | No | Path to a service account JSON file. |
| `GCP_SERVICE_KEY` | `gcp_client_impl`, deployment | No | Raw or base64-encoded service account JSON. |
| `GCP_OAUTH_TOKEN` | `gcp_client_impl` | No | OAuth bearer token for GCS access. |
| `GEMINI_API_KEY` | `gemini_ai_client_impl`, `cloud_storage_service` | Yes | Gemini API key for AI tool calling. |
| `GOOGLE_OAUTH_CLIENT_ID` | `cloud_storage_service` | Yes | OAuth client ID for Google login. |
| `GOOGLE_OAUTH_CLIENT_SECRET` | `cloud_storage_service` | Yes | OAuth client secret for Google login. |
| `GOOGLE_OAUTH_REDIRECT_URI` | `cloud_storage_service` | Yes | OAuth callback URL. |
| `SLACK_BOT_TOKEN` | `cloud_storage_service`, `chat_client_wrapper` | No | Slack bot token for notifications. |
| `CHAT_CHANNEL_ID` | `cloud_storage_service`, `chat_client_wrapper` | No | Slack channel used for notifications. |
| `DEV_AUTH_TOKEN` | `cloud_storage_service` | No | Development/test bearer token bypass. |
| `ENVIRONMENT` | `cloud_storage_service` | No | Enables dev/test auth bypass when set to `development` or `test`. |

### Test and Local-Run Helpers

| Variable | Used By | Purpose |
|---|---|---|
| `STAGING_SERVICE_URL` | `tests/e2e/test_e2e_workflow.py` | Base URL for the deployed or locally running service. |
| `CLOUD_STORAGE_SERVICE_URL` | `components/cloud_storage_adapter/tests/test_adapter_integration.py` | Integration-test target for the adapter. |
| `CLOUD_STORAGE_TEST_CONTAINER` | `components/cloud_storage_adapter/tests/test_adapter_integration.py` | Integration-test bucket/container name. |

### Deployment and IaC

| Variable | Used By | Purpose |
|---|---|---|
| `RENDER_API_KEY` | Terraform / CircleCI | Render API access token. |
| `RENDER_OWNER_ID` | Terraform / CircleCI | Render account or team owner ID. |
| `RENDER_SERVICE_ID` | Terraform / CircleCI | Existing Render service ID for import or deploy checks. |
| `RENDER_SERVICE_URL` | CircleCI | Public URL used by post-deploy checks. |
| `RENDER_REGION` | Terraform | Render region for services. |
| `REPO_URL` | Terraform | Repository URL used by Render runtime_source. |
| `GIT_BRANCH` | Terraform | Branch name Render tracks for auto-deploy. |
| `GRAFANA_ADMIN_PASSWORD` | Terraform / Grafana | Initial Grafana admin password. |

Deployment-only secrets and CI context details are documented in [docs/deployment.md](docs/deployment.md).

## Local Endpoint Smoke Tests

Start the service locally first:

```bash
uv run uvicorn cloud_storage_service.main:app --reload --host 0.0.0.0 --port 8000
```

On Windows PowerShell, use `curl.exe` so the shell does not rewrite the command.

```bash
BASE_URL=http://localhost:8000
TOKEN=${DEV_AUTH_TOKEN:-dev-token-12345}

curl "$BASE_URL/health"
curl "$BASE_URL/metrics"

curl -X POST "$BASE_URL/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "key=sample.txt" \
  -F "file=@sample.txt"

curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/list"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/head/sample.txt"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/download/sample.txt" -o downloaded-sample.txt
curl -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE_URL/delete/sample.txt"

curl -X POST "$BASE_URL/ai/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Container: $GCS_BUCKET_NAME" \
  -d '{"prompt":"list all files in the bucket"}'
```

Expected behavior:

- `/health` returns HTTP 200 without auth.
- `/metrics` returns Prometheus text.
- `/upload`, `/list`, `/head/{key}`, `/download/{key}`, `/delete/{key}` require a bearer token and a configured bucket.
- `/ai/chat` requires `GEMINI_API_KEY` and a container name, and it should produce tool-driven actions rather than plain prose only.

---

## Running Tests

### Unit Tests (Fast, No Credentials Required)

Test individual components with mocked providers:

```bash
uv run pytest components/ -v
```

### Integration Tests (No Credentials Required)

Verify component interactions and shared-contract compatibility:

```bash
uv run pytest tests/integration/ -v
```

### E2E Tests with Environment Variables (Requires GCP Credentials)

Complete workflows against real GCS using `GCP_SERVICE_KEY`:

```bash
uv run pytest tests/e2e/ -m "not local_credentials" -v
```

### E2E Tests with Local Credentials File (Requires GCP Credentials)

Complete workflows using `GOOGLE_APPLICATION_CREDENTIALS`:

```bash
uv run pytest tests/e2e/ -m "local_credentials" -v
```

### All Tests with Coverage Report

```bash
uv run pytest components/ --cov=components/ --cov-report=html --cov-fail-under=85
```

Coverage report opens in `htmlcov/index.html`.

---

## Code Quality & Development

### Code Formatting & Linting

```bash
# Check code style (ruff)
uv run ruff check .

# Auto-fix formatting issues
uv run ruff format .

# Type checking (mypy strict mode)
uv run mypy components/
```

All checks must pass before committing. CircleCI runs these automatically on pull requests.

### Development Standards

- **Strict Type Checking:** `mypy --strict` with minimal exceptions
- **Full Linting:** `ruff select = ["ALL"]` with justified ignores
- **Code Organization:** Absolute imports only; no relative imports
- **Testing:** All code must have unit tests; integration/E2E tests for cross-component flows
- **Commit Messages:** Use conventional format (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`)

---

## Component Details

### cloud_storage_api (shared external package)

The shared interface defines cloud storage operations for all teams. This repository consumes it as a git dependency pinned to `v1.0.0`.

**Six Core Methods:**
- `upload_file(container, local_path, remote_path)` — Upload file from disk
- `upload_obj(container, file_obj, remote_path)` — Upload binary file-like object
- `download_file(container, object_name, file_name)` — Download object to local path
- `list_files(container, prefix)` — List objects matching a prefix
- `delete_file(container, object_name)` — Delete an object
- `get_file_info(container, object_name)` — Get object metadata without downloading

**ObjectInfo fields:**
- `object_name`
- `version_id`
- `data_type`
- `integrity`
- `encryption`
- `storage_tier`
- `size_bytes`
- `updated_at`
- `metadata`

### gcp_client_impl

Google Cloud Storage implementation. See [components/gcp_client_impl/README.md](components/gcp_client_impl/README.md) for configuration and authentication details.

**Authentication Priority:**
1. OAuth token (`oauth_token` argument or `GCP_OAUTH_TOKEN` env var)
2. Service account file (`credentials_path` argument or `GOOGLE_APPLICATION_CREDENTIALS` env var)
3. Inline service account JSON (`service_key` argument or `GCP_SERVICE_KEY` env var — raw or base64-encoded)
4. Application Default Credentials (gcloud login, Workload Identity, etc.)

---

## Documentation

Full documentation is available in the `docs/` directory:

- [Landing Page](docs/index.md) — Quick navigation and user-specific guidance
- [Contributing Guide](docs/CONTRIBUTING.md) — Development workflow, commit standards, PR process
- [Testing Guide](docs/testing.md) — Test execution, environment setup, credentials, debugging
- [CircleCI Setup](docs/circleci-setup.md) — CI configuration, environment variables, troubleshooting
- [Project Structure](docs/structure.md) — Directory layout and component organization
- [Architecture & Design](docs/design.md) — Design patterns, authentication modes, and extensibility
- [Deployment](docs/deployment.md) — IaC bootstrap and Render deployment
- [Observability](docs/observability.md) — Prometheus metrics and Grafana dashboards

**Component-Specific Documentation:**
- [AI Client API](components/ai_client_api/README.md) — Abstract AI interface and shared models
- [Gemini AI Client](components/gemini_ai_client_impl/README.md) — Gemini implementation with tool calling
- [Cloud Storage Adapter](components/cloud_storage_adapter/README.md) — Service-backed shared API implementation
- [Cloud Storage Service](components/cloud_storage_service/README.md) — FastAPI endpoints and auth flow
- [Cloud Storage Service API Client](components/cloud_storage_service_api_client/README.md) — Generated OpenAPI client package
- [GCP Implementation](components/gcp_client_impl/README.md) — Configuration, authentication setup, error handling

---

## Observability & Monitoring

The deployed service emits Prometheus metrics at `/metrics`:

- **storage_service_requests_total** — request count by endpoint, method, status_code, and error_class (success/domain/infra)
- **storage_service_request_latency_seconds** — latency histogram (p50/p95/p99)
- **storage_service_ai_tool_calls_total** — AI tool dispatch count by tool_name and status

Metrics are scraped by Prometheus and visualized in a Grafana dashboard with 7 panels covering latency, request rate, error rate (4xx/5xx), AI tool success/failure, overall success rate, and request distribution by endpoint.

- **Grafana Dashboard:** https://cloud-service-grafana.onrender.com
- **Prometheus:** https://cloud-service-prometheus.onrender.com
- **Metrics endpoint:** https://cloud-storage-service-mcni.onrender.com/metrics

---

## Cross-Vertical Integration: Team 9 Chat

### What is Cross-Vertical Integration?

Team 6's cloud storage service was extended to use Team 9's chat service. Users are now notified in Slack whenever storage operations occur.

### How Team 9's Chat API Was Adopted

We adopted Team 9's shared chat interface (`chat_client_api`). This follows the same clean architecture pattern:

1. **Shared Interface:** Team 9 created `chat_client_api` with a `ChatClient` abstract base class (similar to how Team 6 uses `cloud_storage_api`)
2. **Implementation Adapter:** We created `slack_adapter.py` in the storage service that implements Team 9's `ChatClient` interface and talks to Slack
3. **Wrapper Component:** We created `chat_client_wrapper/` component with a `ChatNotificationWrapper` class that provides a simple `notify()` method
4. **Integration:** The storage service now sends chat notifications on key events (file upload, file delete, AI actions)

### How Chat Notifications Work

When you perform a storage operation or run an AI chat command, the service automatically sends a formatted message to a configured Slack channel:

**Upload Event:**
```
📤 File uploaded: `report.pdf` in container `my-bucket` (1024 bytes)
```

**Delete Event:**
```
🗑️ File deleted: `report.pdf` from container `my-bucket`
```

**AI Action Event:**
```
🤖 AI performed action: `list_files` on container `my-bucket`
   Result: Found 5 matching objects
```

### Configuration

Enable chat notifications by setting:
```bash
CHAT_CHANNEL_ID=your-slack-channel-id
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
```

If `CHAT_CHANNEL_ID` is not set, notifications gracefully disable (storage operations continue to work).

### Architecture Pattern

```
Storage Service (FastAPI)
    ↓
ChatNotificationWrapper (generic notification formatter)
    ↓
SlackChatClient (Team 9's ChatClient implementation)
    ↓
Slack API (via Team 9's slack_sdk dependency)
    ↓
Slack Channel
```

The key insight: **Chat is pluggable.** We depend on Team 9's abstract `ChatClient` interface, not the Slack implementation directly. If Team 9 adds a Teams adapter or Discord adapter to their vertical, we can swap implementations without changing storage code.

---

## CI/CD Pipeline

CircleCI continuously validates code on the `hw-3` branch:

- **Build:** Environment setup with `uv`
- **Lint:** Code style checking with `ruff`
- **Type Check:** Static types with `mypy --strict`
- **Unit Tests:** Fast component tests with coverage reporting
- **Integration Tests:** Component interaction and contract tests
- **Terraform Plan:** IaC validation on every push
- **E2E Tests:** Runs against the deployed Render service (hw-3 branch only)
- **Deploy Check:** Polls Render API to confirm deployment succeeded

Code deploys via Render's `auto_deploy`; `post_deploy_e2e` validates the live service after deployment.

View pipeline status: [CircleCI Project](https://circleci.com/gh/siri1404/OSPSD-Spring-26)

---

## Contributing

We follow a structured contribution process. See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for:

- Setup instructions
- Development workflow and quality checks
- Commit message conventions
- Pull request template and process
- Code review expectations

**Quick Start for Contributors:**
```bash
git checkout -b feature/your-feature-name
# Make changes and run quality checks
uv run ruff check . && uv run ruff format . && uv run mypy components/
uv run pytest components/ tests/integration/ -v
# Push and create PR
```

---

## Extending to Other Providers

To add support for AWS, Azure, or another provider:

1. Create a new component: `components/aws_client_impl/`
2. Implement the shared `CloudStorageClient` interface from `cloud_storage_api`
3. Configure authentication for that provider
4. Expose the implementation as a package (for example `aws_client_impl`)
5. Add comprehensive unit, integration, and E2E tests
6. Wire provider selection in your application layer (constructor/config based), not via shared API DI

See the GCP implementation as a template.

---

## Deployment & Verification

### Platform

- **Live URL:** https://cloud-storage-service-mcni.onrender.com
- **API Docs:** https://cloud-storage-service-mcni.onrender.com/docs
- **Health Check:** https://cloud-storage-service-mcni.onrender.com/health
- **Grafana Dashboard:** https://cloud-service-grafana.onrender.com
- **Prometheus:** https://cloud-service-prometheus.onrender.com
- **Metrics:** https://cloud-storage-service-mcni.onrender.com/metrics

### IaC Bootstrap

Infrastructure is managed via Terraform in `infrastructure/`:

```bash
cd infrastructure
terraform init
terraform plan    # Review changes
terraform apply   # Deploy to Render
```

Requires `RENDER_API_KEY` and `RENDER_OWNER_ID` environment variables. See `infrastructure/variables.tf` for all required variables.

### Required Environment Variables

| Variable | Purpose |
| --- | --- |
| `GCP_SERVICE_KEY` | Base64-encoded GCP service-account JSON used by the storage client |
| `GCS_BUCKET_NAME` | Target bucket for uploads/downloads |
| `GOOGLE_CLOUD_PROJECT` | GCP project that owns the bucket |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth credentials for browser auth flows |
| `GOOGLE_OAUTH_REDIRECT_URI` | Redirect URL Render should call after auth (defaults to the hosted `/auth/callback`) |
| `GEMINI_API_KEY` | Google Gemini API key for AI chat |
| `SLACK_BOT_TOKEN` | Slack bot token for chat notifications |
| `CHAT_CHANNEL_ID` | Slack channel ID for notifications |
| `DEV_AUTH_TOKEN` | Static bearer token for local and smoke testing |
| `RENDER_API_KEY` | (CircleCI only) Render Personal Access Token with deploy scope |
| `RENDER_SERVICE_ID` | (CircleCI only) ID of the Render web service |
| `RENDER_SERVICE_URL` | (CircleCI only) Base URL for smoke test (e.g., https://cloud-storage-service-mcni.onrender.com) |

### Manual API Verification

After deployment, you can verify the service is working with these commands:

```bash
# Health check (should return HTTP 200 and JSON)
curl -i https://cloud-storage-service-mcni.onrender.com/health

# Upload a file
curl -X POST https://cloud-storage-service-mcni.onrender.com/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F key=e2e-manual/sample.txt \
  -F content_type=text/plain \
  -F file=@sample.txt

# Download the file
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://cloud-storage-service-mcni.onrender.com/download/e2e-manual/sample.txt

# Delete the file
curl -X DELETE https://cloud-storage-service-mcni.onrender.com/delete/e2e-manual/sample.txt \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Replace `YOUR_TOKEN` with your configured bearer token.

---

## Known Limitations

### Terraform apply on Render free tier

The `terraform_apply` CI job is currently disabled. The `render-oss/render` v1.8.0 Terraform provider unconditionally sends `maintenance_mode` in update payloads, which Render's free-tier API rejects. Code deploys continue via Render's `auto_deploy`. `terraform_plan` validates IaC on every push. See `.circleci/config.yml` for details.

### Prometheus scraping on Render free tier

Render's free tier does not support private service-to-service networking. Prometheus scrapes the cloud storage service via its public HTTPS URL. If the service is sleeping (free-tier cold start), metrics may be intermittently unavailable.

---

## License

See [LICENSE](LICENSE) file for license information.

---

## Support & Questions

For issues, feature requests, or questions:
- Check [docs/testing.md](docs/testing.md) for test execution guidance
- Review [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before submitting PRs
- File issues using GitHub Issue templates