"""Abstract interface for AI client implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AiClientApi(ABC):
    """Abstract interface for AI chat completions with tool calling."""

    @abstractmethod
    def send_message(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Send a natural language prompt and return the AI's text reply.

        Args:
            prompt: The user's natural language request.
            context: Optional key-value context (e.g. default container name).

        Returns:
            The AI's text response. Implementations are responsible for
            executing any tool calls internally before returning the final
            text reply.
        """
