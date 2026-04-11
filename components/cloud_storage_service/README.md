# Cloud Storage Service (FastAPI)

This is a RESTful API for cloud storage operations, built with FastAPI and designed to work with Google Cloud Storage (GCS) using OAuth 2.0 authentication. It exposes endpoints for uploading, downloading, listing, deleting, and inspecting files in a GCS bucket.

## What does this service do?
- Lets you upload files to a GCS bucket via `/upload`
- Download files with `/download/{key}`
- List files with `/list`
- Delete files with `/delete/{key}`
- Get file metadata with `/head/{key}`
- Health check at `/health` (returns 200 OK if running)
- Handles OAuth 2.0 login and callback for Google authentication

## How it works
- Uses a GCP service account or OAuth token to access your bucket
- All endpoints (except `/health` and `/auth/*`) require a Bearer token
- Returns JSON for metadata and errors, and raw file bytes for downloads

## Example usage (with curl)

**Note:** For local testing, set `DEV_AUTH_TOKEN` in your `.env` file first.

```bash
# Health check (no auth required)
curl https://cloud-storage-service-mcni.onrender.com/health

# Upload a file (replace YOUR_TOKEN with your dev token or OAuth token)
curl -X POST https://cloud-storage-service-mcni.onrender.com/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F key=sample.txt \
  -F file=@sample.txt

# Download a file
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://cloud-storage-service-mcni.onrender.com/download/sample.txt

# List files
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://cloud-storage-service-mcni.onrender.com/list

# Delete a file
curl -X DELETE https://cloud-storage-service-mcni.onrender.com/delete/sample.txt \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Environment variables
- `GCS_BUCKET_NAME` (required): Your GCS bucket name
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS` or `GCP_SERVICE_KEY`: Service account credentials
- `DEV_AUTH_TOKEN`: Token for bypassing OAuth in local/dev testing (must be explicitly set, no default)
- `ENVIRONMENT`: Set to `development` or `test` to enable dev token bypass (defaults to `production`)

## Running locally
1. Install dependencies (see root README)
2. Set up your `.env` file with the above variables
3. Run: `uv run uvicorn cloud_storage_service.main:app --reload`

## Notes
- This is a student project. If you find bugs, check the error handlers in `main.py`.
- For more details, see the root README and the `cloud_storage_api` docs.
