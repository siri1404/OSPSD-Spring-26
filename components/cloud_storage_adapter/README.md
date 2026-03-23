# Cloud Storage Adapter

HTTP adapter that implements the `CloudStorageClient` interface by calling the
`cloud_storage_service` REST API.

## What It Does

- Implements all six `CloudStorageClient` methods
- Talks to service endpoints over HTTP using `httpx`
- Converts API JSON payloads into `ObjectInfo`
- Preserves expected interface semantics (`FileNotFoundError` on missing objects)

## Usage

```python
from cloud_storage_adapter import CloudStorageAdapter

adapter = CloudStorageAdapter(
    base_url="http://localhost:8000",
    token="dev-token-12345",
)

adapter.upload_bytes(data=b"hello", key="samples/hello.txt", content_type="text/plain")
content = adapter.download_bytes(key="samples/hello.txt")
print(content)
```

## Testing

```bash
uv run pytest components/cloud_storage_adapter/tests -v
```
