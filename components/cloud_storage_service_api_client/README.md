# Cloud Storage Service API Client

This package is a Python client for talking to the Cloud Storage Service REST API (the FastAPI backend in this repo). It lets you call the API from Python code instead of using curl.

## What does this do?
- Lets you create a `Client` or `AuthenticatedClient` for the API
- Provides models and functions for each endpoint (auto-generated)
- Supports both sync and async usage

## How to use
```python
from cloud_storage_service_api_client import AuthenticatedClient

client = AuthenticatedClient(base_url="https://cloud-storage-service-mcni.onrender.com", token="your-bearer-token")

# Example: download a file
from cloud_storage_service_api_client.api.storage import download_file
response = download_file.sync(client=client, key="test.txt")
print(response.content)
```

## Notes
- This is a student project. The client is auto-generated from the OpenAPI spec, so check the FastAPI docs for details.
- For more info, see the root README and the FastAPI service docs.
