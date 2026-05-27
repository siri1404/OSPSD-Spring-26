"""In-memory session store for OAuth tokens.

Maps opaque session tokens to provider access tokens.
In production, replace with Redis or database persistence.
"""

from __future__ import annotations

# Opaque session token -> provider access token (or "pending" during OAuth flow)
active_sessions: dict[str, str] = {}
