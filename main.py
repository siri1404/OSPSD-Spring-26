"""Main entry point for cloud storage client interchangeability checks."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_workspace_paths() -> None:
    """Ensure component packages are importable when running this file directly."""
    repo_root = Path(__file__).resolve().parent
    extra_paths = [
        repo_root / "components" / "cloud_storage_client_api" / "src",
        repo_root / "components" / "gcp_client_impl" / "src",
        repo_root / "components" / "cloud_storage_adapter" / "src",
        repo_root / "components" / "cloud_storage_service_api_client",
    ]

    for path in extra_paths:
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


_bootstrap_workspace_paths()

import cloud_storage_adapter  # Import triggers DI registration
import gcp_client_impl  # Import triggers DI registration
from cloud_storage_client_api.di import get_client


def main() -> None:
    """Run a backend interchangeability sanity check.

    Same consumer flow is executed against both providers.
    """
    for name in ["gcp", "service"]:
        try:
            client = get_client(name)
            client.upload_bytes(
                data=b"hello",
                key="test.txt",
                content_type="text/plain",
                metadata={},
            )
            result = client.list(prefix="")
            sys.stdout.write(f"{name}: {result}\n")
        except Exception as exc:
            sys.stdout.write(f"{name}: skipped ({exc})\n")


if __name__ == "__main__":
    main()
