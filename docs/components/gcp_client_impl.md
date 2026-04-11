# GCP Cloud Storage Client Implementation

A Google Cloud Storage implementation of the shared `cloud_storage_api` contract.

## Overview
`gcp_client_impl` provides `GCPCloudStorageClient`, a concrete implementation of `CloudStorageClient` from the shared package. It supports:

- Uploading from local files and binary file objects
- Downloading objects to local files
- Listing objects by prefix
- Deleting objects
- Fetching object metadata
- Multiple auth modes: OAuth token, service account file, service account JSON, ADC

## Constructor
```python
from gcp_client_impl.client import GCPCloudStorageClient

client = GCPCloudStorageClient(
    project_id="my-project",          # optional
    credentials_path="/path/key.json",  # optional
    oauth_token="ya29....",           # optional
)
```

Constructor parameters:

- `project_id: str | None`
- `credentials_path: str | None`
- `oauth_token: str | None`

Important: there is no `bucket_name` constructor argument. The container/bucket is passed per method.

## Shared API Methods
All methods follow the shared `CloudStorageClient` interface:

```python
from io import BytesIO

container = "my-bucket"

# Upload local file
uploaded = client.upload_file(
    container=container,
    local_path="local/report.pdf",
    remote_path="reports/2026/report.pdf",
)

# Upload binary file-like object
uploaded_obj = client.upload_obj(
    container=container,
    file_obj=BytesIO(b"hello"),
    remote_path="notes/hello.txt",
)

# Download to local file path
info = client.download_file(
    container=container,
    object_name="reports/2026/report.pdf",
    file_name="downloads/report.pdf",
)

# List by prefix
objects = client.list_files(container=container, prefix="reports/2026/")

# Delete object
delete_result = client.delete_file(container=container, object_name="notes/hello.txt")

# Get object metadata
meta = client.get_file_info(container=container, object_name="reports/2026/report.pdf")
```

## ObjectInfo Model
Operations return shared `ObjectInfo` values.

Key fields used by this implementation:

- `object_name`
- `version_id`
- `data_type`
- `integrity`
- `encryption`
- `storage_tier`
- `size_bytes`
- `updated_at`
- `metadata`

Example:

```python
meta = client.get_file_info(container="my-bucket", object_name="reports/q1.xlsx")
print(meta.object_name)
print(meta.integrity)
print(meta.data_type)
print(meta.storage_tier)
```

## Exceptions
This implementation raises shared exceptions from `cloud_storage_api.exceptions`, including:

- `AuthenticationError`
- `ContainerNotFoundError`
- `InvalidContainerError`
- `InvalidObjectNameError`
- `InvalidFileObjectError`
- `LocalFileAccessError`
- `ObjectNotFoundError`
- `StorageBackendError`

Typical behaviors:

- Empty container/object names raise validation exceptions.
- Missing local paths raise `LocalFileAccessError`.
- Missing remote objects raise `ObjectNotFoundError`.
- Permission denied or invalid credentials raise `AuthenticationError`.
- Credential/dependency/backend issues raise `StorageBackendError`.

## Authentication Resolution
Credential resolution order:

- `oauth_token` / `GCP_OAUTH_TOKEN`
- `credentials_path` / `GOOGLE_APPLICATION_CREDENTIALS`
- `GCP_SERVICE_KEY` (raw JSON or base64 JSON)
- Application Default Credentials (ADC)

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON key file |
| `GCP_SERVICE_KEY` | Raw or base64-encoded service account JSON |
| `GCP_OAUTH_TOKEN` | OAuth 2.0 access token |

Note: `GCS_BUCKET_NAME` is NOT used by this client. The bucket/container is passed per method call.

## Dependencies
Required runtime dependencies:

- `cloud-storage-api`
- `google-cloud-storage`
- `google-auth`

## Running Tests
```bash
uv run pytest components/gcp_client_impl/tests/ -v
```

## Component Role
This package is the provider-specific implementation layer. It translates the provider-neutral `cloud_storage_api` contract into Google Cloud Storage SDK operations.