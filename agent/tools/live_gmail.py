"""
agent/tools/live_gmail.py
----------------------------
Live Gmail drafts adapter (step 7, stretch goal), via Composio. Same
method names/signatures as agent/tools/mock_backend.py:MockGmailDrafts
(create_email_draft, get_draft). Drafts only -- this never calls a
"send" action, matching the spec's gmail.compose-scope-only limit.

Idempotency: same pattern as agent/tools/live_calendar.py --
agent/tools/idempotency_store.py keyed by idempotency_key -> draft_id.

Known limitation, disclosed: Composio's GMAIL_CREATE_EMAIL_DRAFT
action takes a single `recipient_email` (per Composio's docs as of
2026-11-03), not a list -- unlike our schema's `to: list[str]`. This
adapter maps the first address to `recipient_email` and any additional
addresses to `cc`, which is NOT the same as multiple primary
recipients. Verify against a live account with
scripts/verify_composio_tools.py before trusting this for a real
multi-recipient draft; for this project's data, every gold email_draft
item has exactly one recipient, so this has not been exercised with
more than one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agent.tools.composio_client import get_client, get_user_id
from agent.tools.composio_errors import raise_for_composio_result
from agent.tools.idempotency_store import IdempotencyStore

CREATE_DRAFT_SLUG = "GMAIL_CREATE_EMAIL_DRAFT"
GET_DRAFT_SLUG = "GMAIL_GET_DRAFT"
_DEFAULT_STORE_PATH = ".secrets/live_gmail_idempotency.json"


def _normalize_draft(raw: dict, fallback_to: list, fallback_subject: str, fallback_body: str) -> dict:
    draft = raw.get("draft") if isinstance(raw.get("draft"), dict) else raw
    message = draft.get("message") if isinstance(draft.get("message"), dict) else {}
    return {
        "id": draft.get("id") or raw.get("id"),
        "to": draft.get("to") or message.get("to") or fallback_to,
        "subject": draft.get("subject") or message.get("subject") or fallback_subject,
        "body": draft.get("body") or message.get("body") or fallback_body,
    }


class LiveGmailDrafts:
    def __init__(self, store_path: str | Path = _DEFAULT_STORE_PATH, user_id: Optional[str] = None):
        self._store = IdempotencyStore(store_path)
        self._user_id = user_id or get_user_id()

    def create_email_draft(self, idempotency_key: str, to: list, subject: str, body: str) -> dict:
        existing_id = self._store.get(idempotency_key)
        if existing_id is not None:
            return self.get_draft(existing_id)

        to = list(to or [])
        primary, cc = (to[0], to[1:]) if to else (None, [])

        client = get_client()
        result = client.tools.execute(
            slug=CREATE_DRAFT_SLUG,
            arguments={"recipient_email": primary, "subject": subject, "body": body, "cc": cc},
            user_id=self._user_id,
        )
        data = raise_for_composio_result(CREATE_DRAFT_SLUG, result)
        draft_id = data.get("id") or (data.get("draft") or {}).get("id")
        if not draft_id:
            raise RuntimeError(f"{CREATE_DRAFT_SLUG} succeeded but returned no draft id: {data!r}")
        self._store.set(idempotency_key, draft_id)
        return {"id": draft_id, "to": to, "subject": subject, "body": body}

    def get_draft(self, draft_id: str) -> dict:
        client = get_client()
        result = client.tools.execute(slug=GET_DRAFT_SLUG, arguments={"draft_id": draft_id}, user_id=self._user_id)
        data = raise_for_composio_result(GET_DRAFT_SLUG, result)
        return _normalize_draft(data, fallback_to=[], fallback_subject="", fallback_body="")
