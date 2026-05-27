"""Main entry point for cloud storage client interchangeability checks.

Verifies that the GCP-direct client and the service-backed adapter can both
be imported and instantiated. Useful as a smoke check after a fresh uv sync
and as the integration-target referenced by the structural E2E tests.
"""

from __future__ import annotations

import logging
import sys
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Workspace bootstrap
# ---------------------------------------------------------------------------


def _bootstrap_workspace_paths() -> None:
    """Ensure component packages are importable when running this file directly."""
    repo_root = Path(__file__).resolve().parent
    extra_paths = (
        repo_root / "components" / "gcp_client_impl" / "src",
        repo_root / "components" / "cloud_storage_adapter" / "src",
        repo_root / "components" / "cloud_storage_service_api_client",
    )

    for path in extra_paths:
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


_bootstrap_workspace_paths()

# Imports below depend on the workspace bootstrap above.
from cloud_storage_adapter import CloudStorageAdapter
from gcp_client_impl import GCPCloudStorageClient

# ---------------------------------------------------------------------------
# Smoke check
# ---------------------------------------------------------------------------


def _smoke_check_clients() -> int:
    """Instantiate each known client and report success or skip reason.

    Returns:
        0 if every client either initialized cleanly or was skipped with a
        non-fatal expected error; 1 if any client raised an unexpected error.
    """
    clients: list[tuple[str, Callable[[], object]]] = [
        ("gcp", GCPCloudStorageClient),
        (
            "service",
            lambda: CloudStorageAdapter(
                base_url="http://localhost:8000",
                token="",
            ),
        ),
    ]

    failures = 0
    for name, ctor in clients:
        try:
            client = ctor()
        except (ValueError, RuntimeError, ImportError, ConnectionError) as exc:
            sys.stdout.write(f"{name}: skipped ({exc})\n")
            continue
        except Exception:
            logger.exception("%s: unexpected initialization failure", name)
            failures += 1
            continue

        sys.stdout.write(f"{name}: initialized {client.__class__.__name__}\n")
        # Best-effort cleanup if the client exposes one (no-op otherwise).
        with suppress(AttributeError):
            client.close()  # type: ignore[attr-defined]

    return 0 if failures == 0 else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run a lightweight import/instantiation sanity check."""
    sys.exit(_smoke_check_clients())


if __name__ == "__main__":
    main()
