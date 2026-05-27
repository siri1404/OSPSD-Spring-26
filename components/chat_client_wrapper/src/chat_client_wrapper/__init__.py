"""Chat client wrapper for cross-vertical notifications."""

from __future__ import annotations

from .notifications import NotificationMessages
from .wrapper import ChatNotificationWrapper

__all__ = ["ChatNotificationWrapper", "NotificationMessages"]
