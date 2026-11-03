"""
agent/tools/live_gmail.py
----------------------------
Live Gmail drafts adapter (step 7, stretch goal), via Composio. Same
method names/signatures as agent/tools/mock_backend.py:MockGmailDrafts
(create_email_draft, get_draft). Drafts only -- this never calls a
"send" action, matching the spec's gmail.compose-scope-only limit.

Idempotency: same pattern as agent/tools/live_calendar.py --
agent/tools/idempotency_store.py keyed by idempotency_key -> draft_id.

The pinned live schema supports recipient_email plus extra_recipients
for additional To addresses. Signatures are disabled so read-back can
compare the authored content. Drafts are fetched as raw MIME and decoded;
no send tool is called. Live behavior still requires a smoke test.
"""

from __future__ import annotations

import base64
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

from agent.tools.composio_client import get_client, get_user_id
from agent.tools.composio_errors import raise_for_composio_result
from agent.tools.idempotency_store import IdempotencyStore

CREATE_DRAFT_SLUG = "GMAIL_CREATE_EMAIL_DRAFT"
GET_DRAFT_SLUG = "GMAIL_GET_DRAFT"
GMAIL_TOOLKIT_VERSION = "20261029_00"
_DEFAULT_STORE_PATH = ".secrets/live_gmail_idempotency.json"


class _HtmlText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "br":
            self.parts.append("\n")


def _draft_payload(raw: dict) -> dict:
    payload = raw.get("response_data") if isinstance(raw.get("response_data"), dict) else raw
    return payload.get("draft") if isinstance(payload.get("draft"), dict) else payload


def _normalize_draft(raw: dict, fallback_to: list, fallback_subject: str, fallback_body: str) -> dict:
    draft = _draft_payload(raw)
    message = draft.get("message") if isinstance(draft.get("message"), dict) else {}
    encoded = message.get("raw") or draft.get("raw")
    if encoded:
        mime = BytesParser(policy=policy.default).parsebytes(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        part = mime.get_body(preferencelist=("plain", "html"))
        body = part.get_content() if part else ""
        if part and part.get_content_type() == "text/html":
            parser = _HtmlText()
            parser.feed(body)
            body = "".join(parser.parts)
        return {
            "id": draft.get("id") or raw.get("id"),
            "to": [address for _, address in getaddresses(
                [str(header) for header in mime.get_all("To", [])])],
            "subject": str(mime.get("Subject", "")),
            "body": body.replace("\r\n", "\n").rstrip("\n"),
        }
    return {
        "id": draft.get("id") or raw.get("id"),
        "to": draft.get("to") or message.get("to") or fallback_to,
        "subject": draft.get("subject") or message.get("subject") or fallback_subject,
        "body": draft.get("body") or message.get("body") or fallback_body,
    }


class LiveGmailDrafts:
    def __init__(self, store_path: str | Path = _DEFAULT_STORE_PATH, user_id: Optional[str] = None, client=None):
        self._store = IdempotencyStore(store_path)
        self._user_id = user_id or get_user_id()
        self._client = client

    def create_email_draft(self, idempotency_key: str, to: list, subject: str, body: str) -> dict:
        existing_id = self._store.get(idempotency_key)
        if existing_id is not None:
            return self.get_draft(existing_id)

        to = list(to or [])
        primary, extra_recipients = (to[0], to[1:]) if to else (None, [])

        client = self._client if self._client is not None else get_client()
        result = client.tools.execute(
            slug=CREATE_DRAFT_SLUG,
            arguments={"recipient_email": primary, "subject": subject,
                       "body": escape(body).replace("\n", "<br/>"), "is_html": True,
                       "extra_recipients": extra_recipients, "cc": [], "bcc": [],
                       "include_signature": False, "user_id": "me"},
            user_id=self._user_id,
            version=GMAIL_TOOLKIT_VERSION,
        )
        data = raise_for_composio_result(CREATE_DRAFT_SLUG, result)
        payload = _draft_payload(data)
        draft_id = payload.get("id") or payload.get("draft_id")
        if not draft_id:
            raise RuntimeError(f"{CREATE_DRAFT_SLUG} succeeded but returned no draft id: {data!r}")
        self._store.set(idempotency_key, draft_id)
        return {"id": draft_id, "to": to, "subject": subject, "body": body}

    def get_draft(self, draft_id: str) -> dict:
        client = self._client if self._client is not None else get_client()
        result = client.tools.execute(
            slug=GET_DRAFT_SLUG, arguments={"draft_id": draft_id, "format": "raw", "user_id": "me"},
            user_id=self._user_id, version=GMAIL_TOOLKIT_VERSION,
        )
        data = raise_for_composio_result(GET_DRAFT_SLUG, result)
        return _normalize_draft(data, fallback_to=[], fallback_subject="", fallback_body="")
