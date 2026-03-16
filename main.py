"""Main entry point for the cloud storage project.

This demonstrates basic usage of the GCP cloud storage client library.
"""

from __future__ import annotations

import sys

import gcp_client_impl  # noqa: F401  # Import triggers DI registration
from cloud_storage_client_api.di import get_client


def main() -> None:
    """Demonstrate basic client usage."""
    # Get the registered GCP client
    client = get_client()
    sys.stdout.write(f"Successfully initialized client: {client.__class__.__name__}\n")
    sys.stdout.write("Cloud storage client is ready to use.\n")


if __name__ == "__main__":
    main()
