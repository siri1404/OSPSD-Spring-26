# Cloud Storage Service API Client

Auto-generated Python client for the Cloud Storage Service REST API.

## Overview
This package provides a type-safe HTTP client for communicating with the cloud_storage_service FastAPI backend. It was generated from the service's OpenAPI specification (openapi.json) using openapi-python-client.

Do not edit this package manually. If the service API changes, regenerate the client:

```bash
openapi-python-client generate --path openapi.json
```

## What it provides
- Client and AuthenticatedClient classes for HTTP communication
- Typed request/response models for all endpoints
- Sync and async helpers for every endpoint
- Used internally by cloud_storage_adapter to proxy requests

## Endpoints covered

| Module | Endpoint | Method |
|---|---|---|
| upload_file_upload_post | POST /upload | Upload a file |
| download_file_download_key_get | GET /download/{key} | Download a file |
| list_objects_list_get | GET /list | List objects by prefix |
| delete_object_delete_key_delete | DELETE /delete/{key} | Delete an object |
| head_object_head_key_get | GET /head/{key} | Get object metadata |
| health_check_health_get | GET /health | Health check |
| oauth_login_auth_login_post | POST /auth/login | Initiate OAuth login |
| oauth_callback_auth_callback_get | GET /auth/callback | Handle OAuth callback |

All storage endpoints accept an optional container query parameter.

## Usage
```python
from cloud_storage_service_api_client import AuthenticatedClient
from cloud_storage_service_api_client.api.storage import upload_file_upload_post
from cloud_storage_service_api_client.models import BodyUploadFileUploadPost

client = AuthenticatedClient(
	base_url="https://cloud-storage-service-mcni.onrender.com",
	token="your-bearer-token",
)

body = BodyUploadFileUploadPost(file=b"hello", key="test.txt")
response = upload_file_upload_post.sync_detailed(client=client, body=body)
print(response.status_code)
```

## Component Role
This package is the mechanical HTTP layer between the cloud_storage_adapter and the cloud_storage_service. It handles serialization, authentication headers, and response parsing. Application code should use the adapter (which implements the shared CloudStorageClient interface) rather than calling this client directly.