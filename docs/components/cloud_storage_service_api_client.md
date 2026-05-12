# cloud-storage-service-api-client
A client library for accessing Cloud Storage Service API

Usage
First, create a client:

from cloud_storage_service_api_client import Client

client = Client(base_url="https://api.example.com")


If the endpoints you're going to hit require authentication, use AuthenticatedClient instead:

from cloud_storage_service_api_client import AuthenticatedClient

client = AuthenticatedClient(base_url="https://api.example.com", token="SuperSecretToken")


Now call your endpoint and use your models:

from cloud_storage_service_api_client.models import ObjectInfoResponse, ListResponse
from cloud_storage_service_api_client.api.storage import (
    upload_file_upload_post,
    list_objects_list_get,
    download_file_download_key_get,
    delete_object_delete_key_delete,
    head_object_head_key_get,
)
from cloud_storage_service_api_client.types import Response

with client as client: # List objects result: ListResponse = list_objects_list_get.sync(client=client, prefix="docs/")

Or get full response details
response: Response[ListResponse] = list_objects_list_get.sync_detailed(client=client, prefix="docs/")


Or do the same thing with an async version:

async with client as client:
    result: ListResponse = await list_objects_list_get.asyncio(client=client, prefix="docs/")
    response: Response[ListResponse] = await list_objects_list_get.asyncio_detailed(client=client, prefix="docs/")

By default, when you're calling an HTTPS API it will attempt to verify that SSL is working correctly. Using certificate verification is highly recommended most of the time, but sometimes you may need to authenticate to a server (especially an internal server) using a custom certificate bundle.

client = AuthenticatedClient(
    base_url="https://internal_api.example.com",
    token="SuperSecretToken",
    verify_ssl="/path/to/certificate_bundle.pem",
)

You can also disable certificate validation altogether, but beware that this is a security risk.

client = AuthenticatedClient(
    base_url="https://internal_api.example.com",
    token="SuperSecretToken",
    verify_ssl=False
)

Things to know:

Every path/method combo becomes a Python module with four functions:
sync: Blocking request that returns parsed data (if successful) or None
sync_detailed: Blocking request that always returns a Request, optionally with parsed set if the request was successful.
asyncio: Like sync but async instead of blocking
asyncio_detailed: Like sync_detailed but async instead of blocking
All path/query params, and bodies become method arguments.
If your endpoint had any tags on it, the first tag will be used as a module name for the function (e.g. storage, authentication, ai)
Any endpoint which did not have a tag will be in cloud_storage_service_api_client.api.default
Advanced customizations
There are more settings on the generated Client class which let you control more runtime behavior, check out the docstring on that class for more info. You can also customize the underlying httpx.Client or httpx.AsyncClient (depending on your use-case):

from cloud_storage_service_api_client import Client

def log_request(request): print(f"Request event hook: {request.method} {request.url} - Waiting for response")

def log_response(response): request = response.request print(f"Response event hook: {request.method} {request.url} - Status {response.status_code}")

client = Client( base_url="https://api.example.com", httpx_args={"event_hooks": {"request": [log_request], "response": [log_response]}}, )

Or get the underlying httpx client to modify directly with client.get_httpx_client() or client.get_async_httpx_client()

You can even set the httpx client directly, but beware that this will override any existing settings (e.g., base_url):

import httpx
from cloud_storage_service_api_client import Client

client = Client( base_url="https://api.example.com", )

Note that base_url needs to be re-set, as would any shared cookies, headers, etc.
client.set_httpx_client(httpx.Client(base_url="https://api.example.com", proxies="http://localhost:8030"))


Building / publishing this package
This project uses Hatchling as the build backend. To build:

Update the metadata in pyproject.toml (e.g. authors, version)
Build a wheel with uv build or python -m build
Install from the workspace: this package is a uv workspace member and is auto-installed via uv sync --all-packages
