"""Unit tests for AI client API interface."""

from __future__ import annotations

from typing import Any

import pytest
from ai_client_api import AiClientApi, AIResponse


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
        ) -> AIResponse:
            return AIResponse(text="response", action_taken=None, tool_calls=[])

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
        ) -> AIResponse:
            if context and "container" in context:
                return AIResponse(text=f"Using {context['container']}: {prompt}", action_taken=None, tool_calls=[])
            return AIResponse(text=prompt, action_taken=None, tool_calls=[])

    client = TestClient()
    result = client.send_message("list files")
    assert isinstance(result, AIResponse)
    assert result.text == "list files"

    result_with_context = client.send_message("list files", context={"container": "my-bucket"})
    assert isinstance(result_with_context, AIResponse)
    assert result_with_context.text == "Using my-bucket: list files"


@pytest.mark.unit
def test_send_message_signature_accepts_optional_context() -> None:
    """Test that send_message signature accepts prompt and optional context."""

    class TestClient(AiClientApi):
        def send_message(
            self,
            prompt: str,
            context: dict[str, Any] | None = None,
        ) -> AIResponse:
            return AIResponse(text="ok", action_taken=None, tool_calls=[])

    client = TestClient()
    # Should work with just prompt
    r1 = client.send_message("test")
    assert isinstance(r1, AIResponse)
    assert r1.text == "ok"
    # Should work with prompt and context
    r2 = client.send_message("test", context={"key": "value"})
    assert isinstance(r2, AIResponse)
    assert r2.text == "ok"
    # Should work with context as kwarg
    r3 = client.send_message(prompt="test", context={"key": "value"})
    assert isinstance(r3, AIResponse)
    assert r3.text == "ok"
