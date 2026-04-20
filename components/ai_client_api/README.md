# ai-client-api

Abstract interface for AI client implementations with tool calling support.

## Overview

This component defines the `AiClientApi` abstract base class, which standardizes how AI chat completion clients are integrated into the cloud storage service and other systems.

## Interface

The `AiClientApi` defines a single abstract method:

- `send_message(prompt: str, context: dict[str, Any] | None = None) -> str` — Send a natural language prompt and receive a human-readable response. The optional context dict can carry configuration like default container names.

## Role

This interface enables:
- Pluggable AI providers (Gemini, OpenAI, Claude, etc.)
- Clean dependency injection in FastAPI services
- Tool-calling abstractions for domain-specific actions
- Provider agnosticism in service business logic

## Usage

Concrete implementations inherit from `AiClientApi` and implement the `send_message` method. Each implementation manages its own dependencies (e.g., storage client, API keys, model configuration).

```python
from ai_client_api import AiClientApi

class MyAiClient(AiClientApi):
    def send_message(self, prompt: str, context=None) -> str:
        # Implementation
        return "response"
```
