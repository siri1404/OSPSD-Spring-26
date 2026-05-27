"""Mock implementation of the Chat API for testing.

Provides a reusable deterministic mock of chat_client_api.ChatClient that
captures send_message calls for assertion. Returns fixed Message responses
without requiring live Chat API credentials.

Public surface:
- MockChatClientApi — deterministic stand-in for the Chat client.
- MockMessage — minimal Message stub returned by send_message.
"""

from __future__ import annotations

from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Mock Message
# ---------------------------------------------------------------------------


class MockMessage:
    """Mock Message dataclass matching chat_client_api.Message."""

    def __init__(
        self,
        *,
        message_id: str = "msg_test_123",
        channel: str = "general",
        text: str = "Test notification",
        sender: str = "cloud-storage-service",
        timestamp: datetime | None = None,
    ) -> None:
        """Initialize mock message."""
        self.message_id = message_id
        self.channel = channel
        self.text = text
        self.sender = sender
        self.timestamp = timestamp or datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Mock Chat Client API
# ---------------------------------------------------------------------------


class MockChatClientApi:
    """Deterministic mock of the Chat API for integration testing.

    Captures all send_message calls and their arguments for assertion.
    Returns fixed Message responses without requiring live Chat API credentials.

    Note: The signature mirrors chat_client_api.ChatClient.send_message, which
    takes (channel_id, text). Tests should call this mock with the same
    argument order so assertions on call_history match the real adapter's
    behaviour.
    """

    def __init__(self) -> None:
        """Initialize mock with empty call history."""
        self.call_history: list[tuple[str, str]] = []
        self.call_count: int = 0
        self.raise_on_send: bool = False

    # -----------------------------------------------------------------------
    # Public API (mirrors ChatClient.send_message)
    # -----------------------------------------------------------------------

    def send_message(self, channel_id: str, text: str) -> MockMessage:
        """Send a message to the chat API.

        Args:
            channel_id: The destination channel ID.
            text: The message content to send.

        Returns:
            MockMessage describing the recorded send.

        Raises:
            RuntimeError: If raise_on_send is True (used for error-path tests).
        """
        if self.raise_on_send:
            msg = "Chat service down"
            raise RuntimeError(msg)

        self.call_count += 1
        self.call_history.append((channel_id, text))

        return MockMessage(text=text, channel=channel_id)

    # -----------------------------------------------------------------------
    # Assertion helpers
    # -----------------------------------------------------------------------

    def get_last_message_text(self) -> str | None:
        """Return the text of the last message sent, or None if none."""
        if not self.call_history:
            return None
        return self.call_history[-1][1]

    def get_last_channel(self) -> str | None:
        """Return the channel of the last message sent, or None if none."""
        if not self.call_history:
            return None
        return self.call_history[-1][0]

    def assert_message_sent_with_text(self, text_fragment: str) -> bool:
        """Return True if any sent message text contains the given fragment."""
        needle = text_fragment.lower()
        return any(needle in text.lower() for _channel, text in self.call_history)

    # -----------------------------------------------------------------------
    # Reset helpers
    # -----------------------------------------------------------------------

    def reset(self) -> None:
        """Reset mock to initial state (history + flags)."""
        self.call_history = []
        self.call_count = 0
        self.raise_on_send = False

    def clear_history(self) -> None:
        """Clear call history but preserve flags like raise_on_send."""
        self.call_history = []
        self.call_count = 0
