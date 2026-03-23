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

```bash
# Health check
curl https://cloud-storage-service-mcni.onrender.com/health

# Upload a file
curl -X POST https://cloud-storage-service-mcni.onrender.com/upload \
  -H "Authorization: Bearer dev-token-12345" \
  -F key=sample.txt \
  -F file=@sample.txt

# Download a file
curl -H "Authorization: Bearer dev-token-12345" \
  https://cloud-storage-service-mcni.onrender.com/download/sample.txt

# List files
curl -H "Authorization: Bearer dev-token-12345" \
  https://cloud-storage-service-mcni.onrender.com/list

# Delete a file
curl -X DELETE https://cloud-storage-service-mcni.onrender.com/delete/sample.txt \
  -H "Authorization: Bearer dev-token-12345"
```

## Environment variables
- `GCS_BUCKET_NAME` (required): Your GCS bucket name
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS` or `GCP_SERVICE_KEY`: Service account credentials
- `DEV_ACCESS_TOKEN`: Token for local/dev testing (default: `dev-token-test`)

## Running locally
1. Install dependencies (see root README)
2. Set up your `.env` file with the above variables
3. Run: `uv run uvicorn cloud_storage_service.main:app --reload`

## Notes
- This is a student project. If you find bugs, check the error handlers in `main.py`.
- For more details, see the root README and the `cloud_storage_client_api` docs.
