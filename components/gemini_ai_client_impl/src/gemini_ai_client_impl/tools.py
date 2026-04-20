"""Tool declarations and implementations for Gemini AI client."""

from __future__ import annotations

import base64
import contextlib
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from cloud_storage_api import CloudStorageClient

from cloud_storage_api.exceptions import (
    LocalFileAccessError,
    ObjectNotFoundError,
)

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]


# ============================================================================
# Tool Functions
# ============================================================================


def _list_files(
    storage: CloudStorageClient,
    container: str,
    prefix: str = "",
) -> str:
    """List files in a container.

    Args:
        storage: CloudStorageClient instance.
        container: Container name.
        prefix: Object name prefix for filtering.

    Returns:
        JSON-formatted string of ObjectInfo list.
    """
    objects = storage.list_files(container, prefix)
    serialized = [
        {
            "object_name": obj.object_name,
            "size_bytes": obj.size_bytes,
            "data_type": obj.data_type,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at is not None else str(obj.updated_at),
        }
        for obj in objects
    ]
    return json.dumps(serialized, indent=2)


def _get_file_info(
    storage: CloudStorageClient,
    container: str,
    object_name: str,
) -> str:
    """Get metadata for a single file.

    Args:
        storage: CloudStorageClient instance.
        container: Container name.
        object_name: Object name.

    Returns:
        JSON-formatted ObjectInfo or error string.
    """
    try:
        obj = storage.get_file_info(container, object_name)
        serialized = {
            "object_name": obj.object_name,
            "size_bytes": obj.size_bytes,
            "data_type": obj.data_type,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at is not None else str(obj.updated_at),
        }
        return json.dumps(serialized, indent=2)
    except ObjectNotFoundError:
        return f"Error: Object '{object_name}' not found in container '{container}'."


def _delete_file(
    storage: CloudStorageClient,
    container: str,
    object_name: str,
) -> str:
    """Delete a file from a container.

    Args:
        storage: CloudStorageClient instance.
        container: Container name.
        object_name: Object name to delete.

    Returns:
        Confirmation string or error string.
    """
    try:
        storage.delete_file(container, object_name)
    except ObjectNotFoundError:
        return f"Error: Object '{object_name}' not found in container '{container}'."
    else:
        return f"Deleted {object_name} from {container}."


def _upload_file(
    storage: CloudStorageClient,
    container: str,
    local_path: str,
    remote_path: str,
) -> str:
    """Upload a file to a container.

    Args:
        storage: CloudStorageClient instance.
        container: Container name.
        local_path: Local file path.
        remote_path: Remote object path.

    Returns:
        Confirmation string or error string.
    """
    try:
        obj_info = storage.upload_file(container, local_path, remote_path)
    except LocalFileAccessError:
        return f"Error: Cannot access local file '{local_path}'."
    else:
        return f"Uploaded {obj_info.object_name} ({obj_info.size_bytes} bytes) to {container}."


def _download_file(
    storage: CloudStorageClient,
    container: str,
    object_name: str,
    file_name: str,
) -> str:
    """Download a file from a container.

    Args:
        storage: CloudStorageClient instance.
        container: Container name.
        object_name: Object name to download.
        file_name: Local destination path.

    Returns:
        Confirmation string or error string.
    """
    try:
        storage.download_file(container, object_name, file_name)
    except ObjectNotFoundError:
        return f"Error: Object '{object_name}' not found in container '{container}'."
    else:
        return f"Downloaded {object_name} to {file_name}."


def _summarize_file(
    storage: CloudStorageClient,
    container: str,
    object_name: str,
) -> str:
    """Summarize file content or prepare for Gemini processing.

    Args:
        storage: CloudStorageClient instance.
        container: Container name.
        object_name: Object name to summarize.

    Returns:
        Raw file content (text), base64-encoded content (PDF), error string, or unsupported message.
    """
    ext = "." + object_name.rsplit(".", maxsplit=1)[-1].lower() if "." in object_name else ""

    # Check for supported types first
    text_extensions = {".txt", ".md", ".csv", ".json", ".log", ".py", ".yaml", ".yml"}
    if ext not in text_extensions and ext != ".pdf":
        return f"File type not supported for summarization: {ext}"

    # Download to temp file and process
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name

        storage.download_file(container, object_name, temp_path)

        if ext == ".pdf":
            # Read as bytes and base64-encode
            pdf_bytes = Path(temp_path).read_bytes()
            encoded = base64.b64encode(pdf_bytes).decode("utf-8")
            return f"PDF_CONTENT_BASE64:{encoded}"

        content = Path(temp_path).read_text(encoding="utf-8")

    except ObjectNotFoundError:
        return f"Error: Object '{object_name}' not found in container '{container}'."
    else:
        return content
    finally:
        # Always clean up temp file
        if temp_path is not None:
            with contextlib.suppress(OSError):
                Path(temp_path).unlink()


# ============================================================================
# Tool Declarations
# ============================================================================


def get_tool_declarations() -> list[Any]:
    """Get Gemini tool declarations.

    Returns:
        List of Tool protos for Gemini.
    """
    if genai_types is None:
        msg = "google.genai not installed"
        raise ImportError(msg)

    return [
        genai_types.Tool(
            function_declarations=[
                genai_types.FunctionDeclaration(
                    name="list_files",
                    description="List files in a cloud storage container, optionally filtered by prefix.",
                    parameters=genai_types.Schema(
                        type=genai_types.Type.OBJECT,
                        properties={
                            "container": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The container name (e.g., bucket name).",
                            ),
                            "prefix": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="Optional prefix to filter object names. Defaults to empty string.",
                            ),
                        },
                        required=["container"],
                    ),
                ),
                genai_types.FunctionDeclaration(
                    name="get_file_info",
                    description="Get metadata for a specific file in cloud storage.",
                    parameters=genai_types.Schema(
                        type=genai_types.Type.OBJECT,
                        properties={
                            "container": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The container name.",
                            ),
                            "object_name": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The object name (file path).",
                            ),
                        },
                        required=["container", "object_name"],
                    ),
                ),
                genai_types.FunctionDeclaration(
                    name="delete_file",
                    description="Delete a file from cloud storage.",
                    parameters=genai_types.Schema(
                        type=genai_types.Type.OBJECT,
                        properties={
                            "container": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The container name.",
                            ),
                            "object_name": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The object name to delete.",
                            ),
                        },
                        required=["container", "object_name"],
                    ),
                ),
                genai_types.FunctionDeclaration(
                    name="upload_file",
                    description="Upload a file to cloud storage.",
                    parameters=genai_types.Schema(
                        type=genai_types.Type.OBJECT,
                        properties={
                            "container": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The container name.",
                            ),
                            "local_path": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="Path to the local file to upload.",
                            ),
                            "remote_path": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="Destination object name/path in the container.",
                            ),
                        },
                        required=["container", "local_path", "remote_path"],
                    ),
                ),
                genai_types.FunctionDeclaration(
                    name="download_file",
                    description="Download a file from cloud storage to a local path.",
                    parameters=genai_types.Schema(
                        type=genai_types.Type.OBJECT,
                        properties={
                            "container": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The container name.",
                            ),
                            "object_name": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The object name to download.",
                            ),
                            "file_name": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="Local destination path.",
                            ),
                        },
                        required=["container", "object_name", "file_name"],
                    ),
                ),
                genai_types.FunctionDeclaration(
                    name="summarize_file",
                    description=(
                        "Summarize or retrieve file content for AI processing. "
                        "Supports text, CSV, JSON, YAML, Python, logs, and PDF."
                    ),
                    parameters=genai_types.Schema(
                        type=genai_types.Type.OBJECT,
                        properties={
                            "container": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The container name.",
                            ),
                            "object_name": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The object name to summarize.",
                            ),
                        },
                        required=["container", "object_name"],
                    ),
                ),
            ]
        )
    ]


def dispatch_tool_call(
    name: str,
    args: dict[str, Any],
    storage: CloudStorageClient,
) -> str:
    """Dispatch a tool call to the appropriate function.

    Args:
        name: Tool function name.
        args: Arguments dict.
        storage: CloudStorageClient instance.

    Returns:
        String result from the tool.
    """
    dispatch_map: dict[str, Callable[[], str]] = {
        "list_files": lambda: _list_files(storage, args["container"], args.get("prefix", "")),
        "get_file_info": lambda: _get_file_info(storage, args["container"], args["object_name"]),
        "delete_file": lambda: _delete_file(storage, args["container"], args["object_name"]),
        "upload_file": lambda: _upload_file(storage, args["container"], args["local_path"], args["remote_path"]),
        "download_file": lambda: _download_file(storage, args["container"], args["object_name"], args["file_name"]),
        "summarize_file": lambda: _summarize_file(storage, args["container"], args["object_name"]),
    }

    if name in dispatch_map:
        return dispatch_map[name]()
    return f"Error: Unknown tool '{name}'."
