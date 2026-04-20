# gemini-ai-client-impl

Gemini AI client implementation with tool calling for cloud storage operations.

## Overview

This component integrates Google's Gemini API as a concrete implementation of the `AiClientApi` interface. It provides natural language access to cloud storage operations through tool calling.

## Features

- **Tool Calling**: Enables Gemini to directly execute cloud storage operations (upload, download, list, delete, summarize files).
- **PDF Handling**: Special support for PDF documents passed to Gemini as document parts for native processing.
- **Error Handling**: Gracefully handles storage errors and returns human-readable messages instead of propagating exceptions.
- **Context Injection**: Supports optional context (e.g., default container name) that is automatically injected into tool calls when not explicitly provided.

## Tools

The Gemini client has access to the following tools:

- `list_files` — List files in a container with optional prefix filtering.
- `get_file_info` — Get metadata for a single file.
- `delete_file` — Delete a file from storage.
- `upload_file` — Upload a local file to storage.
- `download_file` — Download a file from storage.
- `summarize_file` — Get file content or base64-encoded PDFs for AI processing.

## Configuration

Set the following environment variable:

```
GEMINI_API_KEY=<your-gemini-api-key>
```

Pass a `CloudStorageClient` instance to the constructor:

```python
from gemini_ai_client_impl import GeminiAiClient
from gcp_client_impl import GCPCloudStorageClient

storage = GCPCloudStorageClient()
ai_client = GeminiAiClient(storage_client=storage)

response = ai_client.send_message("List files in my bucket", context={"container": "my-bucket"})
```

## Implementation Details

- Tool declarations and implementations are in `tools.py`.
- The client loop caps iterations at 10 to prevent infinite loops.
- PDFs returned from `summarize_file` are sent back to Gemini as document parts for native processing.
