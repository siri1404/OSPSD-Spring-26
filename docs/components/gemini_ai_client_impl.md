# Gemini AI Client Implementation

Concrete AI client using Google's Gemini API with tool calling for cloud storage operations.

## Overview

Implements the AiClientApi ABC against Gemini 2.5 Flash. Supports 6 storage tools with Pydantic-validated arguments and a bounded tool-call loop.

## API Methods

- `send_message(prompt, context) -> str` — ABC contract, returns final text
- `send_message_with_metadata(prompt, context) -> AIResponse` — Returns text plus telemetry (action_taken, tool_calls, tool_args)
- `tools() -> list[ToolDefinition]` — Inspect available tools and their parameter schemas

## Available Tools

| Tool | Description | Pydantic Model |
|---|---|---|
| list_files | List objects in a container | ListFilesArgs |
| get_file_info | Get object metadata | GetFileInfoArgs |
| delete_file | Delete an object | DeleteFileArgs |
| upload_file | Upload from local path | UploadFileArgs |
| download_file | Download to local path | DownloadFileArgs |
| summarize_file | Summarize text/PDF content | SummarizeFileArgs |

## Tool Argument Validation

All tool arguments are validated at dispatch time using Pydantic models. Invalid arguments are returned as error strings to the model for self-correction.

## Error Handling

Recoverable errors (ObjectNotFoundError, ContainerNotFoundError, LocalFileAccessError) are caught by the tools layer and returned as "Error: ..." strings. The model sees these and can apologize or retry.

Non-recoverable errors (AuthenticationError, StorageBackendError, InvalidContainerError, etc.) propagate as RuntimeError("Storage operation failed: ...") to the caller.

Tool loop exhaustion raises ToolLoopExhaustedError after 10 iterations without a final response.

## Configuration

- `GEMINI_API_KEY` env var (or constructor argument)

## Dependency

```
google-genai>=1.0,<2.0
```
