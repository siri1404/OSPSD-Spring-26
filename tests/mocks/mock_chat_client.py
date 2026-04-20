"""Mock implementation of Chat API for testing.

Provides a reusable deterministic mock that captures send_message calls for assertion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import TYPE_CHECKING


class MockMessage:
    """Mock Message dataclass matching chat_client_api.Message."""

    def __init__(
        self,
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


class MockChatClientApi:
    """Deterministic mock of Chat API for integration testing.

    Captures all send_message calls and their arguments for assertion.
    Returns fixed Message responses without requiring live Chat API credentials.
    """

    def __init__(self) -> None:
        """Initialize mock with empty call history."""
        self.call_history: list[tuple[str, str | None]] = []
        self.call_count = 0
        self.raise_on_send = False

    def send_message(
        self,
        message_text: str,
        channel_id: str | None = None,
    ) -> MockMessage:
        """Send a message to the chat API.

        Args:
            message_text: The message content to send.
            channel_id: Optional channel ID.

        Returns:
            MockMessage object.

        Raises:
            RuntimeError: If raise_on_send is True (for error path testing).
        """
        if self.raise_on_send:
            msg = "Chat service down"
            raise RuntimeError(msg)

        self.call_count += 1
        self.call_history.append((message_text, channel_id))

        return MockMessage(text=message_text, channel=channel_id or "general")

    def get_last_message_text(self) -> str | None:
        """Get the text of the last message sent.

        Returns:
            The message text, or None if no messages sent.
        """
        if self.call_history:
            return self.call_history[-1][0]
        return None

    def assert_message_sent_with_text(self, text_fragment: str) -> bool:
        """Check if any sent message contains the given text fragment.

        Args:
            text_fragment: Text to search for in sent messages.

        Returns:
            True if found, False otherwise.
        """
        return any(text_fragment.lower() in message_text.lower() for message_text, _ in self.call_history)

    def reset(self) -> None:
        """Reset mock to initial state."""
        self.call_history = []
        self.call_count = 0
        self.raise_on_send = False

    def clear_history(self) -> None:
        """Clear call history but keep other state."""
        self.call_history = []
