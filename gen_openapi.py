"""Generate OpenAPI spec and save with proper encoding."""

import json
import sys
from pathlib import Path

from cloud_storage_service.main import app

spec = app.openapi()
output_path = Path("openapi.json")

output_path.write_text(json.dumps(spec, indent=2))

sys.stdout.write(f"✅ OpenAPI spec saved to {output_path}\n")
