"""Mock implementations of external APIs for testing.

This module provides reusable deterministic mocks that eliminate the need for
live API credentials. Mocks follow the same interface as real implementations
but return fixed test data.

Public surface:
- MockAiClientApi — deterministic stand-in for the AI client used in
  integration tests. Implements both the slim send_message(prompt, context)
  -> str contract from AiClientApi and the extended
  send_message_with_metadata(prompt, context) -> AIResponse used by the
  /ai/chat handler.
"""

from __future__ import annotations

from ai_client_api import AIResponse

# ---------------------------------------------------------------------------
# Mock AI Client
# ---------------------------------------------------------------------------


class MockAiClientApi:
    """Deterministic mock of the AI client for integration testing.

    Each call returns the next AIResponse from the configured queue, or a
    generic fallback when the queue is empty. Tests can pre-load specific
    responses with set_response/set_responses and inspect call history via
    call_count/last_prompt/last_context.
    """

    def __init__(self) -> None:
        """Initialize mock with the default response sequence."""
        self.call_count: int = 0
        self.last_prompt: str = ""
        self.last_context: dict[str, object] | None = None
        self.responses: list[AIResponse] = []
        self._install_default_responses()

    # -----------------------------------------------------------------------
    # Public API (mirrors AiClientApi + extension)
    # -----------------------------------------------------------------------

    def send_message(
        self,
        prompt: str,
        context: dict[str, object] | None = None,
    ) -> str:
        """Slim contract: return only the assistant's final text."""
        return self.send_message_with_metadata(prompt, context).text

    def send_message_with_metadata(
        self,
        prompt: str,
        context: dict[str, object] | None = None,
    ) -> AIResponse:
        """Return the next queued AIResponse (or a generic fallback)."""
        self.call_count += 1
        self.last_prompt = prompt
        self.last_context = context

        if self.responses:
            return self.responses.pop(0)

        return AIResponse(
            text=f"I processed your prompt: {prompt}",
            action_taken=None,
            tool_calls=[],
        )

    # -----------------------------------------------------------------------
    # Test helpers
    # -----------------------------------------------------------------------

    def set_response(self, response: AIResponse) -> None:
        """Queue a single response for the next call."""
        self.responses = [response]

    def set_responses(self, responses: list[AIResponse]) -> None:
        """Queue a sequence of responses to be returned in order."""
        self.responses = list(responses)

    def reset(self) -> None:
        """Reset call history and restore the default response queue."""
        self.call_count = 0
        self.last_prompt = ""
        self.last_context = None
        self._install_default_responses()

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _install_default_responses(self) -> None:
        """Seed the queue with a generic 'list_files' response for default tests."""
        self.responses = [
            AIResponse(
                text="You have 3 files in your bucket",
                action_taken="list_files",
                tool_calls=["list_files"],
                tool_args={"container": "test-bucket"},
            ),
        ]
