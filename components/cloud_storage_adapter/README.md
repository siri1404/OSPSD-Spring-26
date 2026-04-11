# Cloud Storage Adapter

HTTP adapter implementing the shared CloudStorageClient interface by proxying requests to the cloud storage FastAPI service via the auto-generated OpenAPI client.

## What does this do?
- Implements all 6 methods from the shared CloudStorageClient ABC:
  - upload_file
  - upload_obj
  - download_file
  - list_files
  - delete_file
  - get_file_info
- Uses the generated cloud_storage_service_api_client for all HTTP calls (no raw httpx)
- Converts service responses into shared ObjectInfo objects
- Maps HTTP errors to shared domain exceptions (ObjectNotFoundError, StorageBackendError, AuthenticationError, etc.)

## How to use
```python
from io import BytesIO

from cloud_storage_adapter import CloudStorageAdapter

adapter = CloudStorageAdapter(
    base_url="https://cloud-storage-service-mcni.onrender.com",
    token="your-bearer-token",
)

container = "my-bucket"

# Upload a file-like object
info = adapter.upload_obj(
    container=container,
    file_obj=BytesIO(b"hello"),
    remote_path="samples/hello.txt",
)
print(f"Uploaded: {info.object_name}, Size: {info.size_bytes}")

# Download to local file
download_info = adapter.download_file(
    container=container,
    object_name="samples/hello.txt",
    file_name="downloaded.txt",
)

# List files
objects = adapter.list_files(container=container, prefix="samples/")
for obj in objects:
    print(f"{obj.object_name} ({obj.size_bytes} bytes)")

# Get metadata
meta = adapter.get_file_info(container=container, object_name="samples/hello.txt")
print(f"Integrity: {meta.integrity}, Type: {meta.data_type}")

# Delete
result = adapter.delete_file(container=container, object_name="samples/hello.txt")
print(f"Deleted: {result['deleted']}")
```

## Testing
```bash
uv run pytest components/cloud_storage_adapter/tests -v
```

## Component Role
This package is the HTTP adapter layer. It makes the remote cloud storage service usable through the same CloudStorageClient contract as the local gcp_client_impl, enabling location transparency: consumer code works identically with either implementation.
