# GCP Cloud Storage Client

GCS implementation of `CloudStorageClient`.

## Configuration

| Constructor arg | Env var fallback | Description |
|---|---|---|
| `bucket_name` | `GCS_BUCKET_NAME` | Target bucket |
| `project_id` | `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `credentials_path` | `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON |
| - | `GCP_SERVICE_KEY` | Raw or base64-encoded service account JSON |

## Authentication

Priority order:

1. `credentials_path` / `GOOGLE_APPLICATION_CREDENTIALS` — path to a key file
2. `GCP_SERVICE_KEY` — accepts raw JSON or base64-encoded JSON
3. Default credentials — `gcloud` login, Workload Identity, etc.

## Dependencies
```bash
uv sync
```

Raises `RuntimeError` at runtime if `google-cloud-storage` isn't installed.