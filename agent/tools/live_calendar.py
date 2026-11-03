"""
agent/tools/live_calendar.py
-------------------------------
Live Google Calendar adapter (step 7), via Composio's managed
connection (see agent/tools/composio_client.py for why -- replaces a
from-scratch OAuth implementation at the user's request). Same method
names/signatures as agent/tools/mock_backend.py:MockCalendar
(create_calendar_event, get_event), so agent/router.py and
agent/verifier.py work against this unchanged.

Idempotency: neither Composio nor the Google Calendar API accepts a
client idempotency key, so this adapter implements the same guarantee
the mock backend gives for free -- agent/tools/idempotency_store.py,
keyed by idempotency_key -> event_id, checked before every create. On
an idempotent replay, it reads the real event back rather than just
echoing the call's own arguments, so the result reflects the account's
actual current state.

Action-slug/parameter mapping to Composio's GOOGLECALENDAR_CREATE_EVENT
/ GOOGLECALENDAR_EVENTS_GET is based on Composio's docs as of
2026-11-03 -- NOT verified against a live API key while writing this
(none was available). Before the first real run:
    python scripts/verify_composio_tools.py
which calls composio.tools.get_raw_composio_tool_by_slug(...) for both
slugs and diffs the actual parameter schema against what this file
assumes.

No timezone modeling: consistent with agent/router.py's own disclosed
simplification (no transcript in this project's data states an exact
time), start/end are passed as naive ISO datetimes with no timezone,
letting the connected Google Calendar's own default apply.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agent.tools.composio_client import get_client, get_user_id
from agent.tools.composio_errors import raise_for_composio_result
from agent.tools.idempotency_store import IdempotencyStore

CREATE_EVENT_SLUG = "GOOGLECALENDAR_CREATE_EVENT"
GET_EVENT_SLUG = "GOOGLECALENDAR_EVENTS_GET"
_DEFAULT_STORE_PATH = ".secrets/live_calendar_idempotency.json"


def _normalize_event(raw: dict, fallback_title: str, fallback_description: str) -> dict:
    """Best-effort translation of Composio's GOOGLECALENDAR_EVENTS_GET
    response into our flat {id,title,start,end,attendees,description}
    shape (see module docstring: unverified against a real response)."""
    event = raw.get("event") if isinstance(raw.get("event"), dict) else raw
    start = event.get("start")
    end = event.get("end")
    start_str = start.get("dateTime", start) if isinstance(start, dict) else start
    end_str = end.get("dateTime", end) if isinstance(end, dict) else end
    attendees_raw = event.get("attendees") or []
    attendees = [a.get("email", a) if isinstance(a, dict) else a for a in attendees_raw]
    return {
        "id": event.get("id") or raw.get("id"),
        "title": event.get("summary", fallback_title),
        "start": start_str,
        "end": end_str,
        "attendees": attendees,
        "description": event.get("description", fallback_description),
    }


class LiveCalendar:
    def __init__(self, store_path: str | Path = _DEFAULT_STORE_PATH, user_id: Optional[str] = None):
        self._store = IdempotencyStore(store_path)
        self._user_id = user_id or get_user_id()

    def create_calendar_event(self, idempotency_key: str, title: str, start: str, end: str, attendees: list, description: str) -> dict:
        existing_id = self._store.get(idempotency_key)
        if existing_id is not None:
            return self.get_event(existing_id)

        client = get_client()
        result = client.tools.execute(
            slug=CREATE_EVENT_SLUG,
            arguments={
                "summary": title,
                "start_datetime": start,
                "end_datetime": end,
                "attendees": list(attendees or []),
                "description": description,
            },
            user_id=self._user_id,
        )
        data = raise_for_composio_result(CREATE_EVENT_SLUG, result)
        event_id = data.get("id") or (data.get("event") or {}).get("id")
        if not event_id:
            raise RuntimeError(f"{CREATE_EVENT_SLUG} succeeded but returned no event id: {data!r}")
        self._store.set(idempotency_key, event_id)
        return {"id": event_id, "title": title, "start": start, "end": end, "attendees": list(attendees or []), "description": description}

    def get_event(self, event_id: str) -> dict:
        client = get_client()
        result = client.tools.execute(slug=GET_EVENT_SLUG, arguments={"event_id": event_id}, user_id=self._user_id)
        data = raise_for_composio_result(GET_EVENT_SLUG, result)
        return _normalize_event(data, fallback_title="", fallback_description="")
