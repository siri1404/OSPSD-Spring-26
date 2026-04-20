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
        """Send a natural language prompt and return a human-readable response.

        Args:
            prompt: The user's natural language request.
            context: Optional key-value context (e.g. default container name).

        Returns:
            A human-readable string response.
        """
