"""Abstract interface for AI client implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_client_api.models import AIResponse


class AiClientApi(ABC):
    """Abstract interface for AI chat completions with tool calling."""

    @abstractmethod
    def send_message(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AIResponse:
        """Send a natural language prompt and return a structured AI response.

        Args:
            prompt: The user's natural language request.
            context: Optional key-value context (e.g. default container name).

        Returns:
            AIResponse containing text, action_taken, and tool_calls.
        """
