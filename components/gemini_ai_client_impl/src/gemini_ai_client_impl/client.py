"""Gemini AI client implementation with tool calling."""

from __future__ import annotations

import base64
import binascii
import os
from typing import Any, cast

from ai_client_api import AiClientApi, AIResponse
from cloud_storage_api import CloudStorageClient  # noqa: TC002
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

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

from gemini_ai_client_impl.tools import dispatch_tool_call, get_tool_declarations


class GeminiAiClient(AiClientApi):
    """Gemini AI client with tool calling for cloud storage operations."""

    def __init__(
        self,
        storage_client: CloudStorageClient,
        api_key: str | None = None,
        # Updated to Gemini 2.5 Flash (2026 supported model)
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        """Initialize Gemini AI client.

        Args:
            storage_client: CloudStorageClient instance for tool operations.
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var).
            model_name: Gemini model name to use.

        Raises:
            ValueError: If API key is not provided and GEMINI_API_KEY is not set.
        """
        if genai is None:
            msg = "google-generativeai is not installed. Install it with: uv sync"
            raise ImportError(msg)

        self._storage_client = storage_client
        self._model_name = model_name

        # Get API key
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            msg = "GEMINI_API_KEY must be provided or set in environment variables."
            raise ValueError(msg)

        self._genai_client = genai.Client(api_key=api_key)

    def _extract_final_text(self, response: Any) -> str:  # noqa: ANN401
        """Extract final text response from Gemini response.

        Args:
            response: Gemini response object.

        Returns:
            Extracted text or default message.
        """
        if response.text:
            return cast("str", response.text)
        return "No response generated."

    def send_message(  # noqa: C901, PLR0912, PLR0915
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AIResponse:
        """Send a prompt to Gemini and handle tool calling.

        Args:
            prompt: User's natural language request.
            context: Optional context dict (e.g., {"container": "my-bucket"}).

        Returns:
            AIResponse containing text, action_taken, and tool_calls list.

        Raises:
            RuntimeError: If cloud storage operations fail.
        """
        if genai is None:
            msg = "google-genai not available"
            raise ImportError(msg)

        # Validate context schema (ensure non-empty container when provided)
        if (
            context
            and "container" in context
            and (
                not isinstance(context["container"], str)
                or not context["container"].strip()
            )
        ):
            msg = "context['container'] must be a non-empty string"
            raise ValueError(msg)

        config = genai_types.GenerateContentConfig(
            tools=get_tool_declarations(),
            system_instruction=(
                "You are a cloud storage assistant, not a general conversational chatbot. "
                "Use the provided tools to fulfill storage-related requests. "
                "If a container is provided in context, treat it as authoritative and never ask for it again. "
                "Do not ask clarifying questions when the container is already provided. "
                "Return only relevant storage results, with concise bullet lists or JSON-style formatting when useful. "
                "Avoid conversational filler and extra commentary."
            ),
        )

        chat = self._genai_client.chats.create(
            model=self._model_name,
            config=config,
        )
        if context and "container" in context:
            prompt = (
                f"Container: {context['container']}\n"
                f"Request: {prompt}\n"
                "Respond concisely. Use the provided container directly. "
                "Do not ask for clarification or repeat the container name unless it is needed for the result. "
                "Prefer bullet list or JSON-style output for file listings."
            )

        response: Any = chat.send_message(prompt)

        # Track tool calls and the last action taken and last tool args
        last_action_taken: str | None = None
        tool_calls: list[str] = []
        last_tool_args: dict[str, Any] | None = None

        # Tool-calling loop (max 10 iterations)
        max_iterations = 10
        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            if response.candidates:
                has_function_call = False

                for part in response.candidates[0].content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        has_function_call = True
                        tool_name = cast("str", part.function_call.name)
                        tool_args = dict(cast("dict[str, Any]", part.function_call.args))

                        # Track this tool call and its args
                        last_action_taken = tool_name
                        tool_calls.append(tool_name)
                        last_tool_args = dict(tool_args)

                        # Inject context container if not provided
                        if context and "container" in context and "container" not in tool_args:
                            tool_args["container"] = context["container"]

                        # Call the tool
                        try:
                            tool_result = dispatch_tool_call(tool_name, tool_args, self._storage_client)
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

                        # Handle summarize_file specially (use function response parts)
                        if tool_name == "summarize_file":
                            if tool_result.startswith("PDF_CONTENT_BASE64:"):
                                base64_content = tool_result[len("PDF_CONTENT_BASE64:") :]
                                try:
                                    pdf_bytes = base64.b64decode(base64_content, validate=True)
                                except (binascii.Error, ValueError) as exc:
                                    msg = f"Invalid PDF base64 encoding from summarize_file: {exc}"
                                    raise RuntimeError(msg) from exc

                                response = chat.send_message(
                                    [
                                        genai_types.Part.from_function_response(
                                            name=tool_name,
                                            response={"result": "PDF received"},
                                        ),
                                        genai_types.Part.from_bytes(
                                            data=pdf_bytes,
                                            mime_type="application/pdf",
                                        ),
                                    ]
                                )
                            else:
                                # For text-based summaries, present the tool result as a function response
                                response = chat.send_message(
                                    genai_types.Part.from_function_response(
                                        name=tool_name,
                                        response={"result": tool_result},
                                    )
                                )
                        elif tool_result.startswith("PDF_CONTENT_BASE64:"):
                            base64_content = tool_result[len("PDF_CONTENT_BASE64:") :]
                            try:
                                pdf_bytes = base64.b64decode(base64_content, validate=True)
                            except (binascii.Error, ValueError) as exc:
                                msg = f"Invalid PDF base64 encoding from tool result: {exc}"
                                raise RuntimeError(msg) from exc

                            response = chat.send_message(
                                [
                                    genai_types.Part.from_function_response(
                                        name=tool_name,
                                        response={"result": "PDF received"},
                                    ),
                                    genai_types.Part.from_bytes(
                                        data=pdf_bytes,
                                        mime_type="application/pdf",
                                    ),
                                ]
                            )
                        else:
                            response = chat.send_message(
                                genai_types.Part.from_function_response(
                                    name=tool_name,
                                    response={"result": tool_result},
                                )
                            )

                if not has_function_call:
                    break
            else:
                break

        # Check if we hit max iterations
        if iteration >= max_iterations:
            return AIResponse(
                text="Could not complete the request after maximum tool call iterations.",
                action_taken=last_action_taken,
                tool_calls=tool_calls,
                tool_args=last_tool_args,
            )

        final_text = self._extract_final_text(response)
        return AIResponse(
            text=final_text,
            action_taken=last_action_taken,
            tool_calls=tool_calls,
            tool_args=last_tool_args,
        )
