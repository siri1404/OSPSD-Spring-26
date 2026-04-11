"""Main entry point for cloud storage client interchangeability checks."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def _bootstrap_workspace_paths() -> None:
    """Ensure component packages are importable when running this file directly."""
    repo_root = Path(__file__).resolve().parent
    extra_paths = [
        repo_root / "components" / "gcp_client_impl" / "src",
        repo_root / "components" / "cloud_storage_adapter" / "src",
        repo_root / "components" / "cloud_storage_service_api_client",
    ]

    for path in extra_paths:
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


_bootstrap_workspace_paths()

from cloud_storage_adapter import CloudStorageAdapter
from gcp_client_impl import GCPCloudStorageClient


def main() -> None:
    """Run a lightweight import/instantiation sanity check."""
    clients: list[tuple[str, Callable[[], object]]] = [
        ("gcp", GCPCloudStorageClient),
        ("service", lambda: CloudStorageAdapter(base_url="http://localhost:8000", token="")),
    ]
    for name, ctor in clients:
        try:
            client = ctor()
            sys.stdout.write(f"{name}: initialized {client.__class__.__name__}\n")
        except Exception as exc:
            sys.stdout.write(f"{name}: skipped ({exc})\n")


if __name__ == "__main__":
    main()
