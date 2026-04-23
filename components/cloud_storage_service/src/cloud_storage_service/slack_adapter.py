"""Slack ChatClient implementation.

Adapted from Team 9's reference implementation at https://github.com/HarshithKoriRaj/CS-GY-9223-Open-Source
(components/slack_client_impl/src/slack_client_impl/client.py)

Vendored rather than pip-installed because Team 9's package is a uv workspace member and not independently
installable via git URL. We depend on our own pinned chat_client_api (HarshithKoriRaj/Shared-API.git v0.1.0)
to guarantee ABC alignment across the vertical.

Divergence from the upstream reference:

- timestamp is converted from Slack's string 'ts' to a timezone-aware datetime, matching the ABC's
  declared Message.timestamp: datetime.
- Exceptions raised use the ABC-declared exception types (ChannelNotFoundError, MessageNotFoundError,
  MessageDeleteError) instead of bare ValueError.
- register_client() side-effect at module load is omitted; we instantiate SlackChatClient directly
  from main.py for clarity.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

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

_MESSAGE_ID_SEP = ":"


def _encode_message_id(channel: str, ts: str) -> str:
    """Pack Slack's (channel, ts) identifier pair into a single opaque ID."""
    return f"{channel}{_MESSAGE_ID_SEP}{ts}"


def _decode_message_id(message_id: str) -> tuple[str, str]:
    """Unpack an encoded message ID back into (channel, ts)."""
    parts = message_id.split(_MESSAGE_ID_SEP, 1)
    if len(parts) != 2:
        msg = f"Invalid message_id format: {message_id!r}. Expected 'channel_id:timestamp'."
        raise ValueError(msg)
    return parts[0], parts[1]


def _slack_ts_to_datetime(ts: str) -> datetime:
    """Convert Slack's 'ts' string (e.g. '1745265420.012345') to a timezone-aware datetime."""
    return datetime.fromtimestamp(float(ts), tz=UTC)


class SlackChatClient(ChatClient):
    """Slack implementation of ChatClient using slack-sdk."""

    def __init__(self, token: str | None = None) -> None:
        """Initialize Slack client.

        Args:
            token: Slack bot token. Falls back to SLACK_BOT_TOKEN env var.

        Raises:
            ValueError: If no token is provided and env var is unset.
        """
        resolved = token or os.getenv("SLACK_BOT_TOKEN")
        if not resolved:
            msg = "SLACK_BOT_TOKEN environment variable must be set"
            raise ValueError(msg)
        self._token = resolved
        self._client = WebClient(token=resolved)

    def send_message(self, channel_id: str, text: str) -> Message:
        """Send a message to a Slack channel."""
        try:
            response = self._client.chat_postMessage(channel=channel_id, text=text)
            ts = str(response["ts"])
            ch = str(response["channel"])
            return Message(
                message_id=_encode_message_id(ch, ts),
                channel=ch,
                text=text,
                sender="",
                timestamp=_slack_ts_to_datetime(ts),
            )
        except SlackApiError as exc:
            msg = f"Failed to send message to {channel_id}"
            raise ValueError(msg) from exc

    def get_channels(self) -> list[Channel]:
        """List all Slack channels the bot can access."""
        try:
            response = self._client.conversations_list()
            return [
                Channel(
                    channel_id=str(ch["id"]),
                    name=str(ch["name"]),
                    is_private=bool(ch["is_private"]),
                )
                for ch in response["channels"]
            ]
        except SlackApiError:
            return []

    def get_channel(self, channel_id: str) -> Channel:
        """Get a single Slack channel by ID."""
        try:
            response = self._client.conversations_info(channel=channel_id)
            ch = response["channel"]
            return Channel(
                channel_id=str(ch["id"]),
                name=str(ch["name"]),
                is_private=bool(ch["is_private"]),
            )
        except SlackApiError as exc:
            msg = f"Channel not found: {channel_id}"
            raise ChannelNotFoundError(msg) from exc

    def get_messages(
        self,
        channel_id: str,
        limit: int = 10,
        cursor: str | None = None,
    ) -> list[Message]:
        """Get recent messages from a Slack channel."""
        try:
            if cursor:
                response = self._client.conversations_history(
                    channel=channel_id,
                    limit=limit,
                    cursor=cursor,
                )
            else:
                response = self._client.conversations_history(
                    channel=channel_id,
                    limit=limit,
                )
            return [
                Message(
                    message_id=_encode_message_id(channel_id, str(msg.get("ts", ""))),
                    channel=channel_id,
                    text=str(msg.get("text", "")),
                    sender=str(msg.get("user", "unknown")),
                    timestamp=_slack_ts_to_datetime(str(msg.get("ts", "0"))),
                )
                for msg in response["messages"]
            ]
        except SlackApiError:
            return []

    def get_message(self, message_id: str) -> Message:
        """Get a single Slack message by its encoded ID."""
        channel, ts = _decode_message_id(message_id)
        try:
            response = self._client.conversations_history(
                channel=channel,
                latest=ts,
                oldest=ts,
                limit=1,
                inclusive=True,
            )
            messages: list[Any] = response.get("messages", [])
            if not messages:
                msg = f"Message not found: {message_id}"
                raise MessageNotFoundError(msg)
            raw = messages[0]
            return Message(
                message_id=message_id,
                channel=channel,
                text=str(raw.get("text", "")),
                sender=str(raw.get("user", "unknown")),
                timestamp=_slack_ts_to_datetime(ts),
            )
        except SlackApiError as exc:
            msg = f"Message not found: {message_id}"
            raise MessageNotFoundError(msg) from exc

    def delete_message(self, message_id: str) -> None:
        """Delete a Slack message by its encoded ID."""
        channel, ts = _decode_message_id(message_id)
        try:
            self._client.chat_delete(channel=channel, ts=ts)
        except SlackApiError as exc:
            msg = f"Failed to delete message: {message_id}"
            raise MessageDeleteError(msg) from exc
