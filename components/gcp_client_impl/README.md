# GCP Cloud Storage Client Implementation

A production-ready Google Cloud Storage (GCS) client that implements the abstract `CloudStorageClient` interface. This package provides complete cloud storage functionality including file upload, download, listing, deletion, and metadata retrieval.

---

## Overview

`gcp_client_impl` is the concrete implementation of the cloud storage interface for Google Cloud Platform. It handles:

- **File Operations:** Upload files, download objects, list by prefix, delete objects
- **Metadata Retrieval:** Get object info without downloading contents
- **Flexible Authentication:** Service account files, environment variables, or Application Default Credentials
- **Configuration Management:** Constructor kwargs, environment variables, or defaults
- **Automatic Registration:** Registers with the dependency injection system on import

---

## Core Class: `GCPCloudStorageClient`

The main class implementing all storage operations against Google Cloud Storage.

```python
from gcp_client_impl.client import GCPCloudStorageClient

# Create client (reads config from environment)
client = GCPCloudStorageClient()

# Or with explicit configuration
client = GCPCloudStorageClient(
    bucket_name="my-bucket",
    project_id="my-project",
    credentials_path="/path/to/key.json"
)
```

---

## Configuration

Configuration follows a **precedence hierarchy**: constructor kwargs override environment variables, which override defaults.

### Configuration Parameters

| Parameter | Env Variable | Default | Required | Description |
|-----------|--------------|---------|----------|-------------|
| `bucket_name` | `GCS_BUCKET_NAME` | None | Yes | Target GCS bucket name |
| `project_id` | `GOOGLE_CLOUD_PROJECT` | None | No | GCP project ID (for ADC) |
| `credentials_path` | `GOOGLE_APPLICATION_CREDENTIALS` | None | No | Path to service account JSON key file |
| - | `GCP_SERVICE_KEY` | None | No | Raw or base64-encoded service account JSON |

### Configuration Examples

**Example 1: Using Constructor Arguments**
```python
client = GCPCloudStorageClient(
    bucket_name="my-storage-bucket",
    project_id="my-gcp-project",
    credentials_path="/home/user/.gcp/service-account-key.json"
)
```

**Example 2: Using Environment Variables**
```bash
export GCS_BUCKET_NAME="my-storage-bucket"
export GOOGLE_CLOUD_PROJECT="my-gcp-project"
export GOOGLE_APPLICATION_CREDENTIALS="/home/user/.gcp/service-account-key.json"
```

Then in code:
```python
client = GCPCloudStorageClient()  # Reads from environment
```

**Example 3: Using Base64-Encoded Credentials (CI/CD)**
```bash
export GCS_BUCKET_NAME="my-storage-bucket"
export GOOGLE_CLOUD_PROJECT="my-gcp-project"
export GCP_SERVICE_KEY="eyJhbGciOiJSUzI1NiIsImtpZCI6I..."  # base64
```

```python
client = GCPCloudStorageClient()
```

---

## Authentication

The client supports **three authentication modes** with automatic fallback:

### Mode 1: Service Account File Path (Recommended for Development)

Uses a service account JSON key file on disk.

**Setup:**
1. Download service account key from GCP Console
2. Set `GOOGLE_APPLICATION_CREDENTIALS` to the file path
3. Or pass `credentials_path` to constructor

**How it works:**
```python
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/service-account-key.json"

client = GCPCloudStorageClient(bucket_name="my-bucket")
# Client loads credentials from file
```

**Advantages:**
- Works with `gcloud` CLI
- Standard GCP practice
- Secure (key on disk, not in env vars)

**Disadvantages:**
- Requires file system access
- Not suitable for serverless/CI without special setup

---

### Mode 2: Service Account JSON via Environment Variable (Recommended for CI/CD)

Uses service account JSON stored as a string (raw or base64-encoded).

**Setup (for Base64):**
```bash
# Encode service account file
base64 -i /path/to/service-account-key.json | tr -d '\n'

# Set as environment variable
export GCP_SERVICE_KEY="eyJhbGciOiJSUzI1NiIsImtpZCI6I..."
```

**Setup (for Raw JSON):**
```bash
# Set raw JSON as environment variable
export GCP_SERVICE_KEY='{
  "type": "service_account",
  "project_id": "my-project",
  ...
}'
```

**How it works:**
```python
import os
os.environ["GCP_SERVICE_KEY"] = "eyJhbGciOiJSUzI1NiIsImtpZCI6I..."  # base64 or raw JSON

client = GCPCloudStorageClient(bucket_name="my-bucket")
# Client parses JSON and creates credentials
```

**Advantages:**
- No file system required
- Perfect for CI/CD (CircleCI, GitHub Actions, etc.)
- Supports both base64 and raw JSON

**Disadvantages:**
- Credentials visible in environment (minimal risk with CI secrets)
- Slightly more setup required

---

### Mode 3: Application Default Credentials (Recommended for Production)

Uses credentials from the GCP environment (Workload Identity, Service Account Attached, `gcloud` login, etc.).

**Setup:**
```bash
# Option A: Local development with gcloud
gcloud auth application-default login

# Option B: GKE with Workload Identity (automatic)
# Option C: GCE/Cloud Run with attached service account (automatic)
```

**How it works:**
```python
# No credentials_path or GCP_SERVICE_KEY needed
client = GCPCloudStorageClient(bucket_name="my-bucket")
# Client uses Application Default Credentials
```

**Advantages:**
- Zero configuration in production
- Most secure (credentials managed by GCP)
- Automatic in container environments (GKE, Cloud Run)

**Disadvantages:**
- Requires proper GCP environment setup
- Not available locally unless using `gcloud auth`

---

### Authentication Priority Resolution

When the client is initialized, it checks credentials in this order:

```
1. credentials_path (constructor arg or GOOGLE_APPLICATION_CREDENTIALS env var)
   ↓ (if provided, use service account file)
   
2. GCP_SERVICE_KEY (environment variable)
   ↓ (if provided, parse and use JSON service account)
   
3. Application Default Credentials
   ↓ (fallback to gcloud, Workload Identity, Cloud Run, etc.)
   
   ↓ (if none available, fail with RuntimeError)
```

---

## API Methods

All methods match the `CloudStorageClient` interface.

### upload_file()

Upload a file from the local filesystem to cloud storage.

```python
from cloud_storage_client_api import ObjectInfo

info: ObjectInfo = client.upload_file(
    local_path="/path/to/file.txt",
    key="uploads/file.txt",
    content_type="text/plain"
)

print(f"Uploaded: {info.key}")
print(f"Size: {info.size_bytes} bytes")
print(f"ETag: {info.etag}")
```

**Parameters:**
- `local_path` (str): Path to file on disk
- `key` (str): Destination key/path in GCS
- `content_type` (str, optional): MIME type (e.g., "text/plain", "application/json")

**Returns:**
- `ObjectInfo`: Metadata about the uploaded object

**Raises:**
- `FileNotFoundError`: If local file doesn't exist
- `RuntimeError`: If GCS bucket not configured

---

### upload_bytes()

Upload raw bytes to cloud storage with optional metadata.

```python
data = b"Hello, World!"

info: ObjectInfo = client.upload_bytes(
    data=data,
    key="messages/hello.txt",
    content_type="text/plain",
    metadata={"author": "alice", "version": "1"}
)

print(f"Uploaded: {info.key}, Custom metadata: {info.metadata}")
```

**Parameters:**
- `data` (bytes): Raw bytes to upload
- `key` (str): Destination key/path in GCS
- `content_type` (str, optional): MIME type
- `metadata` (dict, optional): Custom metadata key-value pairs

**Returns:**
- `ObjectInfo`: Metadata about the uploaded object

**Raises:**
- `RuntimeError`: If GCS bucket not configured or dependencies missing

---

### download_bytes()

Download an object from cloud storage as raw bytes.

```python
content: bytes = client.download_bytes(key="uploads/file.txt")

print(f"Downloaded {len(content)} bytes")
print(f"Content: {content.decode()}")
```

**Parameters:**
- `key` (str): Object key/path in GCS

**Returns:**
- bytes: Raw file content

**Raises:**
- `FileNotFoundError`: If object doesn't exist in bucket
- `RuntimeError`: If GCS bucket not configured

---

### list()

List objects in cloud storage with optional prefix filter.

```python
objects = client.list(prefix="uploads/")

for obj in objects:
    print(f"{obj.key}: {obj.size_bytes} bytes, modified: {obj.updated_at}")
```

**Parameters:**
- `prefix` (str): Filter objects by key prefix

**Returns:**
- list[ObjectInfo]: List of matching objects

**Raises:**
- `RuntimeError`: If GCS bucket not configured

---

### delete()

Delete an object from cloud storage.

```python
client.delete(key="uploads/old-file.txt")
print("Object deleted")
```

**Parameters:**
- `key` (str): Object key/path in GCS

**Raises:**
- `FileNotFoundError`: If object doesn't exist
- `RuntimeError`: If GCS bucket not configured

---

### head()

Get metadata for an object without downloading its contents.

```python
info: ObjectInfo | None = client.head(key="uploads/file.txt")

if info:
    print(f"Object exists: {info.key}")
    print(f"Size: {info.size_bytes} bytes")
    print(f"Content-Type: {info.content_type}")
else:
    print("Object does not exist")
```

**Parameters:**
- `key` (str): Object key/path in GCS

**Returns:**
- `ObjectInfo | None`: Metadata if object exists, None otherwise

**Raises:**
- `RuntimeError`: If GCS bucket not configured

---

## ObjectInfo Data Class

All methods return `ObjectInfo` objects containing object metadata:

```python
from cloud_storage_client_api import ObjectInfo
from datetime import datetime

info: ObjectInfo = client.head(key="file.txt")

print(info.key)                    # "file.txt"
print(info.size_bytes)             # 1024 (bytes)
print(info.etag)                   # "abc123def456"
print(info.updated_at)             # datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
print(info.content_type)           # "text/plain"
print(info.metadata)               # {"author": "alice", "version": "1"}
```

**Fields:**
- `key` (str): Object path in bucket
- `size_bytes` (int | None): File size in bytes
- `etag` (str | None): Version identifier (hash)
- `updated_at` (datetime | None): Last modification time
- `content_type` (str | None): MIME type
- `metadata` (dict | None): Custom metadata

---

## Error Handling

The client provides **fail-fast, informative error messages**.

### Configuration Errors (Immediate)

```python
# Missing bucket configuration
try:
    client = GCPCloudStorageClient()  # No bucket name
    client.upload_bytes(b"test", key="test.txt")
except RuntimeError as e:
    print(e)
    # RuntimeError: "GCS bucket is not configured. Set `GCS_BUCKET_NAME` or pass `bucket_name`"
```

### Dependency Errors (At First Use)

```python
# google-cloud-storage not installed
try:
    client = GCPCloudStorageClient(bucket_name="my-bucket")
    client.upload_bytes(b"test", key="test.txt")
except RuntimeError as e:
    print(e)
    # RuntimeError: "google-cloud-storage is not installed. Install dependencies: `uv sync`"
```

### Credential Errors (At First Use)

```python
# Invalid GCP_SERVICE_KEY
os.environ["GCP_SERVICE_KEY"] = "not-valid-json!!!"

try:
    client = GCPCloudStorageClient(bucket_name="my-bucket")
    client.upload_bytes(b"test", key="test.txt")
except RuntimeError as e:
    print(e)
    # RuntimeError: "GCP_SERVICE_KEY must be a valid JSON string or base64-encoded JSON service account key."
```

### Operational Errors (From GCS)

```python
# Object doesn't exist
try:
    client.download_bytes(key="nonexistent.txt")
except FileNotFoundError as e:
    print(e)
    # FileNotFoundError: "Object 'nonexistent.txt' not found in bucket 'my-bucket'"

# Permission denied
try:
    client.upload_bytes(b"test", key="protected/file.txt")
except PermissionError as e:
    print(e)
    # PermissionError: "[403] Forbidden: User does not have storage.objects.create permission"
```

---

## Dependencies

### Required

- `cloud-storage-client-api>=0.1.0` — The abstract interface
- `google-auth>=2.0.0` — GCP authentication
- `google-cloud-storage>=2.10.0` — Google Cloud Storage SDK

### Optional (Development)

- `pytest>=8.4.1` — Test framework
- `pytest-mock>=3.10.0` — Mocking for tests
- `pytest-cov>=6.2.1` — Coverage reporting

### Installation

```bash
# Install all dependencies
uv sync --all-packages

# Or just this component
cd components/gcp_client_impl
uv sync
```

---

## Testing

Unit tests are located in `tests/` and use pytest with mocking.

**Run all tests:**
```bash
uv run pytest components/gcp_client_impl/tests/ -v
```

**Run specific test file:**
```bash
uv run pytest components/gcp_client_impl/tests/test_operations.py -v
```

**With coverage:**
```bash
uv run pytest components/gcp_client_impl/tests/ --cov=gcp_client_impl --cov-report=term-missing
```

### Test Categories

- `test_config.py` — Configuration precedence and environment variable handling
- `test_credentials.py` — Authentication modes (file, env var JSON, ADC)
- `test_storage_client.py` — Storage client initialization and lazy loading
- `test_operations.py` — Upload, download, list, delete, head operations
- `test_object_info.py` — ObjectInfo dataclass validation
- `test_registration.py` — DI auto-registration on import

---

## Usage Examples

### Basic Upload and Download

```python
import gcp_client_impl
from cloud_storage_client_api import get_client

# Auto-registers GCP implementation
client = get_client()

# Upload
info = client.upload_bytes(
    data=b"Hello, GCS!",
    key="test.txt",
    content_type="text/plain"
)
print(f"Uploaded: {info.key}")

# Download
content = client.download_bytes(key="test.txt")
print(f"Downloaded: {content.decode()}")

# Cleanup
client.delete(key="test.txt")
```

### List Objects with Prefix

```python
import gcp_client_impl
from cloud_storage_client_api import get_client

client = get_client()

# Upload multiple files
for i in range(3):
    client.upload_bytes(
        data=f"File {i}".encode(),
        key=f"docs/file-{i}.txt"
    )

# List all objects with prefix
objects = client.list(prefix="docs/")

for obj in objects:
    print(f"{obj.key}: {obj.size_bytes} bytes")
```

### Get Object Metadata

```python
import gcp_client_impl
from cloud_storage_client_api import get_client

client = get_client()

# Get metadata without downloading
info = client.head(key="docs/file-0.txt")

if info:
    print(f"Key: {info.key}")
    print(f"Size: {info.size_bytes} bytes")
    print(f"Type: {info.content_type}")
    print(f"Modified: {info.updated_at}")
else:
    print("Object not found")
```

### Upload with Custom Metadata

```python
import gcp_client_impl
from cloud_storage_client_api import get_client

client = get_client()

# Upload with metadata
info = client.upload_bytes(
    data=b"Important document",
    key="documents/report.pdf",
    content_type="application/pdf",
    metadata={
        "author": "alice",
        "department": "finance",
        "confidential": "true"
    }
)

print(f"Custom metadata: {info.metadata}")
```