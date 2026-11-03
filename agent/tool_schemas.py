"""
agent/tool_schemas.py
------------------------
OpenAI tool-calling (function-calling) schemas for the three router
tools, shared by B1 (baselines/b1_single_call.py, step 3) and, later,
Agent A's resolver/router (step 4) — "same tool schemas" per the spec's
B1 definition.

Each schema's REQUIRED, API-shaped arguments mirror the spec's router
signatures exactly:
  create_calendar_event(title, start, end, attendees, description)
  create_task(title, assignee_member_id, due, list_id, description)
  create_email_draft(to, subject, body)

Deliberate, disclosed addition: every schema also carries two
bookkeeping-only arguments, `owner` and `evidence_utterance_ids`. None
of the three real router signatures above has a way to express "whose
action item is this" or "which transcript lines support it" — Agent A
tracks that in its SQLite ledger, separate from the tool-call payload,
but B1 has no ledger. Without asking the model to state them directly,
B1's predictions would be structurally unscorable on owner accuracy for
2 of 3 tool types, and ungroundable for evidence-based matching. Callers
MUST strip these two keys before forwarding arguments to the real
Calendar/Trello/Gmail call — they are not part of any real API request.
"""

from __future__ import annotations

DEFAULT_TRELLO_LIST_ID = "list_todo"

_BOOKKEEPING_PROPERTIES = {
    "owner": {
        "type": "string",
        "description": "Name (as it appears in the roster) of the person who will actually DO this action item.",
    },
    "evidence_utterance_ids": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Utterance id(s) (e.g. 'u3') from the transcript that support this action item.",
    },
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a calendar event for a scheduled meeting, call, or demo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start": {"type": "string", "description": "ISO 8601 datetime"},
                    "end": {"type": "string", "description": "ISO 8601 datetime"},
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Attendee email addresses, from the roster.",
                    },
                    "description": {"type": "string"},
                    **_BOOKKEEPING_PROPERTIES,
                },
                "required": ["title", "start", "end", "attendees", "description", "owner", "evidence_utterance_ids"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a Trello task/card assigned to the person who owns it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "assignee_member_id": {
                        "type": "string",
                        "description": "Trello member id of the task owner, from the roster.",
                    },
                    "due": {
                        "type": ["string", "null"],
                        "description": "ISO-8601 DATE ONLY (YYYY-MM-DD) -- no time, no timezone. "
                        "Null if no confidently-resolvable due date.",
                    },
                    "list_id": {"type": "string", "description": f"Always '{DEFAULT_TRELLO_LIST_ID}'."},
                    "description": {"type": "string"},
                    **_BOOKKEEPING_PROPERTIES,
                },
                "required": [
                    "title",
                    "assignee_member_id",
                    "due",
                    "list_id",
                    "description",
                    "owner",
                    "evidence_utterance_ids",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_email_draft",
            "description": "Create a Gmail draft (never sent) to follow up on an action item by email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient email addresses, from the roster.",
                    },
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    **_BOOKKEEPING_PROPERTIES,
                },
                "required": ["to", "subject", "body", "owner", "evidence_utterance_ids"],
                "additionalProperties": False,
            },
        },
    },
]

# Tool function name -> our canonical schema tool name (agent/schema.py:ALLOWED_TOOLS)
TOOL_NAME_TO_CANONICAL = {
    "create_calendar_event": "calendar_event",
    "create_task": "trello_task",
    "create_email_draft": "email_draft",
}

# Bookkeeping-only argument names every real adapter call must strip.
BOOKKEEPING_ARG_NAMES = ("owner", "evidence_utterance_ids")
