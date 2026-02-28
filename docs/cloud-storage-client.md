# Cloud Storage Interface

Reference for `ObjectInfo` fields and method signatures.

## ObjectInfo

| Field | Type | Description |
|---|---|---|
| `key` | `str` | Object path in storage |
| `size_bytes` | `int | None` | Size in bytes |
| `etag` | `str | None` | Version hash |
| `updated_at` | `datetime | None` | Last modified |
| `content_type` | `str | None` | MIME type |
| `metadata` | `Mapping[str, str] | None` | Custom metadata |

## Methods

| Method | Returns | Raises |
|---|---|---|
| `upload_file(local_path, key, content_type)` | `ObjectInfo` | `FileNotFoundError` if local file missing |
| `upload_bytes(data, key, content_type, metadata)` | `ObjectInfo` | - |
| `download_bytes(key)` | `bytes` | `FileNotFoundError` if object missing |
| `list(prefix)` | `list[ObjectInfo]` | - |
| `delete(key)` | `None` | `FileNotFoundError` if object missing |
| `head(key)` | `ObjectInfo | None` | - |