"""Generate OpenAPI spec and save with proper encoding.

Run from the workspace root after installing the cloud_storage_service
component. Writes openapi.json next to the current working directory.

Per peer review #1, the spec reflects the shared cross-team ObjectInfo
contract (object_name, integrity, data_type, ...). Regenerate this file
whenever cloud_storage_service.models or any route signature changes, then
commit the regenerated SDK in tandem.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from cloud_storage_service.main import app


def _generate(output_path: Path) -> None:
    """Write the FastAPI OpenAPI spec to output_path as UTF-8 JSON."""
    spec = app.openapi()
    output_path.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    sys.stdout.write(f"OpenAPI spec saved to {output_path}\n")


if __name__ == "__main__":
    _generate(Path("openapi.json"))
