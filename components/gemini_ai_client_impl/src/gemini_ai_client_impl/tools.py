"""Tool declarations and implementations for Gemini AI client."""

from __future__ import annotations

import base64
import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cloud_storage_api.exceptions import (
    ContainerNotFoundError,
    LocalFileAccessError,
    ObjectNotFoundError,
)
from google.genai import types as genai_types

if TYPE_CHECKING:
    from cloud_storage_api import CloudStorageClient
    from cloud_storage_api.models import ObjectInfo


# ============================================================================
# Constants
# ============================================================================
_TEXT_EXTENSIONS = frozenset(
    {
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".log",
        ".py",
        ".yaml",
        ".yml",
    }
)

_PDF_EXTENSION = ".pdf"
_PDF_BASE64_PREFIX = "PDF_CONTENT_BASE64:"

_DECLARED_TOOLS: tuple[str, ...] = (
    "list_files",
    "get_file_info",
    "delete_file",
    "upload_file",
    "download_file",
    "summarize_file",
)


# ============================================================================
# Helpers
# ============================================================================


def _serialize_object(obj: ObjectInfo) -> dict[str, object]:
    """Serialize an ObjectInfo to a JSON-friendly dict."""
    return {
        "object_name": obj.object_name,
        "size_bytes": obj.size_bytes,
        "data_type": obj.data_type,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _missing_arg(arg_name: str) -> str:
    """Format a user-facing 'missing required arg' error string."""
    return f"Error: missing required arg '{arg_name}'"


def _check_args(args: dict[str, Any], required: tuple[str, ...]) -> str | None:
    """Return an error string for the first missing required arg, or None."""
    for key in required:
        if key not in args:
            return _missing_arg(key)
    return None


# ============================================================================
# Tool Functions
# ============================================================================


def _list_files(
    storage: CloudStorageClient,
    container: str,
    prefix: str = "",
) -> str:
    """List files in a container.

    Returns a JSON-formatted list of serialized ObjectInfo or an error string.
    """
    try:
        objects = storage.list_files(container, prefix)
    except ContainerNotFoundError:
        return f"Error: Container '{container}' not found."

    serialized = [_serialize_object(obj) for obj in objects]
    return json.dumps(serialized, indent=2)


def _get_file_info(
    storage: CloudStorageClient,
    container: str,
    object_name: str,
) -> str:
    """Get metadata for a single file.

    Returns JSON of the ObjectInfo or an error string if missing.
    """
    try:
        obj = storage.get_file_info(container, object_name)
    except ObjectNotFoundError:
        return f"Error: Object '{object_name}' not found in container '{container}'."
    return json.dumps(_serialize_object(obj), indent=2)


def _delete_file(
    storage: CloudStorageClient,
    container: str,
    object_name: str,
) -> str:
    """Delete a file from a container.

    Returns a confirmation string or an error string when not found.
    """
    try:
        storage.delete_file(container, object_name)
    except ObjectNotFoundError:
        return f"Error: Object '{object_name}' not found in container '{container}'."
    return f"Deleted {object_name} from {container}."


def _upload_file(
    storage: CloudStorageClient,
    container: str,
    local_path: str,
    remote_path: str,
) -> str:
    """Upload a file to a container.

    Returns a confirmation string or an error string when the local file is unavailable.
    """
    try:
        obj_info = storage.upload_file(container, local_path, remote_path)
    except LocalFileAccessError:
        return f"Error: Cannot access local file '{local_path}'."
    return f"Uploaded {obj_info.object_name} ({obj_info.size_bytes} bytes) to {container}."


def _download_file(
    storage: CloudStorageClient,
    container: str,
    object_name: str,
    file_name: str,
) -> str:
    """Download a file from a container to a local path.

    Returns confirmation or an error string if the object is missing.
    """
    try:
        storage.download_file(container, object_name, file_name)
    except ObjectNotFoundError:
        return f"Error: Object '{object_name}' not found in container '{container}'."
    return f"Downloaded {object_name} to {file_name}."


def _summarize_file(
    storage: CloudStorageClient,
    container: str,
    object_name: str,
) -> str:
    """Summarize file content or prepare it for Gemini processing.

    Returns raw text, a PDF base64 payload prefixed by PDF_CONTENT_BASE64:, an
    error string, or a file-type-not-supported message.
    """
    ext = Path(object_name).suffix.lower()
    if ext not in _TEXT_EXTENSIONS and ext != _PDF_EXTENSION:
        return f"File type not supported for summarization: {ext}"

    # mkstemp avoids the open-then-reopen race on Windows
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    try:
        try:
            storage.download_file(container, object_name, temp_path)
        except ObjectNotFoundError:
            return f"Error: Object '{object_name}' not found in container '{container}'."

        if ext == _PDF_EXTENSION:
            pdf_bytes = Path(temp_path).read_bytes()
            encoded = base64.b64encode(pdf_bytes).decode("utf-8")
            return f"{_PDF_BASE64_PREFIX}{encoded}"

        try:
            return Path(temp_path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: Could not decode '{object_name}' as UTF-8 text."
    finally:
        with contextlib.suppress(OSError):
            Path(temp_path).unlink()


# ============================================================================
# Tool Declarations
# ============================================================================


def get_tool_declarations() -> list[genai_types.Tool]:
    """Get Gemini tool declarations.

    Returns a list of genai Tool protos used by the model configuration.
    """
    return [
        genai_types.Tool(
            function_declarations=[
                genai_types.FunctionDeclaration(
                    name="list_files",
                    description=(
                        "List files in a cloud storage container, optionally filtered by prefix."
                    ),
                    parameters=genai_types.Schema(
                        type=genai_types.Type.OBJECT,
                        properties={
                            "container": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description="The container name (e.g., bucket name).",
                            ),
                            "prefix": genai_types.Schema(
                                type=genai_types.Type.STRING,
                                description=(
                                    "Optional prefix to filter object names. "
                                    "Defaults to empty string."
                                ),
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


# ============================================================================
# Dispatch
# ============================================================================


def dispatch_tool_call(  # noqa: C901, PLR0911
    name: str,
    args: dict[str, Any],
    storage: CloudStorageClient,
) -> str:
    """Dispatch a tool call to the appropriate function.

    Args:
        name: Tool function name. Must be one of the declared tools.
        args: Arguments dict from the model's function call.
        storage: CloudStorageClient instance used by all tools.

    Returns:
        String result from the tool. Errors that the model could plausibly
        recover from are returned as "Error: ..." strings; programming
        bugs (unknown tool name) raise ValueError.

    Raises:
        ValueError: If name is not a declared tool.
    """
    if name == "list_files":
        if err := _check_args(args, ("container",)):
            return err
        return _list_files(storage, args["container"], args.get("prefix", ""))

    if name == "get_file_info":
        if err := _check_args(args, ("container", "object_name")):
            return err
        return _get_file_info(storage, args["container"], args["object_name"])

    if name == "delete_file":
        if err := _check_args(args, ("container", "object_name")):
            return err
        return _delete_file(storage, args["container"], args["object_name"])

    if name == "upload_file":
        if err := _check_args(args, ("container", "local_path", "remote_path")):
            return err
        return _upload_file(
            storage,
            args["container"],
            args["local_path"],
            args["remote_path"],
        )

    if name == "download_file":
        if err := _check_args(args, ("container", "object_name", "file_name")):
            return err
        return _download_file(
            storage,
            args["container"],
            args["object_name"],
            args["file_name"],
        )

    if name == "summarize_file":
        if err := _check_args(args, ("container", "object_name")):
            return err
        return _summarize_file(storage, args["container"], args["object_name"])

    msg = f"Unknown tool: {name!r}. Declared tools: {sorted(_DECLARED_TOOLS)}"
    raise ValueError(msg)
