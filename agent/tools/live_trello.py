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

from pathlib import Path
from typing import Optional

from agent.tools.composio_client import get_client, get_user_id
from agent.tools.composio_errors import raise_for_composio_result
from agent.tools.idempotency_store import IdempotencyStore

CREATE_CARD_SLUG = "TRELLO_ADD_CARDS"
GET_CARD_SLUG = "TRELLO_GET_CARDS_BY_ID_CARD"
_DEFAULT_STORE_PATH = ".secrets/live_trello_idempotency.json"


def _normalize_card(raw: dict, fallback_assignee: Optional[str], fallback_list_id: str, fallback_desc: str) -> dict:
    card = raw.get("card") if isinstance(raw.get("card"), dict) else raw
    id_members = card.get("idMembers") or []
    assignee = id_members[0] if id_members else fallback_assignee
    return {
        "id": card.get("id") or raw.get("id"),
        "title": card.get("name", ""),
        "assignee_member_id": assignee,
        "due": card.get("due"),
        "list_id": card.get("idList", fallback_list_id),
        "description": card.get("desc", fallback_desc),
    }


class LiveTrello:
    def __init__(self, store_path: str | Path = _DEFAULT_STORE_PATH, user_id: Optional[str] = None):
        self._store = IdempotencyStore(store_path)
        self._user_id = user_id or get_user_id()

    def create_task(
        self, idempotency_key: str, title: str, assignee_member_id: Optional[str], due: Optional[str],
        list_id: str, description: str,
    ) -> dict:
        existing_id = self._store.get(idempotency_key)
        if existing_id is not None:
            return self.get_card(existing_id)

        client = get_client()
        result = client.tools.execute(
            slug=CREATE_CARD_SLUG,
            arguments={
                "idList": list_id,
                "name": title,
                "desc": description,
                "due": due,
                "idMembers": [assignee_member_id] if assignee_member_id else [],
            },
            user_id=self._user_id,
        )
        data = raise_for_composio_result(CREATE_CARD_SLUG, result)
        card_id = data.get("id") or (data.get("card") or {}).get("id")
        if not card_id:
            raise RuntimeError(f"{CREATE_CARD_SLUG} succeeded but returned no card id: {data!r}")
        self._store.set(idempotency_key, card_id)
        return {"id": card_id, "title": title, "assignee_member_id": assignee_member_id, "due": due, "list_id": list_id, "description": description}

    def get_card(self, card_id: str) -> dict:
        client = get_client()
        result = client.tools.execute(slug=GET_CARD_SLUG, arguments={"idCard": card_id}, user_id=self._user_id)
        data = raise_for_composio_result(GET_CARD_SLUG, result)
        return _normalize_card(data, fallback_assignee=None, fallback_list_id="", fallback_desc="")
