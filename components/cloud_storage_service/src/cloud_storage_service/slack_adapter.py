"""Slack ChatClient implementation.

Adapted from Team 9's reference implementation at
https://github.com/HarshithKoriRaj/CS-GY-9223-Open-Source
(components/slack_client_impl/src/slack_client_impl/client.py).

Vendored rather than pip-installed because Team 9's package is a uv workspace
member and not independently installable via git URL. We depend on our own
pinned chat_client_api (HarshithKoriRaj/Shared-API.git v0.1.0) to guarantee
ABC alignment across the vertical.

Divergence from the upstream reference:

- Slack 'ts' strings are converted to timezone-aware datetime to match the
  ABC's declared Message.timestamp: datetime.
- Exceptions raised use the ABC-declared exception types
  (ChannelNotFoundError, MessageNotFoundError, MessageDeleteError) with
  error-code inspection so auth and rate-limit failures don't masquerade as
  "not found".
- List endpoints (get_channels, get_messages) raise on failure instead of
  silently returning [] — callers shouldn't have to distinguish "no results"
  from "API broken" by interpreting an empty list.
- register_client() side-effect at module load is omitted; we instantiate
  SlackChatClient directly from main.py for clarity.
- The optional cursor kwarg on get_messages is a Slack-specific extension and
  is not part of the shared ChatClient ABC.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any, Final

from chat_client_api import (
    Channel,
    ChannelNotFoundError,
    ChatClient,
    Message,
    MessageDeleteError,
    MessageNotFoundError,
)
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

MESSAGE_ID_SEP: Final = ":"

# Slack API error codes that should map to ChannelNotFoundError.
_CHANNEL_NOT_FOUND_CODES: Final = frozenset({"channel_not_found", "not_in_channel"})

# Slack API error codes that should map to MessageNotFoundError.
_MESSAGE_NOT_FOUND_CODES: Final = frozenset({"message_not_found", "no_such_message"})


def _encode_message_id(channel: str, ts: str) -> str:
    """Pack Slack's (channel, ts) identifier pair into a single opaque ID."""
    return f"{channel}{MESSAGE_ID_SEP}{ts}"


def _decode_message_id(message_id: str) -> tuple[str, str]:
    """Unpack an encoded message ID back into (channel, ts)."""
    parts = message_id.split(MESSAGE_ID_SEP, 1)
    if len(parts) != 2:
        msg = f"Invalid message_id format: {message_id!r}. Expected 'channel_id:timestamp'."
        raise ValueError(msg)
    return parts[0], parts[1]


def _slack_ts_to_datetime(ts: str) -> datetime:
    """Convert Slack's 'ts' string (e.g. '1745265420.012345') to UTC datetime."""
    return datetime.fromtimestamp(float(ts), tz=UTC)


def _slack_error_code(exc: SlackApiError) -> str:
    """Extract Slack's structured error code from a SlackApiError."""
    response = getattr(exc, "response", {}) or {}
    return str(response.get("error", "unknown"))


# ---------------------------------------------------------------------------
# Slack client
# ---------------------------------------------------------------------------


class SlackChatClient(ChatClient):
    """Slack implementation of ChatClient using slack-sdk."""

    def __init__(
        self,
        token: str | None = None,
        web_client: WebClient | None = None,
    ) -> None:
        """Initialize the Slack client.

        Args:
            token: Slack bot token. Falls back to SLACK_BOT_TOKEN env var.
                Ignored when web_client is supplied.
            web_client: Pre-built WebClient (test injection). When supplied,
                the token resolution is skipped entirely.

        Raises:
            ValueError: If no token is provided and SLACK_BOT_TOKEN is unset
                (and no web_client was injected).
        """
        if web_client is not None:
            self.client = web_client
            return

        resolved = token or os.getenv("SLACK_BOT_TOKEN")
        if not resolved:
            msg = "SLACK_BOT_TOKEN environment variable must be set"
            raise ValueError(msg)
        self.client = WebClient(token=resolved)

    # -----------------------------------------------------------------------
    # Send / channels
    # -----------------------------------------------------------------------

    def send_message(self, channel_id: str, text: str) -> Message:
        """Send a message to a Slack channel.

        Raises:
            ChannelNotFoundError: If the channel doesn't exist or the bot
                isn't a member.
            RuntimeError: For other Slack API failures (auth, rate-limit, etc.).
        """
        try:
            response = self.client.chat_postMessage(channel=channel_id, text=text)
        except SlackApiError as exc:
            error_code = _slack_error_code(exc)
            logger.warning(
                "slack.send_message.failed",
                extra={"channel": channel_id, "error": error_code},
            )
            if error_code in _CHANNEL_NOT_FOUND_CODES:
                msg = f"Channel not found: {channel_id}"
                raise ChannelNotFoundError(msg) from exc
            msg = f"Failed to send message to {channel_id}: {error_code}"
            raise RuntimeError(msg) from exc

        ts = str(response["ts"])
        ch = str(response["channel"])
        return Message(
            message_id=_encode_message_id(ch, ts),
            channel=ch,
            text=text,
            sender="",
            timestamp=_slack_ts_to_datetime(ts),
        )

    def get_channels(self) -> list[Channel]:
        """List all Slack channels the bot can access.

        Raises:
            RuntimeError: For Slack API failures.
        """
        try:
            response = self.client.conversations_list()
        except SlackApiError as exc:
            error_code = _slack_error_code(exc)
            logger.warning(
                "slack.get_channels.failed",
                extra={"error": error_code},
            )
            msg = f"Failed to list channels: {error_code}"
            raise RuntimeError(msg) from exc

        return [
            Channel(
                channel_id=str(ch["id"]),
                name=str(ch["name"]),
                is_private=bool(ch["is_private"]),
            )
            for ch in response["channels"]
        ]

    def get_channel(self, channel_id: str) -> Channel:
        """Get a single Slack channel by ID.

        Raises:
            ChannelNotFoundError: If the channel doesn't exist.
            RuntimeError: For other Slack API failures (auth, rate-limit, etc.).
        """
        try:
            response = self.client.conversations_info(channel=channel_id)
        except SlackApiError as exc:
            error_code = _slack_error_code(exc)
            logger.warning(
                "slack.get_channel.failed",
                extra={"channel": channel_id, "error": error_code},
            )
            if error_code in _CHANNEL_NOT_FOUND_CODES:
                msg = f"Channel not found: {channel_id}"
                raise ChannelNotFoundError(msg) from exc
            msg = f"Failed to get channel {channel_id}: {error_code}"
            raise RuntimeError(msg) from exc

        ch = response["channel"]
        return Channel(
            channel_id=str(ch["id"]),
            name=str(ch["name"]),
            is_private=bool(ch["is_private"]),
        )

    # -----------------------------------------------------------------------
    # Messages
    # -----------------------------------------------------------------------

    def get_messages(
        self,
        channel_id: str,
        limit: int = 10,
        cursor: str | None = None,
    ) -> list[Message]:
        """Get recent messages from a Slack channel.

        Note: cursor is a Slack-specific extension and is not part of the
        shared ChatClient ABC.

        Raises:
            ChannelNotFoundError: If the channel doesn't exist or the bot
                isn't a member.
            RuntimeError: For other Slack API failures.
        """
        kwargs: dict[str, Any] = {"channel": channel_id, "limit": limit}
        if cursor is not None:
            kwargs["cursor"] = cursor

        try:
            response = self.client.conversations_history(**kwargs)
        except SlackApiError as exc:
            error_code = _slack_error_code(exc)
            logger.warning(
                "slack.get_messages.failed",
                extra={"channel": channel_id, "error": error_code},
            )
            if error_code in _CHANNEL_NOT_FOUND_CODES:
                msg = f"Channel not found: {channel_id}"
                raise ChannelNotFoundError(msg) from exc
            msg = f"Failed to fetch messages from {channel_id}: {error_code}"
            raise RuntimeError(msg) from exc

        raw_messages: list[dict[str, Any]] = response.get("messages", [])
        messages: list[Message] = []
        for raw in raw_messages:
            ts = str(raw.get("ts", ""))
            if not ts:
                # Skip malformed messages instead of dating them to 1970.
                logger.debug(
                    "slack.get_messages.skipping_message_without_ts",
                    extra={"channel": channel_id},
                )
                continue
            messages.append(
                Message(
                    message_id=_encode_message_id(channel_id, ts),
                    channel=channel_id,
                    text=str(raw.get("text", "")),
                    sender=str(raw.get("user", "unknown")),
                    timestamp=_slack_ts_to_datetime(ts),
                )
            )
        return messages

    def get_message(self, message_id: str) -> Message:
        """Get a single Slack message by its encoded ID.

        Raises:
            MessageNotFoundError: If the message doesn't exist.
            RuntimeError: For other Slack API failures (auth, rate-limit, etc.).
        """
        channel, ts = _decode_message_id(message_id)

        try:
            response = self.client.conversations_history(
                channel=channel,
                latest=ts,
                oldest=ts,
                limit=1,
                inclusive=True,
            )
        except SlackApiError as exc:
            error_code = _slack_error_code(exc)
            logger.warning(
                "slack.get_message.failed",
                extra={"message_id": message_id, "error": error_code},
            )
            if error_code in _CHANNEL_NOT_FOUND_CODES | _MESSAGE_NOT_FOUND_CODES:
                msg = f"Message not found: {message_id}"
                raise MessageNotFoundError(msg) from exc
            msg = f"Failed to fetch message {message_id}: {error_code}"
            raise RuntimeError(msg) from exc

        raw_messages: list[dict[str, Any]] = response.get("messages", [])
        if not raw_messages:
            msg = f"Message not found: {message_id}"
            raise MessageNotFoundError(msg)

        raw = raw_messages[0]
        return Message(
            message_id=message_id,
            channel=channel,
            text=str(raw.get("text", "")),
            sender=str(raw.get("user", "unknown")),
            timestamp=_slack_ts_to_datetime(ts),
        )

    def delete_message(self, message_id: str) -> None:
        """Delete a Slack message by its encoded ID.

        Raises:
            MessageDeleteError: If Slack rejects the delete request.
        """
        channel, ts = _decode_message_id(message_id)
        try:
            self.client.chat_delete(channel=channel, ts=ts)
        except SlackApiError as exc:
            error_code = _slack_error_code(exc)
            logger.warning(
                "slack.delete_message.failed",
                extra={"message_id": message_id, "error": error_code},
            )
            msg = f"Failed to delete message {message_id}: {error_code}"
            raise MessageDeleteError(msg) from exc
