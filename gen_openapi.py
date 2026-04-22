#!/usr/bin/env python3
"""Generate OpenAPI spec and save with proper encoding."""

from pathlib import Path
import json
from cloud_storage_service.main import app

spec = app.openapi()
output_path = Path("openapi.json")

with open(output_path, "w", encoding="utf-8", newline="") as f:
    json.dump(spec, f)

print(f"✅ OpenAPI spec saved to {output_path}")
