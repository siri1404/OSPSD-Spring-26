"""Gemini AI client implementation with tool calling."""

from __future__ import annotations

import base64
import os
from typing import Any, cast

from ai_client_api import AiClientApi
from cloud_storage_api import CloudStorageClient  # noqa: TC002
from cloud_storage_api.exceptions import (
    AuthenticationError,
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
        self._context: dict[str, Any] | None = None

        # Get API key
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            msg = "GEMINI_API_KEY must be provided or set in environment variables."
            raise ValueError(msg)

        self._genai_client = genai.Client(api_key=api_key, vertexai=True)

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

    def send_message(  # noqa: C901, PLR0912
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Send a prompt to Gemini and handle tool calling.

        Args:
            prompt: User's natural language request.
            context: Optional context dict (e.g., {"container": "my-bucket"}).

        Returns:
            Human-readable response string.

        Raises:
            RuntimeError: If cloud storage operations fail.
        """
        if genai is None:
            msg = "google-genai not available"
            raise ImportError(msg)

        self._context = context

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

                        # Inject context container if not provided
                        if context and "container" in context and "container" not in tool_args:
                            tool_args["container"] = context["container"]

                        # Call the tool
                        try:
                            tool_result = dispatch_tool_call(tool_name, tool_args, self._storage_client)
                        except (
                            AuthenticationError,
                            ObjectNotFoundError,
                            StorageBackendError,
                        ) as exc:
                            msg = f"Storage operation failed: {exc}"
                            raise RuntimeError(msg) from exc

                        # Handle PDF base64 content
                        if tool_name == "summarize_file":
                            summarize_prompt = (
                                "Summarize the following file in 5-7 bullet points. "
                                "Return only the summary, with no extra commentary.\n\n"
                                f"{tool_result}"
                            )

                            if tool_result.startswith("PDF_CONTENT_BASE64:"):
                                base64_content = tool_result[len("PDF_CONTENT_BASE64:") :]
                                pdf_bytes = base64.b64decode(base64_content)

                                response = chat.send_message(
                                    [
                                        summarize_prompt,
                                        genai_types.Part.from_bytes(
                                            data=pdf_bytes,
                                            mime_type="application/pdf",
                                        ),
                                    ]
                                )
                            else:
                                response = chat.send_message(summarize_prompt)
                        elif tool_result.startswith("PDF_CONTENT_BASE64:"):
                            base64_content = tool_result[len("PDF_CONTENT_BASE64:") :]
                            pdf_bytes = base64.b64decode(base64_content)

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
            return "Could not complete the request after maximum tool call iterations."

        return self._extract_final_text(response)
