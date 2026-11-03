"""
agent/tools/live_trello.py
------------------------------
Live Trello adapter (step 7), via Composio. Same method names/
signatures as agent/tools/mock_backend.py:MockTrello (create_task,
get_card).

Idempotency: same pattern as agent/tools/live_calendar.py --
agent/tools/idempotency_store.py keyed by idempotency_key -> card_id.

Action-slug/parameter mapping to Composio's TRELLO_ADD_CARDS /
TRELLO_GET_CARDS_BY_ID_CARD is based on Composio's docs as of
2026-11-03 (Trello's own card fields -- name/desc/due/idList/idMembers
-- are long-stable regardless of Composio's exact wrapper, so this is
on firmer ground than the Calendar/Gmail response-shape guesses, but
still unverified against a live key). Before the first real run:
    python scripts/verify_composio_tools.py
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from agent.tools.composio_client import get_client, get_user_id
from agent.tools.composio_errors import raise_for_composio_result
from agent.tools.idempotency_store import IdempotencyStore

CREATE_CARD_SLUG = "TRELLO_ADD_CARDS"
GET_CARD_SLUG = "TRELLO_GET_CARDS_BY_ID_CARD"
# Direct execution requires a dated release; this is the version used
# by the successful live board-list and authenticated-member lookups.
TRELLO_TOOLKIT_VERSION = "20261007_01"
TRELLO_CARD_FIELDS = "name,desc,idList,idMembers,due,url"
# Demo default, explicit rather than inherited from the host or a secret file.
# Other deployments can pass timezone_name to LiveTrello.
DEFAULT_TRELLO_TIMEZONE = "America/Phoenix"
_DEFAULT_STORE_PATH = ".secrets/live_trello_idempotency.json"


def trello_due_timestamp(due: Optional[str], timezone_name: str = DEFAULT_TRELLO_TIMEZONE) -> Optional[str]:
    """Date-only deadlines use a disclosed 17:00 slot in the meeting timezone."""
    if due is None:
        return None
    return datetime.combine(date.fromisoformat(due), time(17), ZoneInfo(timezone_name)).isoformat()


def _normalize_card(raw: dict, fallback_assignee: Optional[str], fallback_list_id: str, fallback_desc: str,
                    timezone_name: str = DEFAULT_TRELLO_TIMEZONE) -> dict:
    card = raw.get("card") if isinstance(raw.get("card"), dict) else raw
    id_members = card.get("idMembers") or []
    assignee = id_members[0] if id_members else fallback_assignee
    due = card.get("due")
    # Compare the deadline's local calendar day, which is what the user sees.
    if isinstance(due, str) and "T" in due:
        try:
            timestamp = datetime.fromisoformat(due.replace("Z", "+00:00"))
            if timestamp.tzinfo is not None:
                due = timestamp.astimezone(ZoneInfo(timezone_name)).date().isoformat()
        except ValueError:
            pass  # malformed provider data must still fail verification
    return {
        "id": card.get("id") or raw.get("id"),
        "title": card.get("name", ""),
        "assignee_member_id": assignee,
        "due": due,
        "list_id": card.get("idList", fallback_list_id),
        "description": card.get("desc", fallback_desc),
    }


class LiveTrello:
    def __init__(self, store_path: str | Path = _DEFAULT_STORE_PATH, user_id: Optional[str] = None,
                 timezone_name: str = DEFAULT_TRELLO_TIMEZONE, client=None, list_id: Optional[str] = None):
        self._store = IdempotencyStore(store_path)
        self._user_id = user_id or get_user_id()
        ZoneInfo(timezone_name)  # fail before any write for an unknown timezone
        self._timezone_name = timezone_name
        self._client = client
        self.list_id = list_id

    def create_task(
        self, idempotency_key: str, title: str, assignee_member_id: Optional[str], due: Optional[str],
        list_id: str, description: str,
    ) -> dict:
        existing_id = self._store.get(idempotency_key)
        if existing_id is not None:
            return self.get_card(existing_id)

        client = self._client if self._client is not None else get_client()
        result = client.tools.execute(
            slug=CREATE_CARD_SLUG,
            arguments={
                "idList": list_id,
                "name": title,
                "desc": description,
                "due": trello_due_timestamp(due, self._timezone_name),
                # This Composio action parses the member IDs as text
                # (comma-separated for multiple IDs), not a JSON array.
                **({"idMembers": assignee_member_id} if assignee_member_id else {}),
            },
            user_id=self._user_id,
            version=TRELLO_TOOLKIT_VERSION,
        )
        data = raise_for_composio_result(CREATE_CARD_SLUG, result)
        card_id = data.get("id") or (data.get("card") or {}).get("id")
        if not card_id:
            raise RuntimeError(f"{CREATE_CARD_SLUG} succeeded but returned no card id: {data!r}")
        self._store.set(idempotency_key, card_id)
        return {"id": card_id, "title": title, "assignee_member_id": assignee_member_id, "due": due, "list_id": list_id, "description": description}

    def get_card(self, card_id: str) -> dict:
        client = self._client if self._client is not None else get_client()
        result = client.tools.execute(
            slug=GET_CARD_SLUG, arguments={"idCard": card_id, "fields": TRELLO_CARD_FIELDS},
            user_id=self._user_id, version=TRELLO_TOOLKIT_VERSION,
        )
        data = raise_for_composio_result(GET_CARD_SLUG, result)
        return _normalize_card(data, fallback_assignee=None, fallback_list_id="", fallback_desc="",
                               timezone_name=self._timezone_name)
