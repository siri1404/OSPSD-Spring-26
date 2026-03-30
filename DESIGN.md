# HW2 Design Document: Service-Based Cloud Storage Architecture

## Architecture Overview

### Components

HW1 established a library-based model where clients import and use implementations directly:
- **cloud_storage_client_api**: Abstract `CloudStorageClient` interface defining contract
- **gcp_client_impl**: Concrete GCP implementation of the interface

HW2 transforms this into a service-based architecture by adding three new components:

1. **cloud_storage_service** (FastAPI backend)
   - Wraps the existing HW1 library code as HTTP endpoints
   - Handles OAuth 2.0 authentication flow
   - Protects storage endpoints with bearer tokens
   - No business logic rewritten—only exposed over HTTP

2. **cloud_storage_service_api_client** (Auto-generated client)
   - Generated from FastAPI OpenAPI spec
   - Provides typed Python client for all service endpoints
   - Generated from openapi.json via openapi-python-client tool
   - Eliminates manual HTTP request boilerplate

3. **cloud_storage_adapter** (HTTP-backed CloudStorageClient implementation)
   - Implements the `CloudStorageClient` interface using the generated HTTP client
   - Translates interface method calls to HTTP service requests and responses
   - Maps HTTP status codes and errors to Python exceptions
   - Enables location transparency: consumer code works identically with local or remote implementations

### Request Flow

A single request travels through this 5-component journey:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Consumer Code (business logic)                                          │
│                                                                         │
│   client: CloudStorageClient = get_client()  # Injected adapter         │
│   info = client.upload_bytes(data=b"...", key="file.txt")               │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ (calls interface method)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Component 5: cloud_storage_adapter                                      │
│                                                                         │
│   def upload_bytes(self, *, data, key, ...):                            │
│       body = BodyUploadFileUploadPost(file=data, key=key)               │
│       response = upload_file_upload_post.sync_detailed(                 │
│           client=self._client,                                          │
│           body=body                                                     │
│       )                                                                 │
│       return self._to_object_info(response.parsed)                      │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ (HTTP POST request via generated client)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Component 4: cloud_storage_service_api_client (generated)               │
│                                                                         │
│   upload_file_upload_post.sync_detailed(...)                            │
│       ↓                                                                 │
│   HTTP POST /upload → Service base URL                                  │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ (HTTP transport)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Component 3: cloud_storage_service (FastAPI)                            │
│                                                                         │
│   @app.post("/upload")                                                  │
│   async def upload_file(                                                │
│       file: UploadFile,                                                 │
│       key: str,                                                         │
│       token: str = Depends(verify_token),                               │
│       client: GCPCloudStorageClient = Depends(get_storage_client)       │
│   ):                                                                    │
│       file_contents = await file.read()                                 │
│       object_info = client.upload_bytes(...)  # Local HW1 client        │
│       return ObjectInfoResponse(...)                                    │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ (calls HW1 library code)
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Component 2: gcp_client_impl (HW1 library)                              │
│                                                                         │
│   class GCPCloudStorageClient(CloudStorageClient):                      │
│       def upload_bytes(self, *, data, key, ...):                        │
│           bucket = self._get_bucket()                                   │
│           blob = bucket.blob(key)                                       │
│           blob.upload_from_string(data)                                 │
│           return self._blob_to_object_info(blob)                        │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ (calls Google Cloud Storage API)
                           ▼
                    Google Cloud Storage
```

**Response Flow (reversed):**
GCS → gcp_client_impl (ObjectInfo) → service (HTTP 200 JSON) → generated client (ObjectInfoResponse) → adapter (ObjectInfo) → consumer code

---

## API Design

### Endpoints

All storage endpoints require bearer token authentication (HTTP Authorization: Bearer <token>).

#### Authentication Endpoints

**POST /auth/login**
- **Purpose:** Initiate OAuth 2.0 login flow with Google
- **Auth Required:** No
- **Request Body:** None (form data)
- **Response (200):**
  ```json
  {
    "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&state=..."
  }
  ```
- **Notes:** Returns authorization URL for client-side redirect to Google consent screen

**GET /auth/callback**
- **Purpose:** Handle OAuth 2.0 callback from Google (exchanges authorization code for token)
- **Auth Required:** No
- **Query Parameters:**
  - `code` (required): Authorization code from Google OAuth
  - `state` (required): State parameter for CSRF protection
- **Response (200):**
  ```json
  {
    "access_token": "ya29.a0AfH6SMBx...",
    "token_type": "bearer",
    "expires_in": 3599
  }
  ```
- **Error Responses:**
  - **400:** Invalid state parameter (possible CSRF attack) or token exchange failure
- **Flow:** Validates state exists in active_sessions → exchanges code via Google token endpoint → stores token → returns access_token to client

#### Health Endpoint

**GET /health**
- **Purpose:** Verify service status
- **Auth Required:** No
- **Response (200):**
  ```json
  {
    "status": "healthy",
    "service": "cloud-storage-service",
    "timestamp": "2026-03-29T14:30:45.123456"
  }
  ```

#### Storage Endpoints

**POST /upload**
- **Purpose:** Upload a file to cloud storage
- **Auth Required:** Yes (Bearer token)
- **Request Body:** multipart/form-data
  - `file` (required): File binary data
  - `key` (required): Destination path in storage
  - `content_type` (optional): MIME type
- **Response (200):**
  ```json
  {
    "key": "documents/report.pdf",
    "size_bytes": 245687,
    "etag": "abc123def456",
    "updated_at": "2026-03-29T14:30:45.123456",
    "content_type": "application/pdf",
    "metadata": {"owner": "user1"}
  }
  ```
- **Error Responses:**
  - **401:** Missing or invalid bearer token
  - **422:** Validation error (missing required fields)
  - **500:** Upload failure

**GET /download/{key}**
- **Purpose:** Download file from cloud storage
- **Auth Required:** Yes (Bearer token)
- **Path Parameters:**
  - `key` (required): Object key/path to download
- **Response (200):** Binary file content
- **Error Responses:**
  - **401:** Missing or invalid bearer token
  - **404:** File not found
  - **422:** Validation error (invalid path)

**GET /list**
- **Purpose:** List objects in cloud storage with optional prefix filter
- **Auth Required:** Yes (Bearer token)
- **Query Parameters:**
  - `prefix` (optional): Filter objects by key prefix (default: "")
- **Response (200):**
  ```json
  {
    "objects": [
      {
        "key": "documents/report1.pdf",
        "size_bytes": 245687,
        "etag": "abc123",
        "updated_at": "2026-03-29T14:30:45.123456",
        "content_type": "application/pdf",
        "metadata": null
      },
      {
        "key": "documents/report2.pdf",
        "size_bytes": 156234,
        "etag": "def456",
        "updated_at": "2026-03-29T14:25:30.654321",
        "content_type": "application/pdf",
        "metadata": null
      }
    ]
  }
  ```

**DELETE /delete/{key}**
- **Purpose:** Delete an object from cloud storage
- **Auth Required:** Yes (Bearer token)
- **Path Parameters:**
  - `key` (required): Object key/path to delete
- **Response (204):** No content (successful deletion)
- **Error Responses:**
  - **401:** Missing or invalid bearer token
  - **404:** File not found
  - **422:** Validation error

**GET /head/{key}**
- **Purpose:** Get object metadata without downloading contents
- **Auth Required:** Yes (Bearer token)
- **Path Parameters:**
  - `key` (required): Object key/path to query
- **Response (200):**
  ```json
  {
    "key": "documents/report.pdf",
    "size_bytes": 245687,
    "etag": "abc123def456",
    "updated_at": "2026-03-29T14:30:45.123456",
    "content_type": "application/pdf",
    "metadata": null
  }
  ```
- **Error Responses:**
  - **401:** Missing or invalid bearer token
  - **404:** Object not found

### Error Handling

The service translates errors from the underlying GCP client into HTTP responses. Here's the error mapping strategy:

#### Error Translation in CloudStorageAdapter

**Download Errors:**
- **GCS returns 404** → Adapter raises `FileNotFoundError` → Service catches → HTTP 404
- **GCS returns other non-200** → Adapter raises `RuntimeError` → Service catches → HTTP 500

```python
# From adapter.py - download_bytes() method
def download_bytes(self, *, key: str) -> bytes:
    response = self._client.get_httpx_client().request("get", f"/download/{encoded_key}")
    if response.status_code == HTTPStatus.OK:
        return response.content
    if response.status_code == HTTPStatus.NOT_FOUND:
        msg = f"Object not found: {key}"
        raise FileNotFoundError(msg)
    msg = f"download_bytes failed with status {response.status_code}: {response.text}"
    raise RuntimeError(msg)
```

**Delete Errors:**
```python
# From adapter.py - delete() method
def delete(self, *, key: str) -> None:
    response = delete_object_delete_key_delete.sync_detailed(key=key, client=self._client)
    parsed = response.parsed
    
    if response.status_code == HTTPStatus.NO_CONTENT:
        return
    if response.status_code == HTTPStatus.NOT_FOUND:
        msg = f"Object not found: {key}"
        raise FileNotFoundError(msg)
    
    # Other errors raised via helper method
    self._raise_validation_or_runtime("delete", parsed, response.status_code)
```

**Head Errors:**
```python
# From adapter.py - head() method
def head(self, *, key: str) -> ObjectInfo | None:
    response = head_object_head_key_get.sync_detailed(key=key, client=self._client)
    parsed = response.parsed
    
    if response.status_code == HTTPStatus.NOT_FOUND:
        return None  # Returns None if object doesn't exist (not an error)
    if response.status_code == HTTPStatus.OK and isinstance(parsed, ObjectInfoResponse):
        return self._to_object_info(parsed)
    
    # Raise error for unexpected status codes
    self._raise_validation_or_runtime("head", parsed, response.status_code)
```

**HTTP Validation Errors:**
- Generated client returns `HTTPValidationError` in response when request validation fails
- Adapter detects this via `isinstance(parsed, HTTPValidationError)` check
- Raises `TypeError` to indicate contract violation to consumer

#### Service-Level Error Handling

Service endpoints wrap all operations in try/except blocks:

```python
@app.post("/upload", response_model=ObjectInfoResponse, tags=["Storage"])
async def upload_file(...):
    try:
        object_info = client.upload_bytes(...)
        return object_info_to_response(object_info)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {exc}",
        ) from exc
```

#### Authentication Error Handling

**Invalid Bearer Token:**
- `verify_token()` checks dev token bypass first (`DEV_AUTH_TOKEN`)
- Falls back to Google tokeninfo endpoint validation
- Raises `HTTPException(401)` if token invalid or missing

---

## The Adapter Pattern

### Why It's Needed

The problem: Generated API client doesn't match the original HW1 interface contract.

**HW1 CloudStorageClient interface:**
```python
class CloudStorageClient(ABC):
    @abstractmethod
    def upload_file(self, *, local_path: str, key: str, content_type: str | None = None) -> ObjectInfo:
        pass
    
    @abstractmethod
    def upload_bytes(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectInfo:
        pass
    
    @abstractmethod
    def download_bytes(self, *, key: str) -> bytes:
        pass
    
    @abstractmethod
    def list(self, *, prefix: str) -> list[ObjectInfo]:
        pass
    
    @abstractmethod
    def delete(self, *, key: str) -> None:
        pass
    
    @abstractmethod
    def head(self, *, key: str) -> ObjectInfo | None:
        pass
```

**Generated client from /upload endpoint:**
```python
# From cloud_storage_service_api_client/api/storage/upload_file_upload_post.py
def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: BodyUploadFileUploadPost,
) -> Response[HTTPValidationError | ObjectInfoResponse]:
    """Returns a typed response wrapper with parsed payload union."""
```

**The mismatch:**
- Interface expects method `upload_bytes(data: bytes, key: str)` → returns `ObjectInfo`
- Generated client exposes `sync_detailed(..., body=...)` and returns `Response[HTTPValidationError | ObjectInfoResponse]`
- Different types, different calling convention, different error semantics

**Consumer code must NOT change:** Same code should work with local (HW1) or remote (HW2) implementation.

### How It Works: Code Example Comparison

#### Library Usage (HW1 - Before)
```python
# Consumer code using local library
from cloud_storage_client_api import get_client

def process_file(token: str):
    # DI provides local GCPCloudStorageClient
    client = get_client()  
    
    # Direct, simple interface usage
    info = client.upload_bytes(
        data=b"file contents",
        key="documents/report.pdf",
        content_type="application/pdf"
    )
    
    downloaded = client.download_bytes(key="documents/report.pdf")
    files = client.list(prefix="documents/")
    client.delete(key="documents/report.pdf")
    
    return info
```

#### Service Usage (HW2 - After)
```python
# EXACT SAME consumer code—only DI registration changes
from cloud_storage_client_api import get_client

def process_file(token: str):
    # DI now provides CloudStorageAdapter instead of GCPCloudStorageClient
    # Consumer has no idea—same interface!
    client = get_client()  
    
    # IDENTICAL interface usage
    info = client.upload_bytes(
        data=b"file contents",
        key="documents/report.pdf",
        content_type="application/pdf"
    )
    
    downloaded = client.download_bytes(key="documents/report.pdf")
    files = client.list(prefix="documents/")
    client.delete(key="documents/report.pdf")
    
    return info
```

**DI Registration (what changes beneath the surface):**

```python
# HW1 registration in gcp_client_impl/__init__.py
from cloud_storage_client_api.di import register_get_client

def _make_gcp_client() -> CloudStorageClient:
    return GCPCloudStorageClient()

register_get_client(_make_gcp_client, name="gcp")
register_get_client(_make_gcp_client)  # default provider

# HW2 registration in cloud_storage_adapter/__init__.py
def _make_cloud_storage_adapter() -> CloudStorageClient:
    return CloudStorageAdapter(
        base_url=os.getenv("CLOUD_STORAGE_SERVICE_URL", "http://localhost:8000"),
        token=os.getenv("DEV_AUTH_TOKEN", "dev-token-12345"),
    )

register_get_client(_make_cloud_storage_adapter, name="service")
```


#### Adapter Implementation (The Shim)

```python
class CloudStorageAdapter(CloudStorageClient):
    """Implements CloudStorageClient interface over HTTP service"""
    
    def __init__(self, base_url: str, token: str) -> None:
        self._client = AuthenticatedClient(base_url=base_url, token=token)
    
    def upload_bytes(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectInfo:
        """Translate CloudStorageClient method to generated client call"""
        # Adapt: interface parameters → request body
        body = BodyUploadFileUploadPost(
            file=data.decode("latin-1"),
            key=key,
            content_type=content_type if content_type is not None else UNSET,
        )
        
        # Call generated client
        response = upload_file_upload_post.sync_detailed(
            client=self._client, 
            body=body
        )
        parsed = response.parsed
        
        # Adapt: response model → interface return type
        if response.status_code == HTTPStatus.OK and isinstance(parsed, ObjectInfoResponse):
            return self._to_object_info(parsed)
        
        # Adapt: HTTP errors → Python exceptions
        self._raise_validation_or_runtime("upload_bytes", parsed, response.status_code)
```

**Key Benefits of Adapter:**
1. **Location transparency**: Consumer doesn't care if using local or remote
2. **Contract consistency**: Maintains HW1 interface across both implementations
3. **Error mapping**: HTTP status codes → Python exceptions (FileNotFoundError, RuntimeError, TypeError)
4. **Type safety**: Interface return types match consumer expectations

---

## Testing Strategy

### What Was Tested

**Component Testing (unit/integration level):**

1. **Service endpoints** (components/cloud_storage_service/tests/)
   - Auth flow (login, callback state validation)
   - Bearer token verification
   - Storage operations (upload, download, list, delete, head)
   - Error handling for malformed requests

2. **Generated client** (tested via E2E in `tests/e2e/test_e2e.py`)
  - Generated endpoint helpers exercised against the live FastAPI service
  - `AuthenticatedClient` initialization and bearer-token usage verified
  - Typed model parsing validated in round-trip flows

3. **Adapter operations** (components/cloud_storage_adapter/tests/)
   - CloudStorageClient interface implementation
   - Error mapping (404 → FileNotFoundError, HTTP errors → RuntimeError)
   - Request/response transformation between interface and HTTP

4. **Adapter DI registration** (components/cloud_storage_adapter/tests/test_adapter_di.py)
   - Service provider factory wiring
   - DI container resolution

5. **Integration DI** (tests/integration/test_di.py)
   - Full 5-component dependency injection
   - Service lookup and resolution

6. **E2E tests** (tests/e2e/test_e2e.py)
   - Full request flow from consumer → adapter → service → GCP → back

### Test Types

| Type | Purpose | Count | Examples |
|------|---------|-------|----------|
| **Unit** | Test single functions/methods in isolation | 165 total (152 passed) | Token validation, error mapping, model conversion |
| **Integration** | Test component interactions (no external APIs) | 7 total (7 passed) | Adapter calling generated client, service route handling |
| **E2E** | Full workflow with real service and GCP (when available) | 22 total (18 passed) | Upload/download cycle, OAuth flow |

**CircleCI latest snapshot:**
- Unit: 165 total, 152 passed, 13 skipped, 0 failed
- Integration: 7 total, 7 passed, 0 failed
- E2E: 22 total, 18 passed, 4 skipped, 0 failed
- Overall: 194 total, 177 passed, 17 skipped, with **94.64% code coverage**

### Mocking Strategy

**What We Mock:**
1. **Google OAuth endpoints** (exchange code, token validation)
   - Why: Don't want to hit real Google servers in tests
  - How: Patch `cloud_storage_service.main.exchange_code_for_token` with `AsyncMock`; `AsyncClient` is used to call routes, not mocked directly
   - Enables reliable testing without OAuth credentials

2. **Google Cloud Storage bucket operations** (in unit tests)
   - Why: GCP integration is tested separately
   - How: `gcp_client_impl.GCPCloudStorageClient` mocked in service route tests
   - Allows testing service logic without GCP dependencies

3. **FastAPI dependency injection** (in adapter tests)
   - Why: Test adapter in isolation without running full service
  - How: Monkeypatch generated endpoint helper functions and/or set mocked underlying `httpx` client on the adapter
   - Enables error mapping validation without HTTP transport

**What We Test With Real Implementations:**
1. **Adapter ↔ Generated client interaction**
   - Uses actual generated client code (not mocked)
   - Verifies real serialization/deserialization

2. **Generated client creation and configuration**
   - Tests actual `AuthenticatedClient` instantiation
   - Verifies bearer token injection

3. **DI registration and resolution**
   - Uses actual dependency injection library
   - Validates real service provider factory wiring

4. **E2E flows**
   - When running against live deployment: full real flow
   - When running locally: uses dev token plus real backend credentials when available; tests are skipped if credentials are missing

### Interface Compliance: How We Verified Adapter Implements CloudStorageClient Correctly

**Approach 1: Contract and behavior tests**
- `test_upload_bytes_returns_object_info`
- `test_download_404_raises_file_not_found`
- `test_download_non_404_error_raises_runtime`
- `test_head_404_returns_none`
- `test_delete_404_raises_file_not_found`
- `test_list_maps_objects`

These tests verify that adapter methods return interface-level types (`ObjectInfo`, `bytes`, `list[ObjectInfo]`, `None`) and map HTTP outcomes to expected Python exceptions.

**Approach 2: DI resolution tests**
- `components/cloud_storage_adapter/tests/test_adapter_di.py` verifies resolving adapter instances through DI override contexts.
- `tests/integration/test_di.py` verifies provider registration, named provider lookup, and parallel/context isolation.

**Approach 3: End-to-end behavioral equivalence**
- `test_adapter_and_impl_interoperate` exercises the same storage workflow through adapter and direct GCP implementation paths.
- `test_generated_client_round_trip` verifies generated client + service contract end-to-end.


**Coverage Validation:**
- **Method coverage**: All 6 CloudStorageClient methods implemented and tested
- **Error path coverage**: Each error case (404, 500, validation) covered
- **Type compliance**: Return-type behavior is validated by adapter operation tests and integration usage
- **Parameter compliance**: Method signatures are implemented per interface in code; no dedicated signature-equality test currently exists
- **DI integration**: Adapter correctly registers and resolves through DI system

---

## Summary

HW2 successfully transforms a library-based cloud storage client into a service-oriented architecture:

1. **FastAPI Service** wraps the HW1 library with HTTP endpoints and OAuth authentication
2. **Auto-generated Client** eliminates HTTP boilerplate automatically from OpenAPI spec
3. **Adapter Pattern** ensures consumer code never changes—works with local OR remote provider

The three-bridge architecture achieves the core goal: **consumer code doesn't care whether it's using a library or a service**. Location is merely geography. The same interface, same method calls, same types—whether the implementation runs locally or reaches a remote service over HTTP.

Testing validates each component and the full integrated flow. In the latest CircleCI run: 194 total tests, 177 passed, 17 skipped, 0 failed, with 94.64% coverage.
