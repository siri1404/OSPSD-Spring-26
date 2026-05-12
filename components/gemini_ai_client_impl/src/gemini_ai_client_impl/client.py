"""Gemini AI client implementation with tool calling.

This module provides a small, well-typed Gemini client that performs
tool-calling for cloud storage operations and returns either the final
assistant text (public HW-3 contract) or, when requested, the full
tool-call telemetry via `send_message_with_metadata`.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from ai_client_api import AiClientApi, AIResponse, ToolDefinition, ToolParameter
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from google import genai
from google.genai import types as genai_types

from gemini_ai_client_impl.tools import (
    dispatch_tool_call,
    get_tool_declarations,
    get_tool_definitions,
)

if TYPE_CHECKING:
    from cloud_storage_api import CloudStorageClient


class ToolLoopExhaustedError(RuntimeError):
    """Raised when the AI tool calling loop exhausts its iteration limit.

    This exception indicates that the model made the maximum number of tool
    calls without producing a final response. This typically means the model
    got into a repetitive loop or the task is inherently complex.

    Attributes:
        max_iterations: The maximum number of iterations that were attempted.
        last_action_taken: The name of the last tool that was called.
        tool_calls: List of all tool names called during this request.
        last_tool_args: Arguments passed to the last tool call.
    """

    def __init__(
        self,
        max_iterations: int,
        last_action_taken: str | None = None,
        tool_calls: list[str] | None = None,
        last_tool_args: dict[str, object] | None = None,
    ) -> None:
        """Initialize ToolLoopExhaustedError with iteration and tool call metadata."""
        self.max_iterations = max_iterations
        self.last_action_taken = last_action_taken
        self.tool_calls = tool_calls or []
        self.last_tool_args = last_tool_args
        msg = (
            f"Tool loop exhausted after {max_iterations} iterations. "
            f"Last action: {last_action_taken}. "
            f"Total tool calls: {len(self.tool_calls)}."
        )
        super().__init__(msg)


# Sentinel prefix used by tools to signal PDF payloads encoded as base64.
_PDF_BASE64_PREFIX = "PDF_CONTENT_BASE64:"


@dataclass(frozen=True)
class _ToolPayload:
    """Normalized tool result: either text or a decoded PDF blob."""

    text: str | None = None
    pdf_bytes: bytes | None = None


class GeminiAiClient(AiClientApi):
    """Gemini AI client with tool calling for cloud storage operations.

    For true multi-vertical support (e.g., AI client calling into both storage and chat),
    consider a future refactor to accept a tool_dispatcher Callable instead:

        def __init__(
            self,
            tool_dispatcher: Callable[[str, dict], str],
            ...
        ) -> None:

    This dispatcher pattern would decouple the AI client from specific implementations,
    allowing consumers to compose tools from multiple domains. See Team 5's pattern for
    an example implementation.
    """

    MAX_TOOL_ITERATIONS: int = 10

    def __init__(
        self,
        storage_client: CloudStorageClient,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        """Initialize Gemini AI client with storage and model configuration.

        Args:
            storage_client: CloudStorageClient for tool execution.
            api_key: Gemini API key. Falls back to GEMINI_API_KEY env var.
            model_name: Gemini model identifier (default: gemini-2.5-flash).

        Raises:
            ValueError: If GEMINI_API_KEY is not available.
        """
        self._storage_client = storage_client
        self._model_name = model_name
        resolved_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            msg = "GEMINI_API_KEY must be provided or set in environment variables."
            raise ValueError(msg)

        self._genai_client = genai.Client(api_key=resolved_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def send_message(self, prompt: str, context: dict[str, object] | None = None) -> str:
        """Return the assistant's final text response (HW-3 shared contract).

        Raises:
            ValueError: If context is malformed.
            RuntimeError: If a storage tool fails or a payload is invalid.
            ToolLoopExhaustedError: If tool calling exhausts the iteration limit.
        """
        final_text, _, _, _ = self._run_send_message(prompt, context)
        return final_text

    def send_message_with_metadata(
        self, prompt: str, context: dict[str, object] | None = None
    ) -> AIResponse:
        """Return final text plus tool-call telemetry for callers that need it.

        Raises:
            ValueError: If context is malformed.
            RuntimeError: If a storage tool fails or a payload is invalid.
            ToolLoopExhaustedError: If tool calling exhausts the iteration limit.
        """
        final_text, action_taken, tool_calls, tool_args = self._run_send_message(prompt, context)
        return AIResponse(
            text=final_text,
            action_taken=action_taken,
            tool_calls=tool_calls,
            tool_args=cast("dict[str, Any]", tool_args or {}),
        )

    def tools(self) -> list[ToolDefinition]:
        """Return the list of available tools for this AI client.

        This exposes the tool definitions so callers can inspect what the
        Gemini client can do (e.g., list_files, upload_file, etc.) without
        invoking send_message. Each tool includes a description and parameter
        schema for validation and discovery.

        Returns:
            A list of ToolDefinition objects describing each available tool.

        Example:
            >>> client = GeminiAiClient(storage_client)
            >>> for tool in client.tools():
            ...     print(f"Tool: {tool.name}")
            ...     for param in tool.parameters:
            ...         print(f"  - {param.name} ({param.type}): {param.description}")
        """
        tool_defs = get_tool_definitions()
        result: list[ToolDefinition] = []

        for tool_dict in tool_defs:
            # Extract parameters from the JSON schema
            parameters: list[ToolParameter] = []
            properties = tool_dict.get("parameters", {}).get("properties", {})
            required = tool_dict.get("parameters", {}).get("required", [])

            for param_name, param_schema in properties.items():
                param = ToolParameter(
                    name=param_name,
                    type=param_schema.get("type", "string"),
                    description=param_schema.get("description", ""),
                    required=param_name in required,
                )
                parameters.append(param)

            tool_def = ToolDefinition(
                name=tool_dict["name"],
                description=tool_dict["description"],
                parameters=parameters,
            )
            result.append(tool_def)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_context(context: dict[str, object] | None) -> str | None:
        """Validate optional context and return the container when present.

        Raises ValueError when `context['container']` is present but invalid.
        """
        if context is None:
            return None
        container = context.get("container")
        if container is None:
            return None
        if not isinstance(container, str) or not container.strip():
            msg = "context['container'] must be a non-empty string"
            raise ValueError(msg)
        return container

    @staticmethod
    def _build_prompt(prompt: str, container: str | None) -> str:
        """Augment the prompt with container context when available."""
        if container is None:
            return prompt
        return (
            f"Container: {container}\n"
            f"Request: {prompt}\n"
            "Respond concisely. Use the provided container directly. "
            "Do not ask for clarification or repeat the container name "
            "unless it is needed for the result. Prefer bullet list or JSON-style output."
        )

    @staticmethod
    def _build_config() -> genai_types.GenerateContentConfig:
        """Build the Gemini generation config with declared tools."""
        system_instruction = (
            "You are a cloud storage assistant, not a general conversational chatbot. "
            "Use the provided tools to fulfill storage-related requests. "
            "If a container is provided in context, treat it as authoritative "
            "and never ask for it again. "
            "Do not ask clarifying questions when the container is already provided. "
            "Return only relevant storage results, with concise bullet lists or "
            "JSON-style formatting when useful. "
            "Avoid conversational filler and extra commentary."
        )
        return genai_types.GenerateContentConfig(
            tools=cast("list[genai_types.Tool | Any]", get_tool_declarations()),
            system_instruction=system_instruction,
        )

    @staticmethod
    def _decode_pdf(base64_content: str, source: str) -> bytes:
        """Decode a base64 PDF payload, raising RuntimeError on failure."""
        try:
            return base64.b64decode(base64_content, validate=True)
        except (binascii.Error, ValueError) as exc:
            msg = f"Invalid PDF base64 encoding from {source}: {exc}"
            raise RuntimeError(msg) from exc

    @classmethod
    def _normalize_tool_result(cls, tool_name: str, raw: str) -> _ToolPayload:
        """Translate a raw tool string into a typed payload."""
        if raw.startswith(_PDF_BASE64_PREFIX):
            prefix_len = len(_PDF_BASE64_PREFIX)
            pdf_bytes = cls._decode_pdf(raw[prefix_len:], source=f"{tool_name} tool result")
            return _ToolPayload(pdf_bytes=pdf_bytes)
        return _ToolPayload(text=raw)

    @staticmethod
    def _payload_to_parts(tool_name: str, payload: _ToolPayload) -> list[genai_types.Part]:
        """Convert a typed tool payload into Gemini function-response parts."""
        if payload.pdf_bytes is not None:
            return [
                genai_types.Part.from_function_response(
                    name=tool_name, response={"result": "PDF received"}
                ),
                genai_types.Part.from_bytes(data=payload.pdf_bytes, mime_type="application/pdf"),
            ]
        return [
            genai_types.Part.from_function_response(
                name=tool_name, response={"result": payload.text}
            )
        ]

    @staticmethod
    def _extract_final_text(response: genai_types.GenerateContentResponse) -> str:
        """Extract the final text from a Gemini response, logging when empty.

        Args:
            response: The Gemini GenerateContentResponse.

        Returns:
            The response text if present, or a fallback message if empty.

        Note:
            When no text is available, a warning is logged. Callers should
            check for this condition and handle it appropriately (e.g., by
            catching ToolLoopExhaustedError or checking if the response
            looks like a fallback message).
        """
        text = response.text
        if text:
            return text
        logger = logging.getLogger(__name__)
        logger.warning(
            "Gemini returned an empty response. "
            "The model may have encountered an error or constraint."
        )
        return "No response generated."

    def _dispatch_tool(self, tool_name: str, tool_args: dict[str, object]) -> str:
        """Dispatch a tool call, surfacing storage errors as RuntimeError."""
        try:
            return dispatch_tool_call(tool_name, tool_args, self._storage_client)
        except (
            AuthenticationError,
            ContainerNotFoundError,
            InvalidContainerError,
            InvalidFileObjectError,
            InvalidObjectNameError,
            LocalFileAccessError,
            ObjectNotFoundError,
            StorageBackendError,
        ) as exc:
            msg = f"Storage operation failed: {exc}"
            raise RuntimeError(msg) from exc

    def _run_send_message(
        self,
        prompt: str,
        context: dict[str, object] | None = None,
    ) -> tuple[str, str | None, list[str], dict[str, object] | None]:
        """Drive the tool-calling loop and return final text plus telemetry.

        Returns a 4-tuple (final_text, last_action_taken, tool_calls, last_tool_args).
        """
        container = self._validate_context(context)
        config = self._build_config()
        chat = self._genai_client.chats.create(model=self._model_name, config=config)
        final_prompt = self._build_prompt(prompt, container)
        response: genai_types.GenerateContentResponse = chat.send_message(final_prompt)

        last_action_taken: str | None = None
        tool_calls: list[str] = []
        last_tool_args: dict[str, object] | None = None

        for _ in range(self.MAX_TOOL_ITERATIONS):
            candidates = getattr(response, "candidates", None)
            if not candidates:
                break

            candidate = candidates[0]
            if candidate.content is None or not candidate.content.parts:
                break

            function_response_parts: list[genai_types.Part] = []
            has_function_call = False

            for part in candidate.content.parts:
                function_call = part.function_call
                if not function_call:
                    continue

                # function_call.name is typed `str | None` by the SDK
                if not function_call.name:
                    continue

                has_function_call = True
                tool_name: str = function_call.name
                tool_args: dict[str, object] = dict(function_call.args or {})

                if container is not None and "container" not in tool_args:
                    tool_args["container"] = container

                last_action_taken = tool_name
                tool_calls.append(tool_name)
                last_tool_args = dict(tool_args)

                tool_result = self._dispatch_tool(tool_name, tool_args)
                payload = self._normalize_tool_result(tool_name, tool_result)
                function_response_parts.extend(self._payload_to_parts(tool_name, payload))

            if not has_function_call:
                break

            if function_response_parts:
                response = chat.send_message(function_response_parts)
        else:
            # All MAX_TOOL_ITERATIONS consumed without the model producing a final answer.
            msg = (
                f"Tool loop exhausted after {self.MAX_TOOL_ITERATIONS} iterations. "
                f"Model did not produce a final response."
            )
            logger = logging.getLogger(__name__)
            logger.warning(msg)
            raise ToolLoopExhaustedError(
                max_iterations=self.MAX_TOOL_ITERATIONS,
                last_action_taken=last_action_taken,
                tool_calls=tool_calls,
                last_tool_args=last_tool_args,
            )

        return (self._extract_final_text(response), last_action_taken, tool_calls, last_tool_args)
