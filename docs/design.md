# Design Document: Cloud Storage Client Architecture

## Overview

This project implements a provider-agnostic cloud storage system that aligns with the shared `cloud_storage_api` contract (`v1.0.0`) defined by the Cloud Storage vertical (Teams 2, 6, 10). The architecture separates the shared interface from provider-specific implementations, enabling seamless provider switching.

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

### Component 1: `gcp_client_impl`

Google Cloud Storage implementation of `CloudStorageClient`.

- Every method takes `container` as first argument
- `_validate_container` and `_validate_object_name` on every call
- `_map_provider_error` translates GCP SDK exceptions to shared domain exceptions
- `_blob_to_object_info` maps GCS blob to shared `ObjectInfo` (all 9 fields)
- `list_files` sorts results by `object_name`
- `get_file_info` raises `ObjectNotFoundError` (not returns `None`)

Authentication resolution order:

1. `oauth_token` / `GCP_OAUTH_TOKEN`
2. `credentials_path` / `GOOGLE_APPLICATION_CREDENTIALS`
3. `GCP_SERVICE_KEY` (raw JSON or base64)
4. Application Default Credentials

### Component 2: `cloud_storage_adapter`

HTTP adapter implementing `CloudStorageClient` via the generated OpenAPI client.

- All 6 methods proxy to the FastAPI service
- `upload_obj` reads `BinaryIO`, sends raw bytes
- `download_file` writes response content to local file
- Maps HTTP status codes to shared exceptions (401/403 -> `AuthenticationError`, 404 -> `ObjectNotFoundError` or `ContainerNotFoundError`)
- `list_files` sorts results by `object_name`
- No raw `httpx` calls; all requests go through the generated client

### Component 3: `cloud_storage_service`

FastAPI microservice wrapping the GCP implementation.

- All endpoints use shared method names via the `CloudStorageClient` interface
- Optional `container` query parameter (defaults to `GCS_BUCKET_NAME`)
- `object_info_to_response` maps shared `ObjectInfo` fields to HTTP response fields
- Comprehensive exception handling: all 8 shared exceptions to appropriate HTTP status codes
- OAuth 2.0 with opaque session tokens (provider token stays server-side)

### Component 4: `cloud_storage_service_api_client`

Auto-generated from `openapi.json` via `openapi-python-client`. Used internally by the adapter. Not hand-edited.

## Error Handling

### Exception Translation at Two Boundaries

Adapter boundary (HTTP -> domain):

| HTTP Status | Shared Exception |
|---|---|
| 401, 403 | `AuthenticationError` |
| 404 (container) | `ContainerNotFoundError` |
| 404 (object) | `ObjectNotFoundError` |
| 422 (key/object_name) | `InvalidObjectNameError` |
| 422 (container) | `InvalidContainerError` |
| Other | `StorageBackendError` |

Service boundary (domain -> HTTP):

| Shared Exception | HTTP Status |
|---|---|
| `AuthenticationError` | 401 |
| `ContainerNotFoundError` | 404 |
| `ObjectNotFoundError` | 404 |
| `InvalidContainerError` | 422 |
| `InvalidObjectNameError` | 422 |
| `InvalidFileObjectError` | 422 |
| `LocalFileAccessError` | 500 |
| `StorageBackendError` | 500 |

## Testing Strategy

| Type | Location | What it tests |
|---|---|---|
| Unit | `components/*/tests/` | Individual methods, mocked providers, exception paths |
| Integration | `tests/integration/` | Shared contract compliance, fake client behavior |
| E2E | `tests/e2e/` | Full workflows against real GCS and deployed service |

Coverage threshold: 85% (enforced in CI).

## Deployment

- Direct: Instantiate `GCPCloudStorageClient` and call GCS SDK directly
- Remote: Instantiate `CloudStorageAdapter` and call FastAPI service over HTTP
- Both implement the same `CloudStorageClient` interface, so consumer code is identical
- The FastAPI service is deployed to Render with auto-deploy on push. CircleCI verifies deployment via the Render API.

## Extending to Other Providers

1. Create `components/new_provider_impl/`
2. Implement all 6 `CloudStorageClient` methods with `container` parameter
3. Map provider exceptions to shared domain exceptions
4. Map provider metadata to shared `ObjectInfo` fields
5. Add tests

No changes are needed to the shared interface, service, or adapter.
