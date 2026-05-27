# GCP Cloud Storage Client Implementation

A production-ready Google Cloud Storage (GCS) client that implements the abstract `CloudStorageClient` interface. This package provides complete cloud storage functionality including file upload, download, listing, deletion, and metadata retrieval.

---

## Overview

`gcp_client_impl` is the concrete implementation of the cloud storage interface for Google Cloud Platform. It handles:

- **File Operations:** Upload files, download objects, list by prefix, delete objects
- **Metadata Retrieval:** Get object info without downloading contents
- **Flexible Authentication:** Service account files, environment variables, or Application Default Credentials
- **Configuration Management:** Constructor kwargs, environment variables, or defaults
- **Automatic Registration:** Registers with the dependency injection system on import

---

## Core Class: `GCPCloudStorageClient`

The main class implementing all storage operations against Google Cloud Storage.

```python
from gcp_client_impl.client import GCPCloudStorageClient

# Create client (reads config from environment)
client = GCPCloudStorageClient()

# Or with explicit configuration
client = GCPCloudStorageClient(
    bucket_name="my-bucket",
    project_id="my-project",
    credentials_path="/path/to/key.json"
)
```

---

## Configuration

Configuration follows a **precedence hierarchy**: constructor kwargs override environment variables, which override defaults.

### Configuration Parameters

| Parameter | Env Variable | Default | Required | Description |
|-----------|--------------|---------|----------|-------------|
| `bucket_name` | `GCS_BUCKET_NAME` | None | Yes | Target GCS bucket name |
| `project_id` | `GOOGLE_CLOUD_PROJECT` | None | No | GCP project ID (for ADC) |
| `credentials_path` | `GOOGLE_APPLICATION_CREDENTIALS` | None | No | Path to service account JSON key file |
| - | `GCP_SERVICE_KEY` | None | No | Raw or base64-encoded service account JSON |

### Configuration Examples

**Example 1: Using Constructor Arguments**
```python
client = GCPCloudStorageClient(
    bucket_name="my-storage-bucket",
    project_id="my-gcp-project",
    credentials_path="/home/user/.gcp/service-account-key.json"
)
```

**Example 2: Using Environment Variables**
```bash
export GCS_BUCKET_NAME="my-storage-bucket"
export GOOGLE_CLOUD_PROJECT="my-gcp-project"
export GOOGLE_APPLICATION_CREDENTIALS="/home/user/.gcp/service-account-key.json"
```

Then in code:
```python
client = GCPCloudStorageClient()  # Reads from environment
```

**Example 3: Using Base64-Encoded Credentials (CI/CD)**
```bash
export GCS_BUCKET_NAME="my-storage-bucket"
export GOOGLE_CLOUD_PROJECT="my-gcp-project"
export GCP_SERVICE_KEY="eyJhbGciOiJSUzI1NiIsImtpZCI6I..."  # base64
```