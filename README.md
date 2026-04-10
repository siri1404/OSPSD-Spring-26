# OSPSD Spring '26 - Cloud Storage Client

> **⚠️ HW3 Status:** This project has been refactored to align with the shared Cloud Storage API contract (v1.0.0).  
> See [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md), [VERTICAL_API_MEMO.md](VERTICAL_API_MEMO.md), [DESIGN.md](DESIGN.md), and [docs/design.md](docs/design.md) for details.

[![CircleCI](https://dl.circleci.com/status-badge/img/gh/siri1404/OSPSD-Spring-26/tree/hw-2.svg?style=shield)](https://dl.circleci.com/status-badge/redirect/gh/siri1404/OSPSD-Spring-26/tree/hw-2)
![Coverage](https://img.shields.io/badge/coverage-85%25%2B-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
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
- Comprehensive testing strategy (unit, integration, E2E)
- CI/CD automation with CircleCI

---

## Architecture Overview

This repository contains **four local components** plus one **external shared API dependency**:

### External Shared API: `cloud_storage_api` (Git Dependency)

The provider-agnostic contract is maintained in the cross-team repository and consumed here via `uv` git source pinning (`tag = "v1.0.0"`).

**Key Features:**
- Abstract `CloudStorageClient` base class with 6 methods
- `ObjectInfo` dataclass for metadata representation
- Shared exception taxonomy (`ObjectNotFoundError`, `StorageBackendError`, etc.)
- Stable contract reused by implementation, adapter, and service layers

**Source of truth:** `cloud-storage-api = { git = "https://github.com/2SpaceMasterRace/ospsd-cloud-storage.git", tag = "v1.0.0" }`

### Component 1: `gcp_client_impl` (Implementation)

Google Cloud Storage implementation of the abstract interface.

**Key Features:**
- Full GCS operations: upload, download, list, delete, metadata retrieval
- Multiple authentication modes: service account file, environment variable JSON, Application Default Credentials
- Configuration via environment variables with constructor argument overrides
- Comprehensive error handling with clear messages

### Component 2: `cloud_storage_adapter` (HTTP Adapter)

HTTP wrapper implementing `CloudStorageClient` by proxying requests to the cloud storage service via OpenAPI client.

**Key Features:**
- Wraps service endpoints as CloudStorageClient operations
- Type-safe async HTTP communication with generated OpenAPI client
- Proper HTTP status code handling (200, 204, 404, 400, 500, 507)
- Metadata extraction from response headers
- Configurable service base URL (default: local service)

### Component 3: `cloud_storage_service` (FastAPI Service)

FastAPI microservice exposing cloud storage operations via REST endpoints with OAuth 2.0 authentication.

**Key Features:**
- 8 REST endpoints: login, callback, upload, download, list, delete, head, health
- OAuth 2.0 authentication flow with state management
- Bearer token validation for protected storage routes
- Pluggable backend using the shared `CloudStorageClient` contract
- Pydantic models for request/response validation

### Component 4: `cloud_storage_service_api_client` (Generated API Client)

Type-safe OpenAPI-generated async HTTP client for the cloud storage service.

**Key Features:**
- Auto-generated from service OpenAPI schema
- Pydantic models for all operations
- Async/await support for non-blocking I/O
- Used by cloud_storage_adapter to communicate with service

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

- Python 3.11 or higher
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
1. `credentials_path` argument or `GOOGLE_APPLICATION_CREDENTIALS` env var (service account file)
2. `GCP_SERVICE_KEY` env var (raw or base64-encoded service account JSON)
3. Application Default Credentials (gcloud login, Workload Identity, etc.)

---

## Documentation

Full documentation is available in the `docs/` directory:

- [Landing Page](docs/index.md) — Quick navigation and user-specific guidance
- [Contributing Guide](docs/CONTRIBUTING.md) — Development workflow, commit standards, PR process
- [Testing Guide](docs/testing.md) — Test execution, environment setup, credentials, debugging
- [CircleCI Setup](docs/circleci-setup.md) — CI configuration, environment variables, troubleshooting
- [Project Structure](docs/structure.md) — Directory layout and component organization
- [Architecture & Design](docs/design.md) — Design patterns, DI system, authentication modes, extensibility

**Component-Specific Documentation:**
- [Cloud Storage Adapter](components/cloud_storage_adapter/README.md) — Service-backed shared API implementation
- [Cloud Storage Service](components/cloud_storage_service/README.md) — FastAPI endpoints and auth flow
- [Cloud Storage Service API Client](components/cloud_storage_service_api_client/README.md) — Generated OpenAPI client package
- [GCP Implementation](components/gcp_client_impl/README.md) — Configuration, authentication setup, error handling

---

## CI/CD Pipeline

CircleCI continuously validates code on the `hw-2` branch:

- Build: Environment setup with `uv`
- Lint: Code style checking with `ruff`
- Type Check: Static types with `mypy --strict`
- Unit Tests: Fast component tests with coverage reporting
- Integration Tests: Component interaction and contract tests
- E2E Tests: Real GCS workflows (protected branches only)

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
 - **Docs:** https://cloud-storage-service-mcni.onrender.com/docs
 - **OAuth Login Endpoint:** https://cloud-storage-service-mcni.onrender.com/auth/login

### Required Environment Variables
| Variable | Purpose |
| --- | --- |
| `GCP_SERVICE_KEY` | Base64-encoded GCP service-account JSON used by the storage client |
| `GCS_BUCKET_NAME` | Target bucket for uploads/downloads |
| `GOOGLE_CLOUD_PROJECT` | GCP project that owns the bucket |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth credentials for browser auth flows |
| `GOOGLE_OAUTH_REDIRECT_URI` | Redirect URL Render should call after auth (defaults to the hosted `/auth/callback`) |
| `DEV_AUTH_TOKEN` | Static bearer token for local and smoke testing |
| `RENDER_API_KEY` | (CircleCI only) Render Personal Access Token with deploy scope |
| `RENDER_SERVICE_ID` | (CircleCI only) ID of the Render web service |
| `RENDER_SERVICE_URL` | (CircleCI only) Base URL for smoke test (e.g., https://cloud-storage-service-mcni.onrender.com) |

### CI/CD Pipeline (CircleCI)
- On every push to `hw-2`:
  - Build, lint, typecheck, unit/integration/e2e test
  - Deploys to Render using API
  - Verifies `/health` endpoint
- See `.circleci/config.yml` and [docs/circleci-setup.md](docs/circleci-setup.md) for details.

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

## License

See [LICENSE](LICENSE) file for license information.

---

## Support & Questions

For issues, feature requests, or questions:
- Check [docs/testing.md](docs/testing.md) for test execution guidance
- Review [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before submitting PRs
- File issues using GitHub Issue templates