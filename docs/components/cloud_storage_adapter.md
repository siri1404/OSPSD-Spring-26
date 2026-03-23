# Cloud Storage Adapter

This is an HTTP adapter that lets you use the `CloudStorageClient` interface to talk to a remote cloud storage service over HTTP. Basically, it turns API calls into HTTP requests to a FastAPI backend (like the one in this repo).

## What does this do?
- Implements all 6 methods from the `CloudStorageClient` interface
- Uses `httpx` to send requests to the service (upload, download, list, delete, head)
- Converts JSON responses into `ObjectInfo` objects
- Raises `FileNotFoundError` if the object doesn't exist

## How to use
```python
from cloud_storage_adapter import CloudStorageAdapter

adapter = CloudStorageAdapter(
    base_url="http://localhost:8000",  # or your deployed service URL
    token="dev-token-12345",           # Bearer token for auth
)

adapter.upload_bytes(data=b"hello", key="samples/hello.txt", content_type="text/plain")
content = adapter.download_bytes(key="samples/hello.txt")
print(content)
```

## Testing
```bash
uv run pytest components/cloud_storage_adapter/tests -v
```

## Notes
- This is a student project. If you get errors, check your service URL and token.
- For more details, see the root README and the FastAPI service docs.
