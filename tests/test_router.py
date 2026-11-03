from agent.participants import Roster
from agent.resolver import ResolvedAction
from agent.router import build_tool_args, call_tool, idempotency_key
from agent.schema import ActionItem
from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello

ROSTER = Roster(
    [
        {"name": "Marcus", "aliases": [], "email": "marcus@example.com", "trello_member_id": "member_marcus"},
        {"name": "Priya", "aliases": [], "email": "priya@example.com", "trello_member_id": "member_priya"},
    ]
)


def _resolved_action(**kwargs):
    defaults = dict(
        owner="Marcus", tool="calendar_event", task_text="Demo", description="demo description",
        due="2026-09-04", attendees_or_recipients=[], confidence_notes="", unresolved=False,
    )
    defaults.update(kwargs)
    return ResolvedAction(**defaults)


def _item(**kwargs):
    defaults = dict(
        id="t1-1", transcript_id="t1", task="Demo with design team", owner="Marcus",
        tool="calendar_event", due="2026-09-04", attendees_or_recipients=[], evidence_utterance_ids=["u3"],
    )
    defaults.update(kwargs)
    return ActionItem(**defaults)


def test_idempotency_key_is_deterministic_hash():
    k1 = idempotency_key("t1", "t1-1")
    k2 = idempotency_key("t1", "t1-1")
    k3 = idempotency_key("t1", "t1-2")
    assert k1 == k2
    assert k1 != k3


def test_calendar_args_default_time_and_includes_owner_as_attendee():
    args = build_tool_args(_item(), _resolved_action(), ROSTER)
    assert args["start"] == "2026-09-04T10:00:00"
    assert args["end"] == "2026-09-04T10:30:00"
    assert "marcus@example.com" in args["attendees"]
    assert args["title"] == "Demo with design team"
    assert args["description"] == "demo description"


def test_calendar_args_does_not_duplicate_owner_already_in_attendees():
    item = _item(attendees_or_recipients=["marcus@example.com", "priya@example.com"])
    args = build_tool_args(item, _resolved_action(), ROSTER)
    assert args["attendees"].count("marcus@example.com") == 1


def test_trello_task_args_resolve_assignee_member_id():
    item = _item(tool="trello_task", owner="Marcus", due="2026-09-04")
    args = build_tool_args(item, _resolved_action(tool="trello_task"), ROSTER)
    assert args["assignee_member_id"] == "member_marcus"
    assert args["list_id"] == "list_todo"
    assert args["due"] == "2026-09-04"


def test_email_draft_args():
    item = _item(tool="email_draft", owner="Priya", due=None, attendees_or_recipients=["legal@example.com"],
                 task="Vendor contract follow-up")
    args = build_tool_args(item, _resolved_action(tool="email_draft", description="body text"), ROSTER)
    assert args["to"] == ["legal@example.com"]
    assert args["subject"] == "Vendor contract follow-up"
    assert args["body"] == "body text"


def test_call_tool_dispatches_to_correct_backend():
    tools = {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}
    args = build_tool_args(_item(), _resolved_action(), ROSTER)
    record = call_tool("calendar_event", args, tools, "idem-1")
    assert record["id"].startswith("evt_")
    assert len(tools["calendar"].all_objects()) == 1
    assert len(tools["trello"].all_objects()) == 0
    assert len(tools["gmail"].all_objects()) == 0
