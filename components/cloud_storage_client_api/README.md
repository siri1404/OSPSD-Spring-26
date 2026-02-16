# Cloud Storage Client API

## What is this?

This package defines the interface for cloud storage clients. It's an abstract base class (`CloudStorageClient`) that says "here's what a storage client should be able to do" - without caring whether you're using GCP, AWS, or anything else.

## Why separate it?

So you can write code that uses a storage client without knowing (or caring) which provider it's actually using. Implementation details stay in the implementation.

## The Interface

Six methods that do what you'd expect:

- **`upload_file(local_path, key, content_type)`** - Upload a file from  computer
- **`upload_bytes(data, key, content_type, metadata)`** - Upload raw bytes
- **`download_bytes(key)`** - Download something
- **`list(prefix)`** - List objects with a prefix
- **`delete(key)`** - Delete an object
- **`head(key)`** - Get info about an object without downloading it

All methods use keyword-only args (`*,`) to keep things explicit.

## ObjectInfo

A simple data class that holds object metadata:

```python
@dataclass(frozen=True)
class ObjectInfo:
    key: str                              # The object ID
    size_bytes: int | None = None         # How big it is
    etag: str | None = None               # Version hash
    updated_at: datetime | None = None    # When it changed
    content_type: str | None = None       # MIME type
    metadata: Mapping[str, str] | None = None  # Custom stuff
```

## Using It

```python
from cloud_storage_client_api import get_client

client = get_client()  # Gets whatever implementation is registered
info = client.upload_bytes(data=b"hello", key="test.txt")
print(f"Uploaded: {info.key}")

content = client.download_bytes(key="test.txt")
client.delete(key="test.txt")
```

## How DI Works

When you import the implementation (e.g., `cloud_storage_client_impl`), it registers itself. So after that, `get_client()` returns the GCP client. You don't need to pass it around or wire it up - it's automatic.

```python
import cloud_storage_client_impl  # This registers the GCP implementation

from cloud_storage_client_api import get_client
client = get_client()  # Now it's the GCP client
```

## For Implementers

If you're building a GCP (or AWS, or Azure) client:

1. Inherit from `CloudStorageClient`
2. Implement all 6 methods
3. Return `ObjectInfo` objects from upload/download/head
4. Register your factory with `register_get_client()`
5. Done - consumers just call `get_client()`

## Testing

```bash
uv run pytest components/cloud_storage_client_api/tests/
```
