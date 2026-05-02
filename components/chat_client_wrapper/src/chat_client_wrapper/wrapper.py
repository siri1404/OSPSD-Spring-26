"""Chat notification wrapper for cloud storage events."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from chat_client_api import ChatClient

logger = logging.getLogger(__name__)


class NotificationResult(TypedDict):
    """Shape of the notify() return value."""

    message_id: str
    channel: str
    text: str
    sender: str
    timestamp: str | None


class ChatNotificationWrapper:
    """Wrapper for chat notifications on storage events.

    Provides a simple notify() method to send messages to a configured
    chat channel when storage events occur: upload, delete, AI actions.
    """

    def __init__(
        self,
        chat_client: ChatClient,
        channel_id: str | None = None,
    ) -> None:
        """Initialize chat notification wrapper.

        Args:
            chat_client: ChatClient implementation from shared chat-client-api.
            channel_id: Channel ID to send notifications to. Falls back to
                CHAT_CHANNEL_ID env var when not provided.

        Raises:
            ValueError: If neither argument nor env var supplies a channel.
        """
        resolved_channel_id = channel_id or os.getenv("CHAT_CHANNEL_ID")

        if not resolved_channel_id:
            msg = "channel_id must be provided or CHAT_CHANNEL_ID env var must be set"
            raise ValueError(msg)

        self._chat_client = chat_client
        self._channel_id: str = resolved_channel_id

    @property
    def channel_id(self) -> str:
        """Return the configured chat channel ID."""
        return self._channel_id

    def notify(self, message: str) -> NotificationResult:
        """Send a notification message to the configured channel.

        Args:
            message: The notification message to send.

        Returns:
            Result dict with message metadata.

        Raises:
            ValueError: If message is empty.
            RuntimeError: If the message could not be sent through the chat client.
        """
        if not message:
            msg = "Message must be a non-empty string"
            raise ValueError(msg)

        try:
            response = self._chat_client.send_message(
                channel_id=self._channel_id,
                text=message,
            )
        except Exception as exc:
            logger.warning(
                "chat.notify.failed",
                extra={"channel": self.channel_id, "error": str(exc)},
            )
            err_msg = f"Failed to send notification to chat: {exc}"
            raise RuntimeError(err_msg) from exc

        return NotificationResult(
            message_id=response.message_id,
            channel=response.channel,
            text=response.text,
            sender=response.sender,
            timestamp=str(response.timestamp) if response.timestamp else None,
        )
