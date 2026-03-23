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
| `size_bytes` | `int | None` | File size in bytes (optional) |
| `etag` | `str | None` | Version hash/identifier (optional) |
| `updated_at` | `datetime | None` | Last modification time (optional) |
| `content_type` | `str | None` | MIME type (optional) |
| `metadata` | `Mapping[str, str] | None` | Custom key-value metadata (optional) |

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