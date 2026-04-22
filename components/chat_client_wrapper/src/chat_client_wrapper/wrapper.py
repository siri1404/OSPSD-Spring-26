"""Chat notification wrapper for cloud storage events."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chat_client_api import ChatClient  # type: ignore[import-untyped]


class ChatNotificationWrapper:
    """Wrapper for chat notifications on storage events.

    Provides a simple notify() method to send messages to a configured chat channel
    when storage events occur (upload, delete, AI actions).
    """

    def __init__(
        self,
        chat_client: ChatClient,
        channel_id: str | None = None,
    ) -> None:
        """Initialize chat notification wrapper.

        Args:
            chat_client: ChatClient implementation from shared chat-client-api.
            channel_id: Channel ID to send notifications to.
                        Defaults to CHAT_CHANNEL_ID env var.

        Raises:
            ValueError: If channel_id is not provided and env var not set.
        """
        self._chat_client = chat_client
        self._channel_id = channel_id or os.getenv("CHAT_CHANNEL_ID")

        if not self._channel_id:
            msg = "channel_id must be provided or CHAT_CHANNEL_ID env var must be set"
            raise ValueError(msg)

    def notify(self, message: str) -> dict[str, Any]:
        """Send a notification message to the configured channel.

        Args:
            message: The notification message to send.

        Returns:
            Response dict with message metadata.

        Raises:
            ValueError: If message is empty.
            RuntimeError: If the message could not be sent.
        """
        if not message or not isinstance(message, str):
            msg = "Message must be a non-empty string"
            raise ValueError(msg)

        try:
            response = self._chat_client.send_message(
                channel_id=self._channel_id,
                text=message,
            )
            # Convert Message dataclass to dict for consistency
            return {
                "message_id": response.message_id,
                "channel": response.channel,
                "text": response.text,
                "sender": response.sender,
                "timestamp": str(response.timestamp) if response.timestamp else None,
            }
        except Exception as exc:
            err_msg = f"Failed to send notification to chat: {exc}"
            raise RuntimeError(err_msg) from exc
