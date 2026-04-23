"""Mock implementations of external APIs for testing.

This module provides reusable deterministic mocks that eliminate need for live API credentials.
Mocks follow the same interface as real implementations but return fixed test data.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ai_client_api import AIResponse


class MockAiClientApi:
    """Deterministic mock of AiClientApi for integration testing.

    Provides controlled responses without requiring live Gemini API key.
    Each response is deterministic and includes realistic action_taken values.
    """

    def __init__(self) -> None:
        """Initialize mock with default response sequence."""
        self.call_count = 0
        self.last_prompt = ""
        self.responses: list[AIResponse] = []
        self._setup_default_responses()

    def _setup_default_responses(self) -> None:
        """Setup default response sequence for list_files prompt."""
        self.responses = [
            AIResponse(
                text="You have 3 files in your bucket",
                action_taken="list_files",
                tool_calls=["list_files"],
                tool_args={"container": "test-bucket"},
            ),
        ]

    def send_message(
        self,
        prompt: str,
        container: str | None = None,
    ) -> AIResponse:
        """Send a message to the AI and get a response.

        Args:
            prompt: The user's prompt or question.
            container: Optional GCS bucket name.

        Returns:
            AIResponse with text, action_taken, tool_calls, and tool_args.
        """
        self.call_count += 1
        self.last_prompt = prompt

        # Return first response if available, otherwise return a generic response
        if self.responses:
            return self.responses.pop(0)

        return AIResponse(
            text=f"I processed your prompt: {prompt}",
            action_taken=None,
            tool_calls=[],
            tool_args=None,
        )

    def set_response(self, response: AIResponse) -> None:
        """Set a single response to be returned on next send_message call.

        Args:
            response: The AIResponse to return.
        """
        self.responses = [response]

    def set_responses(self, responses: list[AIResponse]) -> None:
        """Set a sequence of responses to be returned sequentially.

        Args:
            responses: List of AIResponse objects to return in order.
        """
        self.responses = responses.copy()

    def reset(self) -> None:
        """Reset mock to initial state."""
        self.call_count = 0
        self.last_prompt = ""
        self._setup_default_responses()
