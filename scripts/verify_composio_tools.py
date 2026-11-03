#!/usr/bin/env python3
"""
scripts/verify_composio_tools.py
------------------------------------
agent/tools/live_{calendar,gmail,trello}.py's argument-name mapping to
Composio's action slugs was written from Composio's docs, NOT verified
against a live API key (none was available while writing it). Run
this once a real COMPOSIO_API_KEY is set, BEFORE the first live run,
to catch any parameter-name drift before it causes a confusing
silent failure in a real meeting.

Fetches the actual tool schema for every action slug our live adapters
use (composio.tools.get_raw_composio_tool_by_slug) and checks that
every parameter name our code sends actually exists in that schema.
Prints a clear PASS/FAIL per slug; does not call execute() -- no real
side effects, no connected account required.

Usage:
    python scripts/verify_composio_tools.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from agent.tools.composio_client import get_client  # noqa: E402

# slug -> the argument names our adapter code actually sends
EXPECTED_ARGS = {
    "GOOGLECALENDAR_CREATE_EVENT": {"summary", "start_datetime", "end_datetime", "attendees", "description"},
    "GOOGLECALENDAR_EVENTS_GET": {"event_id"},
    "GMAIL_CREATE_EMAIL_DRAFT": {"recipient_email", "subject", "body", "cc"},
    "GMAIL_GET_DRAFT": {"draft_id"},
    "TRELLO_ADD_CARDS": {"idList", "name", "desc", "due", "idMembers"},
    "TRELLO_GET_CARDS_BY_ID_CARD": {"idCard"},
}


def _schema_param_names(tool) -> set[str]:
    # Tool.input_parameters is a JSON-schema-shaped dict; be defensive
    # about exactly where "properties" lives since this is the first
    # real look at the schema's actual shape.
    schema = getattr(tool, "input_parameters", None) or getattr(tool, "parameters", None) or {}
    if isinstance(schema, dict):
        return set(schema.get("properties", {}).keys())
    return set()


def main() -> None:
    client = get_client()
    failures = []

    for slug, expected in EXPECTED_ARGS.items():
        try:
            tool = client.tools.get_raw_composio_tool_by_slug(slug)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {slug}: could not fetch tool schema ({type(exc).__name__}: {exc})")
            failures.append(slug)
            continue

        actual = _schema_param_names(tool)
        unknown = expected - actual
        if unknown:
            print(f"[FAIL] {slug}: our code sends {sorted(unknown)}, not in the real schema {sorted(actual)}")
            failures.append(slug)
        else:
            print(f"[PASS] {slug}: all expected args {sorted(expected)} exist in the real schema")

    if failures:
        print(f"\n{len(failures)} slug(s) need fixing before a live run: {failures}")
        sys.exit(1)
    print("\nAll slugs verified.")


if __name__ == "__main__":
    main()
