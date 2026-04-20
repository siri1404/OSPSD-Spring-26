"""Response models for AI client API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIResponse:
    """Structured response from AI client.

    Attributes:
        text: The human-readable response text from the AI.
        action_taken: The name of the tool/action performed (e.g., 'list_files', 'upload_file'),
                      or None if no action was taken.
        tool_calls: List of all tool names that were called during this request.
    """

    text: str
    action_taken: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    tool_args: dict[str, Any] | None = None
