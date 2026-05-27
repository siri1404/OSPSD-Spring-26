"""Abstract interface for AI client implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_client_api.models import ToolDefinition


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

    @abstractmethod
    def tools(self) -> list[ToolDefinition]:
        """Return the list of tools available to this AI client.

        This method exposes the tool definitions so callers can inspect
        what operations the AI client can perform before invoking send_message.

        Returns:
            A list of ToolDefinition objects describing each available tool,
            including name, description, and parameter signature.

        Example:
            >>> client = GeminiAiClient(storage_client)
            >>> available_tools = client.tools()
            >>> for tool in available_tools:
            ...     print(f"{tool.name}: {tool.description}")
        """
