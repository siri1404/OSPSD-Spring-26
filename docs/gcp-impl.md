# GCP Implementation

Covers non-obvious behavior. For method signatures, see the [interface reference](../api/interface.md).

## Authentication detail

`credentials_path` takes priority — if set, `GCP_SERVICE_KEY` is ignored entirely. `GCP_SERVICE_KEY` can be raw JSON or base64-encoded JSON; the client tries base64 first and falls back to treating it as raw.

## Error handling

- `download_bytes` and `delete` raise `FileNotFoundError` if the object doesn't exist
- `head` returns `None` instead of raising
- Missing bucket config raises `RuntimeError` before any network call
- Missing `google-cloud-storage` package raises `RuntimeError` on first use, not at import time

## Upload behavior

`upload_file` reads the file and delegates to `upload_bytes`. After upload, metadata is refreshed with a `reload()` call, so the returned `ObjectInfo` reflects what GCS actually stored.