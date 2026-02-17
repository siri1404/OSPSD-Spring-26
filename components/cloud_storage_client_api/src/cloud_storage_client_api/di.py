from __future__ import annotations

from collections.abc import Callable

from cloud_storage_client_api.client import CloudStorageClient

GetClient = Callable[[], CloudStorageClient]
_get_client: GetClient | None = None


def register_get_client(fn: GetClient) -> None:
    global _get_client
    _get_client = fn


def get_client() -> CloudStorageClient:
    if _get_client is None:
        raise RuntimeError(
            "No CloudStorageClient implementation injected. "
            "Import an implementation package first (e.g. `import gcp_cloud_storage_client_impl`)."
        )
    return _get_client()
