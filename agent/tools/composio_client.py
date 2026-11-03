"""
agent/tools/composio_client.py
---------------------------------
Shared Composio client for this project's live integrations (step 7).
Composio replaces a from-scratch Google OAuth flow and raw Trello REST
calls with a managed connection layer, at the user's explicit request
mid-project.

Env vars (.env):
  COMPOSIO_API_KEY  -- required for any --tools live call.
  COMPOSIO_USER_ID  -- identifies which connected accounts to use
                       (default: "meeting-action-router"). Composio
                       stores the actual OAuth tokens server-side,
                       keyed by this user_id + toolkit -- unlike the
                       raw-OAuth plan this replaced, there is no local
                       token cache file for this project to manage.

One-time setup per toolkit (GOOGLECALENDAR, GMAIL, TRELLO), BEFORE any
live run can use it:
    python scripts/composio_connect.py --toolkit GOOGLECALENDAR
This opens a browser consent URL and blocks until a human approves it.
Nothing in this project ever calls toolkits.authorize() automatically
-- connecting an account is a deliberate, one-time, human-in-the-loop
action, never something the agent does on its own.
"""

from __future__ import annotations

import os
from functools import lru_cache

from composio import Composio

DEFAULT_USER_ID = "meeting-action-router"


@lru_cache(maxsize=1)
def get_client() -> Composio:
    api_key = os.environ.get("COMPOSIO_API_KEY")
    if not api_key:
        raise RuntimeError("COMPOSIO_API_KEY is not set (.env) -- required for any --tools live call.")
    return Composio(api_key=api_key)


def get_user_id() -> str:
    return os.environ.get("COMPOSIO_USER_ID") or DEFAULT_USER_ID
