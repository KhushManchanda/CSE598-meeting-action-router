"""Read-only verification of the existing Calendar demo event.

Run with permission to use this checkout's .env. No event creation/update,
no ledger edits, and no model calls. Original run reports remain unchanged.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.tools.live_calendar import (  # noqa: E402
    GOOGLECALENDAR_TOOLKIT_VERSION, GET_EVENT_SLUG, _normalize_event,
)


def verify_existing(client, user_id, event_id, email):
    response = client.tools.execute(
        slug=GET_EVENT_SLUG,
        arguments={"event_id": event_id, "calendar_id": "primary", "time_zone": "America/Phoenix"},
        user_id=user_id, version=GOOGLECALENDAR_TOOLKIT_VERSION,
    )
    if not response.get("successful"):
        raise RuntimeError("Event read failed")
    event = _normalize_event(response.get("data") or {}, "", "")
    expected = {"id": event_id, "title": "Schedule a capstone demo rehearsal",
                "start": "2026-11-08T10:00:00", "end": "2026-11-08T10:30:00",
                "attendees": [email]}
    mismatches = {}
    for field, value in expected.items():
        actual = event.get(field)
        matches = sorted(actual or []) == sorted(value) if field == "attendees" else actual == value
        if not matches:
            mismatches[field] = {"expected": value, "actual": actual}
    return {"event_id": event_id, "timezone": "America/Phoenix",
            "fields_checked": list(expected), "actual": event,
            "mismatches": mismatches, "verified": not mismatches,
            "note": "Read-only check of existing event; description is shown for review, not independently scored."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-id", required=True)
    args = parser.parse_args()
    from dotenv import dotenv_values
    from composio import Composio

    config = dotenv_values(ROOT / ".env", interpolate=False)
    if not config.get("COMPOSIO_API_KEY"):
        raise SystemExit("COMPOSIO_API_KEY must be configured locally")
    roster = json.loads((ROOT / "data/demo/arjun_google/roster.json").read_text())
    try:
        result = verify_existing(Composio(api_key=config["COMPOSIO_API_KEY"]),
            config.get("COMPOSIO_USER_ID") or "meeting-action-router", args.event_id, roster[0]["email"])
    except Exception as exc:
        raise SystemExit(f"Read-only verification failed ({type(exc).__name__}); no event was created or changed") from None
    path = ROOT / "runs/calendar_existing_event_verification.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"Verification evidence: {path}")
    if not result["verified"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
