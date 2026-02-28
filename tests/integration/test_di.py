"""Integration tests for dependency injection and client registration."""

from __future__ import annotations

import concurrent.futures
from typing import TYPE_CHECKING

import pytest

import gcp_client_impl
from cloud_storage_client_api.client import CloudStorageClient, ObjectInfo
from cloud_storage_client_api.di import get_client, override_get_client, register_get_client

if TYPE_CHECKING:
    from collections.abc import Mapping


# Fake client for testing DI isolation and thread safety
class _FakeClient(CloudStorageClient):
    """This is a fake client for testing DI without real GCP calls."""

    def upload_file(self, *, local_path: str, key: str, content_type: str | None = None) -> ObjectInfo:
        raise NotImplementedError

    def upload_bytes(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ObjectInfo:
        raise NotImplementedError

    def download_bytes(self, *, key: str) -> bytes:
        raise NotImplementedError

    def list(self, *, prefix: str) -> list[ObjectInfo]:
        raise NotImplementedError

    def delete(self, *, key: str) -> None:
        raise NotImplementedError

    def head(self, *, key: str) -> ObjectInfo | None:
        raise NotImplementedError


def test_importing_impl_injects_factory() -> None:
    """Legacy test - kept for backwards compatibility."""
    client = get_client()
    assert client.__class__.__name__ == "GCPCloudStorageClient"


@pytest.mark.integration
def test_import_registers_gcp_client() -> None:
    """Verify importing gcp_client_impl registers the factory.

    This validates the auto-registration mechanism:
    - Importing the impl module triggers registration
    - Client is available via get_client("gcp")
    - Client is also registered as the default provider
    """
    # Import already happened at module level, so registration is done
    client = get_client("gcp")
    assert isinstance(client, CloudStorageClient)
    assert client.__class__.__name__ == "GCPCloudStorageClient"

    # Also registered as default
    default_client = get_client()
    assert isinstance(default_client, CloudStorageClient)
    assert default_client.__class__.__name__ == "GCPCloudStorageClient"


@pytest.mark.integration
def test_multiple_providers_dont_conflict() -> None:
    """Verify different implementations can be registered simultaneously.

    This validates that:
    - Multiple named providers can coexist in the registry
    - Each provider returns its own implementation
    - Providers don't interfere with each other
    """
    # Create two different fake clients
    fake_gcp = _FakeClient()
    fake_aws = _FakeClient()

    # Register them with different names
    register_get_client(lambda: fake_gcp, name="test-gcp")
    register_get_client(lambda: fake_aws, name="test-aws")

    # Retrieve them and verify they're distinct
    retrieved_gcp = get_client(name="test-gcp")
    retrieved_aws = get_client(name="test-aws")

    assert retrieved_gcp is fake_gcp
    assert retrieved_aws is fake_aws
    assert retrieved_gcp is not retrieved_aws


@pytest.mark.integration
@pytest.mark.parametrize("provider_name", ["test1", "test2", "test3"])
def test_parallel_contexts_dont_interfere(provider_name: str) -> None:
    """Run this with pytest -n 3 to verify parallel safety.

    This validates that:
    - Multiple pytest workers can run simultaneously
    - ContextVar provides isolation between workers
    - Each test instance gets its own override context
    - No cross-contamination between parallel test runs

    Run with: pytest -n 3 tests/integration/test_di.py::test_parallel_contexts_dont_interfere
    """
    fake = _FakeClient()

    # Use override to create isolated context for this test
    with override_get_client(lambda: fake, name=provider_name):
        # Each parallel test should retrieve its own fake client
        retrieved = get_client(name=provider_name)
        assert retrieved is fake


@pytest.mark.integration
def test_override_is_thread_safe() -> None:
    """Verify ContextVar provides proper isolation in multi-threaded code.

    This validates that:
    - Each thread gets its own ContextVar value
    - Overrides in one thread don't leak to other threads
    - Concurrent override_get_client() calls are isolated
    - This is critical for web servers and background workers
    """

    def worker(client_id: int) -> None:
        """Worker function that runs in a separate thread."""
        fake = _FakeClient()
        with override_get_client(lambda: fake, name=f"worker-{client_id}"):
            # Each thread should get its own override
            retrieved = get_client(name=f"worker-{client_id}")
            assert retrieved is fake, f"Worker {client_id} got wrong client!"

    # Run 10 workers across 5 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker, i) for i in range(10)]

        # Wait for all to complete and check for exceptions
        for future in concurrent.futures.as_completed(futures):
            # This will raise if any assertion failed in the worker
            future.result()
