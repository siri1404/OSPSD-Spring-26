"""Response models for AI client API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AIResponse:
    """Structured response from AI client.

    Attributes:
        text: The human-readable response text from the AI.
        action_taken: The name of the last tool/action performed (e.g., 'list_files', 'upload_file'),
                      or None if no action was taken.
        tool_calls: List of all tool names called during this request, in invocation order. Empty when no tool was invoked.
        tool_args: Arguments passed to the last tool call, or None if no tool was called.
    """

    text: str
    action_taken: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    tool_args: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolParameter:
    """Describes a single parameter of a tool.

    Attributes:
        name: Parameter name (e.g., 'container', 'object_name').
        type: Parameter type (e.g., 'string', 'integer', 'boolean').
        description: Human-readable description of the parameter.
        required: Whether this parameter is mandatory.
    """

    name: str
    type: str
    description: str
    required: bool = True


@dataclass(frozen=True)
class ToolDefinition:
    """Describes an AI tool that the model can invoke.

    Attributes:
        name: Unique tool identifier (e.g., 'list_files', 'upload_file').
        description: Human-readable description of what the tool does.
        parameters: List of ToolParameter describing the tool's signature.
    """

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
