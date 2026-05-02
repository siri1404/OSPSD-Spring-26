"""Unit tests for AI client API interface."""

from __future__ import annotations

from typing import Any

import pytest
from ai_client_api import AiClientApi


@pytest.mark.unit
def test_ai_client_api_cannot_be_instantiated() -> None:
    """Test that AiClientApi cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AiClientApi()  # type: ignore[abstract]


@pytest.mark.unit
def test_subclass_without_send_message_cannot_be_instantiated() -> None:
    """Test that a subclass without send_message implementation cannot be instantiated."""

    class IncompleteClient(AiClientApi):
        pass

    with pytest.raises(TypeError):
        IncompleteClient()  # type: ignore[abstract]


@pytest.mark.unit
def test_properly_implemented_subclass_can_be_instantiated() -> None:
    """Test that a properly implemented subclass can be instantiated."""

    class CompleteClient(AiClientApi):
        def send_message(
            self,
            prompt: str,
            context: dict[str, Any] | None = None,
        ) -> str:
            return "response"

    client = CompleteClient()
    assert isinstance(client, AiClientApi)


@pytest.mark.unit
def test_send_message_can_be_called_on_subclass() -> None:
    """Test that send_message can be called on a properly implemented subclass."""

    class TestClient(AiClientApi):
        def send_message(
            self,
            prompt: str,
            context: dict[str, Any] | None = None,
        ) -> str:
            if context and "container" in context:
                return f"Using {context['container']}: {prompt}"
            return prompt

    client = TestClient()
    result = client.send_message("list files")
    assert isinstance(result, str)
    assert result == "list files"

    result_with_context = client.send_message("list files", context={"container": "my-bucket"})
    assert isinstance(result_with_context, str)
    assert result_with_context == "Using my-bucket: list files"


@pytest.mark.unit
def test_send_message_signature_accepts_optional_context() -> None:
    """Test that send_message signature accepts prompt and optional context."""

    class TestClient(AiClientApi):
        def send_message(
            self,
            prompt: str,
            context: dict[str, Any] | None = None,
        ) -> str:
            return "ok"

    client = TestClient()
    # Should work with just prompt
    r1 = client.send_message("test")
    assert isinstance(r1, str)
    assert r1 == "ok"
    # Should work with prompt and context
    r2 = client.send_message("test", context={"key": "value"})
    assert isinstance(r2, str)
    assert r2 == "ok"
    # Should work with context as kwarg
    r3 = client.send_message(prompt="test", context={"key": "value"})
    assert isinstance(r3, str)
    assert r3 == "ok"
