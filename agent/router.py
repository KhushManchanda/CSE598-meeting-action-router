"""
agent/router.py
------------------
Router: maps a validated, human-approved ActionItem onto the real tool
call (create_calendar_event / create_task / create_email_draft), tagged
with idempotency_key = hash(meeting_id, action_id) per spec. Works
against either the mock backend (agent/tools/mock_backend.py) or a live
step-7 adapter -- both expose the same method names/signatures
(tools["calendar"].create_calendar_event(...), etc.), so this module
never needs to know which one it's talking to.

This module does the mapping and ONE call -- no retry, no read-back.
agent/verifier.py is what adds retry/escalation/read-back around it, so
each module has one job.

Calendar default-time convention (disclosed, not hidden): no transcript
in this project's data states an exact meeting TIME, only a day. The
validator (agent/validator.py) already guarantees a calendar_event has
a resolved `due` day before it ever reaches here; this router applies a
fixed default slot (DEFAULT_EVENT_START_TIME, 30 minutes) rather than
guessing a time from nothing.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from agent.participants import Roster
from agent.tool_schemas import DEFAULT_TRELLO_LIST_ID

DEFAULT_EVENT_START_TIME = "10:00"
DEFAULT_EVENT_DURATION_MINUTES = 30


def idempotency_key(meeting_id: str, action_id: str) -> str:
    return hashlib.sha256(f"{meeting_id}:{action_id}".encode()).hexdigest()[:16]


def _calendar_start_end(due_date: str) -> tuple[str, str]:
    start = datetime.fromisoformat(f"{due_date}T{DEFAULT_EVENT_START_TIME}:00")
    end = start + timedelta(minutes=DEFAULT_EVENT_DURATION_MINUTES)
    return start.isoformat(), end.isoformat()


def _owner_field(owner_name: Optional[str], roster: Roster, field: str) -> Optional[str]:
    match = roster.lookup(owner_name) if owner_name else None
    return match[field] if match else None


def build_tool_args(resolved_item, resolved_action, roster: Roster, trello_list_id: Optional[str] = None) -> dict:
    """resolved_item: the validator-produced ActionItem (owner/tool/due/
    attendees already roster-checked). resolved_action: the resolver's
    ResolvedAction (only used here for its longer `description`).
    Returns the exact kwargs (no idempotency_key, no bookkeeping fields)
    for the matching tools[...].create_* call."""
    tool = resolved_item.tool
    if tool == "calendar_event":
        start, end = _calendar_start_end(resolved_item.due)
        attendees = list(resolved_item.attendees_or_recipients)
        owner_email = _owner_field(resolved_item.owner, roster, "email")
        if owner_email and owner_email not in attendees:
            attendees.append(owner_email)
        return {
            "title": resolved_item.task,
            "start": start,
            "end": end,
            "attendees": attendees,
            "description": resolved_action.description,
        }
    if tool == "trello_task":
        return {
            "title": resolved_item.task,
            "assignee_member_id": _owner_field(resolved_item.owner, roster, "trello_member_id"),
            "due": resolved_item.due,
            "list_id": trello_list_id or DEFAULT_TRELLO_LIST_ID,
            "description": resolved_action.description,
        }
    if tool == "email_draft":
        return {
            "to": list(resolved_item.attendees_or_recipients),
            "subject": resolved_item.task,
            "body": resolved_action.description,
        }
    raise ValueError(f"Unknown canonical tool: {tool!r}")


def call_tool(tool: str, args: dict, tools: dict, idem_key: str) -> dict:
    """Dispatches ONE already-built args dict to the matching backend
    method. Raises whatever the backend raises -- callers (agent/
    verifier.py) decide retry vs escalate based on the exception type."""
    if tool == "calendar_event":
        return tools["calendar"].create_calendar_event(idem_key, **args)
    if tool == "trello_task":
        return tools["trello"].create_task(idem_key, **args)
    if tool == "email_draft":
        return tools["gmail"].create_email_draft(idem_key, **args)
    raise ValueError(f"Unknown canonical tool: {tool!r}")
