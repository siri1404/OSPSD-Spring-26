"""In-memory session store for OAuth tokens and pending login states.

Two stores are maintained:

- pending_oauth_states — CSRF state tokens issued by /auth/login and consumed
  (validated and discarded) by /auth/callback.
- active_sessions — opaque session token → provider access token, populated by
  /auth/callback after a successful code exchange.

Both stores are in-memory and process-local; they don't survive restarts and
don't sync across multi-instance deployments. Replace with Redis or signed JWTs
for true multi-instance production use.
"""

from __future__ import annotations

# CSRF state tokens awaiting OAuth callback validation.
# A state in this set proves the callback came from a login flow we initiated.
pending_oauth_states: set[str] = set()

# Opaque session tokens mapped to their underlying provider access tokens.
# The provider token is never exposed to clients — they only ever see the
# opaque session ID returned by /auth/callback.
active_sessions: dict[str, str] = {}
