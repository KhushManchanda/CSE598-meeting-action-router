"""
tools.py
--------
Stub "external system" tools that the agent can invoke.

In a production system these would call a real Calendar API, an Email API,
and a Task Tracker API (e.g. Google Calendar, Gmail, Asana, Jira). For this
baseline they are simulated locally so the whole pipeline is runnable by
anyone with zero credentials, zero cost, and zero network access. Each
function still has the shape of a real tool call: it takes structured
arguments and returns a structured confirmation, so swapping in a real
API later only means changing the function body, not the agent logic.
"""

from datetime import datetime


def schedule_event(owner: str, description: str) -> dict:
    """Simulates creating a calendar event for a follow-up meeting/call."""
    return {
        "tool": "schedule_event",
        "status": "success",
        "confirmation": (
            f"[CalendarAPI] Draft event created for {owner}: "
            f"'{description}'. Awaiting owner to confirm a time slot."
        ),
    }


def send_email(owner: str, description: str) -> dict:
    """Simulates drafting a follow-up email."""
    return {
        "tool": "send_email",
        "status": "success",
        "confirmation": (
            f"[EmailAPI] Draft email queued to {owner} re: '{description}'. "
            f"Saved to Drafts folder, not yet sent."
        ),
    }


def create_task(owner: str, description: str) -> dict:
    """Simulates creating a task-tracker ticket."""
    return {
        "tool": "create_task",
        "status": "success",
        "confirmation": (
            f"[TaskTrackerAPI] Task created and assigned to {owner}: "
            f"'{description}'. Ticket opened {datetime.now().date()}."
        ),
    }


# Registry the agent uses to look up a tool by name.
TOOL_REGISTRY = {
    "schedule_event": schedule_event,
    "send_email": send_email,
    "create_task": create_task,
}
