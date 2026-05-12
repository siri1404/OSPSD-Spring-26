# Cloud Storage Service (FastAPI)

This is a RESTful API for cloud storage operations, built with FastAPI and designed to work with Google Cloud Storage (GCS) using OAuth 2.0 authentication. It exposes endpoints for uploading, downloading, listing, deleting, and inspecting files in a GCS bucket, plus an AI-powered natural language interface and Prometheus telemetry.

## What does this service do?
- Upload files to a GCS bucket via `/upload`
- Download files with `/download/{key}`
- List files with `/list`
- Delete files with `/delete/{key}`
- Get file metadata with `/head/{key}`
- AI-powered natural language interface at `/ai/chat` (with tool calling)
- Prometheus metrics at `/metrics`
- Health check at `/health` (returns 200 OK if running)
- Root status at `/`
- OAuth 2.0 login (`/auth/login`), callback (`/auth/callback`), and logout (`/auth/logout`)
- Chat notifications via Slack on storage events and AI actions

## How it works
- Uses a GCP service account or OAuth token to access your bucket
- All endpoints (except `/health`, `/`, and `/auth/*`) require a Bearer token
- Returns JSON for metadata and errors, and raw file bytes for downloads
- AI chat endpoint dispatches tool calls to the storage client via Gemini
- Prometheus middleware emits latency, success/failure, and AI tool call metrics

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

# AI chat
curl -X POST https://cloud-storage-service-mcni.onrender.com/ai/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Container: your-bucket-name" \
  -d '{"prompt": "list all files in the bucket"}'

# Prometheus metrics (no auth required)
curl https://cloud-storage-service-mcni.onrender.com/metrics
```

## Environment variables
- `GCS_BUCKET_NAME` (required): Your GCS bucket name
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS` or `GCP_SERVICE_KEY`: Service account credentials
- `GEMINI_API_KEY`: Google Gemini API key for AI chat
- `SLACK_BOT_TOKEN`: Slack bot token for chat notifications
- `CHAT_CHANNEL_ID`: Slack channel ID for notifications
- `DEV_AUTH_TOKEN`: Token for bypassing OAuth in local/dev testing (must be explicitly set, no default)
- `ENVIRONMENT`: Set to `development` or `test` to enable dev token bypass (defaults to `production`)

## Running locally
1. Install dependencies (see root README)
2. Set up your `.env` file with the above variables
3. Run: `uv run uvicorn cloud_storage_service.main:app --reload`

## Notes
- This is a student project. If you find bugs, check the error handlers in `main.py`.
- For more details, see the root README and the `cloud_storage_api` docs.
