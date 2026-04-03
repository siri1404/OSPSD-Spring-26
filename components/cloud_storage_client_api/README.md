# Cloud Storage Client API

A provider-agnostic interface for cloud storage operations. This package defines the abstract contract that all cloud storage implementations must follow, enabling seamless switching between providers (GCP, AWS, Azure, etc.) without changing client code.

---

## Overview

`cloud_storage_client_api` provides:

- **Abstract Interface:** `CloudStorageClient` ABC defining 6 core operations
- **Data Models:** `ObjectInfo` dataclass for consistent metadata representation
- **Dependency Injection:** Registry-based auto-discovery with thread-safe test isolation
- **Provider Agnostic:** Implementations register themselves; consumers don't care which one

This separation of interface from implementation enables:
- **Loose Coupling:** Code depends on the interface, not specific implementations
- **Easy Testing:** Mock clients or swap implementations with `override_get_client()`
- **Multi-Provider Support:** Both GCP and AWS clients can coexist, selectable by name

---

## ObjectInfo Data Class

All storage operations return `ObjectInfo` containing object metadata.

```python
from cloud_storage_client_api import ObjectInfo

info = ObjectInfo(
    key="documents/report.pdf",
    size_bytes=2048,
    etag="abc-etag-hash",
    updated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
    content_type="application/pdf",
    metadata={"author": "alice", "confidential": "true"}
)
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Object path/ID in storage (required) |
| `size_bytes` | `int \| None` | File size in bytes (optional) |
| `etag` | `str \| None` | Version hash/identifier (optional) |
| `updated_at` | `datetime \| None` | Last modification time (optional) |
| `content_type` | `str \| None` | MIME type (optional) |
| `metadata` | `Mapping[str, str] \| None` | Custom key-value metadata (optional) |

### Properties

- **Immutable:** `frozen=True` dataclass — fields cannot be changed after creation
- **Typed:** Full type hints for IDE support and type checking
- **Flexible:** Only `key` is required; everything else optional

---

## CloudStorageClient Interface

Abstract base class defining the contract all implementations must follow.

### upload_file()

Upload a file from the local filesystem to cloud storage.

```python
from cloud_storage_client_api import get_client

client = get_client()

info = client.upload_file(
    local_path="/path/to/file.pdf",
    key="documents/report.pdf",
    content_type="application/pdf"
)

print(f"Uploaded: {info.key}")
print(f"Size: {info.size_bytes} bytes")
```

**Parameters:**
- `local_path` (str): Path to file on disk
- `key` (str): Destination object key/path in storage
- `content_type` (str, optional): MIME type

**Returns:**
- `ObjectInfo`: Metadata about the uploaded object

**Raises:**
- `FileNotFoundError`: If local file doesn't exist
- Vendor-specific errors: Permission denied, bucket not found, etc.

---

### upload_bytes()

Upload raw bytes to cloud storage with optional custom metadata.

```python
data = b"Important document content"

info = client.upload_bytes(
    data=data,
    key="reports/2026-q1.txt",
    content_type="text/plain",
    metadata={"quarter": "Q1", "year": "2026"}
)

print(f"Uploaded with metadata: {info.metadata}")
```

**Parameters:**
- `data` (bytes): Raw bytes to upload
- `key` (str): Destination object key/path in storage
- `content_type` (str, optional): MIME type
- `metadata` (Mapping[str, str], optional): Custom key-value metadata

**Returns:**
- `ObjectInfo`: Metadata about the uploaded object

**Raises:**
- Vendor-specific errors: Permission denied, quota exceeded, etc.

---

### download_bytes()

Download an object from cloud storage as raw bytes.

```python
content = client.download_bytes(key="documents/report.pdf")

print(f"Downloaded {len(content)} bytes")

# Process as image, JSON, etc.
with open("report.pdf", "wb") as f:
    f.write(content)
```

**Parameters:**
- `key` (str): Object key/path in storage

**Returns:**
- bytes: Complete file contents

**Raises:**
- `FileNotFoundError`: If object doesn't exist
- Vendor-specific errors: Permission denied, etc.

---

### list()

List objects in cloud storage with optional prefix filter.

```python
# List all objects with "documents/" prefix
objects = client.list(prefix="documents/")

for obj in objects:
    print(f"{obj.key}: {obj.size_bytes} bytes, modified {obj.updated_at}")

# Typical output:
# documents/report.pdf: 2048 bytes, modified 2026-03-01 12:00:00+00:00
# documents/summary.txt: 512 bytes, modified 2026-02-28 15:30:00+00:00
```

**Parameters:**
- `prefix` (str): Filter objects by key prefix (e.g., "documents/", "temp/old-")

**Returns:**
- `list[ObjectInfo]`: All matching objects (empty list if none found)

**Raises:**
- Vendor-specific errors: Permission denied, etc.

---

### delete()

Delete an object from cloud storage.

```python
client.delete(key="documents/old-report.pdf")
print("Object deleted successfully")
```

**Parameters:**
- `key` (str): Object key/path in storage

**Returns:**
- `None`

**Raises:**
- `FileNotFoundError`: If object doesn't exist (behavior depends on implementation)
- Vendor-specific errors: Permission denied, etc.

---

### head()

Get metadata about an object without downloading its contents.

```python
info = client.head(key="documents/report.pdf")

if info:
    print(f"Object exists: {info.key}")
    print(f"Size: {info.size_bytes} bytes")
    print(f"Content-Type: {info.content_type}")
    print(f"Modified: {info.updated_at}")
else:
    print("Object does not exist")
```

**Parameters:**
- `key` (str): Object key/path in storage

**Returns:**
- `ObjectInfo | None`: Metadata if object exists, `None` otherwise

**Raises:**
- Vendor-specific errors: Permission denied, etc.

---

## Dependency Injection System

The DI system enables automatic provider registration, swapping, and test isolation.

### Basic Usage: get_client()

Retrieves a registered client implementation.

```python
import cloud_storage_client_impl  # This registers the GCP implementation

from cloud_storage_client_api import get_client

client = get_client()  # Returns the registered GCP client
```

**Parameters:**
- `name` (str, default="default"): Named provider to retrieve

**Returns:**
- `CloudStorageClient`: Client instance from factory

**Raises:**
- `RuntimeError`: If no client registered for the given name

---

### Registration: register_get_client()

Registers a client factory function.

```python
from cloud_storage_client_api import register_get_client

def make_gcp_client() -> CloudStorageClient:
    return GCPCloudStorageClient(bucket_name="my-bucket")

# Register as the default provider
register_get_client(make_gcp_client)

# Or with a custom name
register_get_client(make_gcp_client, name="gcp")
```

**Parameters:**
- `fn` (Callable): Factory function returning `CloudStorageClient`
- `name` (str, default="default"): Provider name

**Thread Safety:**
- Uses `RLock` for safe concurrent registration

---

### Unregistration: unregister_get_client()

Removes a registered provider.

```python
from cloud_storage_client_api import unregister_get_client

# Unregister the default provider
unregister_get_client()

# Or a named provider
unregister_get_client(name="gcp")
```

**Parameters:**
- `name` (str, default="default"): Provider name

---

### Test Isolation: override_get_client()

Temporarily replaces a provider for testing (thread-safe with context variables).

```python
import pytest
from cloud_storage_client_api import get_client, override_get_client

class MockClient(CloudStorageClient):
    # Implementation...
    pass

def test_upload_workflow():
    """Test with a mock client instead of the real GCP client."""
    mock = MockClient()
    
    with override_get_client(lambda: mock):
        # Inside this block, get_client() returns the mock
        client = get_client()
        info = client.upload_bytes(data=b"test", key="test.txt")
        assert info.key == "test.txt"
    
    # Outside the block, get_client() returns the original registered client
```

**Key Features:**
- **Context Manager:** Automatic cleanup when exiting the `with` block
- **Thread-Safe:** Uses `ContextVar` for isolating overrides per thread/task
- **Nestable:** Supports nested overrides that restore properly
- **Pytest Compatible:** Perfect for test fixtures

**How It Works:**
```python
# No override - uses global registry
client = get_client()

# With override - uses temporary context-local value
with override_get_client(lambda: mock):
    client = get_client()  # Returns mock

# Override removed - back to global registry
client = get_client()
```

---

### Named Providers

Support multiple implementations simultaneously, useful for multi-cloud strategies.

```python
from cloud_storage_client_api import register_get_client, get_client

# Register both GCP and S3 implementations
register_get_client(make_gcp_client, name="gcp")
register_get_client(make_s3_client, name="s3")

# Use them independently
gcp_client = get_client(name="gcp")
s3_client = get_client(name="s3")

# Sync a file between clouds
data = s3_client.download_bytes(key="source.txt")
gcp_client.upload_bytes(data=data, key="destination.txt")
```

---

## Usage Examples

### Example 1: Basic Usage (With Auto-Registered Implementation)

```python
import cloud_storage_client_impl  # Auto-registers GCP implementation

from cloud_storage_client_api import get_client

# Simple workflow
client = get_client()

# Upload
info = client.upload_bytes(
    data=b"Hello, Cloud Storage!",
    key="greeting.txt",
    content_type="text/plain"
)
print(f"Uploaded: {info.key}")

# Download
content = client.download_bytes(key="greeting.txt")
print(f"Downloaded: {content.decode()}")

# Cleanup
client.delete(key="greeting.txt")
```

### Example 2: Using Named Providers

```python
from cloud_storage_client_api import register_get_client, get_client

# Register implementations with different names
register_get_client(
    lambda: GCPCloudStorageClient(bucket_name="prod-bucket"),
    name="production"
)
register_get_client(
    lambda: GCPCloudStorageClient(bucket_name="staging-bucket"),
    name="staging"
)

# Use based on environment
environment = os.getenv("ENVIRONMENT", "staging")
client = get_client(name=environment)

client.upload_bytes(data=data, key="app.log")
```

### Example 3: Testing with Mock Implementation

```python
import pytest
from cloud_storage_client_api import get_client, override_get_client, CloudStorageClient, ObjectInfo

class InMemoryClient(CloudStorageClient):
    """Mock client storing objects in memory."""
    
    def __init__(self):
        self.storage: dict[str, bytes] = {}
    
    def upload_bytes(self, *, data: bytes, key: str, 
                     content_type: str | None = None, 
                     metadata: dict[str, str] | None = None) -> ObjectInfo:
        self.storage[key] = data
        return ObjectInfo(key=key, size_bytes=len(data), content_type=content_type)
    
    def download_bytes(self, *, key: str) -> bytes:
        return self.storage[key]
    
    # ... implement other methods ...

@pytest.fixture
def mock_storage():
    """Fixture providing mock storage client."""
    mock = InMemoryClient()
    with override_get_client(lambda: mock):
        yield mock

def test_data_processing(mock_storage):
    """Test without touching real cloud storage."""
    client = get_client()
    
    # This goes to mock_storage, not real GCS
    client.upload_bytes(data=b"test", key="test.txt")
    
    # Assertions
    assert b"test" in mock_storage.storage.values()
```

### Example 4: Listing and Filtering Objects

```python
client = get_client()

# List all objects with a specific prefix
logs = client.list(prefix="logs/2026-03/")

# Filter to recent logs
recent = [obj for obj in logs if obj.updated_at.day >= 15]

for obj in recent:
    print(f"Processing: {obj.key}")
    content = client.download_bytes(key=obj.key)
    # Process log data...
```

---

## For Implementers

If you're building a cloud storage client (GCP, AWS, Azure, MinIO, etc.):

### Step 1: Create Implementation Module

```python
# my_cloud_impl/src/my_cloud_impl/client.py

from cloud_storage_client_api import CloudStorageClient, ObjectInfo

class MyCloudClient(CloudStorageClient):
    """Concrete implementation for 'My Cloud' provider."""
    
    def __init__(self, config):
        self.config = config
    
    def upload_file(self, *, local_path: str, key: str, content_type: str | None = None) -> ObjectInfo:
        # Read file and delegate to upload_bytes
        with open(local_path, "rb") as f:
            data = f.read()
        return self.upload_bytes(data=data, key=key, content_type=content_type)
    
    def upload_bytes(self, *, data: bytes, key: str, content_type: str | None = None, 
                     metadata: dict[str, str] | None = None) -> ObjectInfo:
        # Call provider API to upload
        ...
        return ObjectInfo(key=key, size_bytes=len(data), content_type=content_type)
    
    # ... implement other methods ...
```

### Step 2: Create Registration Module

```python
# my_cloud_impl/src/my_cloud_impl/__init__.py

from cloud_storage_client_api import register_get_client
from my_cloud_impl.client import MyCloudClient

def _make_client() -> MyCloudClient:
    """Factory function for DI system."""
    return MyCloudClient(config=...)

# Auto-register on import
register_get_client(_make_client, name="my-cloud")
register_get_client(_make_client)  # Also as default
```

### Step 3: Document Configuration and Error Handling

See [gcp_client_impl/README.md](../gcp_client_impl/README.md) for a detailed example.

### Requirements Checklist

- ✅ Inherit from `CloudStorageClient`
- ✅ Implement all 6 abstract methods
- ✅ Return `ObjectInfo` from upload/list/head operations
- ✅ Raise `FileNotFoundError` for missing objects (if applicable)
- ✅ Create factory function and register with `register_get_client()`
- ✅ Add comprehensive README documenting your implementation

---

## Testing

### Run Tests

```bash
# All tests
uv run pytest components/cloud_storage_client_api/tests/ -v

# With coverage
uv run pytest components/cloud_storage_client_api/tests/ --cov=cloud_storage_client_api
```

### Test Categories

- **test_client_api.py** — ObjectInfo immutability, interface contract verification
- **test_get_client.py** — DI registry, named providers, overrides, error handling

### Writing Tests for Your Implementation

```python
import pytest
from cloud_storage_client_api import override_get_client
from your_impl import make_client

@pytest.fixture
def client():
    """Provide a real client configured for testing."""
    test_client = make_client(bucket="test-bucket")
    with override_get_client(lambda: test_client):
        yield test_client

def test_upload_download_roundtrip(client):
    """Test upload and download work together."""
    data = b"Hello, World!"
    info = client.upload_bytes(data=data, key="test.txt")
    
    downloaded = client.download_bytes(key="test.txt")
    assert downloaded == data
```

---

## See Also

- [gcp_client_impl README](../gcp_client_impl/README.md) — Concrete GCP implementation example
- [Design Document](../../docs/design.md) — Architecture and design patterns
- [Contributing Guide](../../docs/CONTRIBUTING.md) — Development workflow
- [Testing Guide](../../docs/testing.md) — Test strategies and markers
