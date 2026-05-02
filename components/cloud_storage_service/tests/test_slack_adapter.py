"""Tests for Slack adapter implementation.

Verifies SlackChatClient ABC compliance, including:
- Proper initialization and token handling
- Message timestamp is timezone-aware datetime (not string)
- Exception types match the chat_client_api ABC
- Auth/rate-limit failures don't masquerade as "not found"
- Message ID encoding/decoding roundtrip
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock

import pytest
from chat_client_api import ChannelNotFoundError, MessageDeleteError, MessageNotFoundError
from cloud_storage_service.slack_adapter import SlackChatClient, _decode_message_id, _encode_message_id, _slack_ts_to_datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def _slack_error(code: str, message: str = "error") -> SlackApiError:
    """Build a SlackApiError whose response carries a structured error code."""
    response = MagicMock()
    response.get.return_value = code
    return SlackApiError(message=message, response=response)  # type: ignore[no-untyped-call]


def _make_client(web_client: MagicMock | None = None) -> SlackChatClient:
    """Construct a SlackChatClient with an injected mock WebClient."""
    return SlackChatClient(web_client=web_client or MagicMock(spec=WebClient))


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_init_without_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Init raises ValueError when no token is provided and no env var is set."""
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

    with pytest.raises(ValueError, match="SLACK_BOT_TOKEN"):
        SlackChatClient(token=None)


@pytest.mark.unit
def test_init_with_explicit_token_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit token argument overrides the SLACK_BOT_TOKEN env var."""
    explicit_token = "xoxb-explicit-token-12345"
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-env-token")

    fake_web_client = MagicMock(spec=WebClient)
    with monkeypatch.context() as mp:
        mp.setattr(
            "cloud_storage_service.slack_adapter.WebClient",
            MagicMock(return_value=fake_web_client),
        )
        client = SlackChatClient(token=explicit_token)

        # The injected WebClient is what subsequent methods use.
        assert client.client is fake_web_client


@pytest.mark.unit
def test_init_falls_back_to_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Init falls back to SLACK_BOT_TOKEN env var when no token is supplied."""
    env_token = "xoxb-env-token-67890"
    monkeypatch.setenv("SLACK_BOT_TOKEN", env_token)

    captured: dict[str, str] = {}

    def fake_web_client_factory(token: str) -> MagicMock:
        captured["token"] = token
        return MagicMock(spec=WebClient)

    monkeypatch.setattr(
        "cloud_storage_service.slack_adapter.WebClient",
        fake_web_client_factory,
    )

    SlackChatClient(token=None)

    assert captured["token"] == env_token


@pytest.mark.unit
def test_init_accepts_injected_web_client() -> None:
    """Init uses the injected web_client and skips token resolution entirely."""
    fake = MagicMock(spec=WebClient)

    client = SlackChatClient(web_client=fake)

    assert client.client is fake


# ---------------------------------------------------------------------------
# Message timestamp ABC compliance
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_send_message_returns_datetime_timestamp() -> None:
    """send_message returns a Message with a timezone-aware UTC datetime timestamp."""
    fake = MagicMock(spec=WebClient)
    fake.chat_postMessage.return_value = {
        "ts": "1234567890.123456",
        "channel": "C1234567890",
    }
    client = _make_client(fake)

    message = client.send_message("C1234567890", "Hello World")

    assert isinstance(message.timestamp, datetime)
    assert message.timestamp.tzinfo is not None
    assert message.timestamp.utcoffset() == UTC.utcoffset(None)
    assert message.text == "Hello World"
    assert message.channel == "C1234567890"
    assert message.message_id


@pytest.mark.unit
def test_get_messages_returns_datetime_timestamps() -> None:
    """get_messages returns Messages with timezone-aware UTC datetime timestamps."""
    fake = MagicMock(spec=WebClient)
    fake.conversations_history.return_value = {
        "messages": [
            {
                "ts": "1234567890.000000",
                "text": "Message 1",
                "user": "U1234567890",
            },
            {
                "ts": "1234567891.000000",
                "text": "Message 2",
                "user": "U0987654321",
            },
        ]
    }
    client = _make_client(fake)

    messages = client.get_messages("C1234567890", limit=10)

    assert len(messages) == 2
    for msg in messages:
        assert isinstance(msg.timestamp, datetime)
        assert msg.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# Exception routing
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_send_message_channel_not_found_raises_channel_not_found_error() -> None:
    """send_message routes channel_not_found to ChannelNotFoundError."""
    fake = MagicMock(spec=WebClient)
    fake.chat_postMessage.side_effect = _slack_error("channel_not_found")
    client = _make_client(fake)

    with pytest.raises(ChannelNotFoundError, match="C1234567890"):
        client.send_message("C1234567890", "Hello")


@pytest.mark.unit
def test_send_message_unknown_error_raises_runtime_error() -> None:
    """send_message routes unknown Slack errors to RuntimeError, not ChannelNotFoundError."""
    fake = MagicMock(spec=WebClient)
    fake.chat_postMessage.side_effect = _slack_error("rate_limited")
    client = _make_client(fake)

    with pytest.raises(RuntimeError, match="rate_limited"):
        client.send_message("C1234567890", "Hello")


@pytest.mark.unit
def test_get_channel_not_found_raises_channel_not_found_error() -> None:
    """get_channel routes channel_not_found to ChannelNotFoundError."""
    fake = MagicMock(spec=WebClient)
    fake.conversations_info.side_effect = _slack_error("channel_not_found")
    client = _make_client(fake)

    with pytest.raises(ChannelNotFoundError, match="C1234567890"):
        client.get_channel("C1234567890")


@pytest.mark.unit
def test_get_channel_auth_failure_raises_runtime_error() -> None:
    """get_channel routes auth failures to RuntimeError, not ChannelNotFoundError."""
    fake = MagicMock(spec=WebClient)
    fake.conversations_info.side_effect = _slack_error("invalid_auth")
    client = _make_client(fake)

    with pytest.raises(RuntimeError, match="invalid_auth"):
        client.get_channel("C1234567890")


@pytest.mark.unit
def test_get_channels_failure_raises_runtime_error() -> None:
    """get_channels raises RuntimeError on Slack API failure (no silent empty list)."""
    fake = MagicMock(spec=WebClient)
    fake.conversations_list.side_effect = _slack_error("invalid_auth")
    client = _make_client(fake)

    with pytest.raises(RuntimeError, match="invalid_auth"):
        client.get_channels()


@pytest.mark.unit
def test_get_message_empty_response_raises_message_not_found_error() -> None:
    """get_message raises MessageNotFoundError when Slack returns no messages."""
    fake = MagicMock(spec=WebClient)
    fake.conversations_history.return_value = {"messages": []}
    client = _make_client(fake)

    with pytest.raises(MessageNotFoundError, match=r"C1234567890:1234567890\.000000"):
        client.get_message("C1234567890:1234567890.000000")


@pytest.mark.unit
def test_get_message_api_error_raises_message_not_found_error() -> None:
    """get_message routes Slack message_not_found errors to MessageNotFoundError."""
    fake = MagicMock(spec=WebClient)
    fake.conversations_history.side_effect = _slack_error("message_not_found")
    client = _make_client(fake)

    with pytest.raises(MessageNotFoundError):
        client.get_message("C1234567890:1234567890.000000")


@pytest.mark.unit
def test_delete_message_api_error_raises_message_delete_error() -> None:
    """delete_message wraps Slack API errors as MessageDeleteError."""
    fake = MagicMock(spec=WebClient)
    fake.chat_delete.side_effect = _slack_error("message_not_found")
    client = _make_client(fake)

    with pytest.raises(MessageDeleteError, match=r"C1234567890:1234567890\.000000"):
        client.delete_message("C1234567890:1234567890.000000")


# ---------------------------------------------------------------------------
# Message ID encoding/decoding
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_encode_decode_message_id_roundtrip() -> None:
    """_encode_message_id and _decode_message_id are inverse operations."""
    channel = "C1234567890"
    ts = "1234567890.123456"

    encoded = _encode_message_id(channel, ts)
    decoded_channel, decoded_ts = _decode_message_id(encoded)

    assert decoded_channel == channel
    assert decoded_ts == ts


@pytest.mark.unit
def test_decode_message_id_rejects_malformed_input() -> None:
    """_decode_message_id raises ValueError for malformed IDs."""
    with pytest.raises(ValueError, match="Invalid message_id format"):
        _decode_message_id("malformed_id_no_separator")

    with pytest.raises(ValueError, match="Invalid message_id format"):
        _decode_message_id("")


@pytest.mark.unit
def test_decode_message_id_preserves_dots_in_timestamp() -> None:
    """_decode_message_id splits only on the first separator, preserving dots in ts."""
    channel = "C999999999"
    ts = "1234567890.999999"

    encoded = _encode_message_id(channel, ts)
    decoded_channel, decoded_ts = _decode_message_id(encoded)

    assert decoded_channel == channel
    assert decoded_ts == ts
    assert "." in decoded_ts


# ---------------------------------------------------------------------------
# Slack ts → datetime
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_slack_ts_to_datetime_returns_utc_datetime() -> None:
    """_slack_ts_to_datetime returns a UTC datetime preserving the epoch value."""
    ts = "1234567890.123456"

    dt = _slack_ts_to_datetime(ts)

    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None
    assert dt.timestamp() == 1234567890.123456


@pytest.mark.unit
@pytest.mark.parametrize(
    ("ts_str", "expected_epoch"),
    [
        ("1234567890.000000", 1234567890.0),
        ("1609459200.123456", 1609459200.123456),
        ("1000000000.999999", 1000000000.999999),
    ],
)
def test_slack_ts_to_datetime_handles_various_precisions(
    ts_str: str,
    expected_epoch: float,
) -> None:
    """_slack_ts_to_datetime handles timestamps with different fractional precisions."""
    dt = _slack_ts_to_datetime(ts_str)

    assert dt.timestamp() == expected_epoch
    assert dt.tzinfo is not None
