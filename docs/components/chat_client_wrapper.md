# Chat Client Wrapper

Notification wrapper on top of Team 9's shared ChatClient abstraction.

## Overview

The chat_client_wrapper component provides a simple `notify()` method for sending storage event notifications to any chat provider that implements the shared ChatClient ABC.

## Key Classes

**ChatNotificationWrapper** — Accepts any ChatClient implementation and a channel ID. Calls `notify(message)` to send formatted notifications.

**NotificationMessages** — Static message formatters for storage events:
- `file_uploaded(container, object_name, size_bytes)`
- `file_deleted(container, object_name)`
- `ai_action_performed(action, container, object_name, result)`
- `error_occurred(error_type, message, context)`

## Configuration

- `CHAT_CHANNEL_ID` env var (or constructor argument)
- `SLACK_BOT_TOKEN` env var (for the Slack implementation)

## Error Resilience

Notification failures are swallowed by `safe_notify()` in main.py — storage operations always succeed even if chat is down.

## Dependency

```
chat-client-api = { git = "https://github.com/HarshithKoriRaj/Shared-API.git", rev = "ebb37e1..." }
```
