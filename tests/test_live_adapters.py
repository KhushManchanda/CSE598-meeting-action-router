"""
Tests for agent/tools/live_{calendar,gmail,trello}.py, with
composio.Composio entirely replaced by a fake -- no real network
calls, no API key needed.
"""

import pytest

from agent.tools.errors import InvalidArgumentError
from agent.tools.live_calendar import LiveCalendar
from agent.tools.live_gmail import LiveGmailDrafts
from agent.tools.live_trello import LiveTrello


class _FakeToolsResource:
    """Scripted stand-in for Composio's `composio.tools`. `responses`
    is {slug: callable(arguments) -> ToolExecutionResponse dict} so
    each test controls exactly what each action slug returns."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def execute(self, slug, arguments, user_id=None, **kwargs):
        self.calls.append((slug, arguments, user_id))
        return self.responses[slug](arguments)


class _FakeComposioClient:
    def __init__(self, tools_resource):
        self.tools = tools_resource


def _ok(data):
    return lambda args: {"successful": True, "data": data, "error": None}


def _fail(error):
    return lambda args: {"successful": False, "data": {}, "error": error}


@pytest.fixture
def patch_calendar_client(monkeypatch):
    def _patch(fake_client):
        monkeypatch.setattr("agent.tools.live_calendar.get_client", lambda: fake_client)
        monkeypatch.setattr("agent.tools.live_calendar.get_user_id", lambda: "test-user")
    return _patch


@pytest.fixture
def patch_gmail_client(monkeypatch):
    def _patch(fake_client):
        monkeypatch.setattr("agent.tools.live_gmail.get_client", lambda: fake_client)
        monkeypatch.setattr("agent.tools.live_gmail.get_user_id", lambda: "test-user")
    return _patch


@pytest.fixture
def patch_trello_client(monkeypatch):
    def _patch(fake_client):
        monkeypatch.setattr("agent.tools.live_trello.get_client", lambda: fake_client)
        monkeypatch.setattr("agent.tools.live_trello.get_user_id", lambda: "test-user")
    return _patch


# --- LiveCalendar -----------------------------------------------------

def test_create_calendar_event_success(tmp_path, patch_calendar_client):
    fake = _FakeComposioClient(_FakeToolsResource({"GOOGLECALENDAR_CREATE_EVENT": _ok({"id": "evt_1"})}))
    patch_calendar_client(fake)
    cal = LiveCalendar(store_path=tmp_path / "idem.json")

    record = cal.create_calendar_event("idem-1", "Demo", "2026-09-09T10:00:00", "2026-09-09T10:30:00", ["a@x.com"], "desc")

    assert record["id"] == "evt_1"
    assert record["title"] == "Demo"
    slug, args, user_id = fake.tools.calls[0]
    assert slug == "GOOGLECALENDAR_CREATE_EVENT"
    assert args["summary"] == "Demo"
    assert user_id == "test-user"


def test_create_calendar_event_idempotent_replay_calls_get_not_create(tmp_path, patch_calendar_client):
    responses = {
        "GOOGLECALENDAR_CREATE_EVENT": _ok({"id": "evt_1"}),
        "GOOGLECALENDAR_EVENTS_GET": _ok({"event": {"id": "evt_1", "summary": "Demo", "start": {"dateTime": "2026-09-09T10:00:00"}, "end": {"dateTime": "2026-09-09T10:30:00"}, "attendees": [], "description": "desc"}}),
    }
    fake = _FakeComposioClient(_FakeToolsResource(responses))
    patch_calendar_client(fake)
    cal = LiveCalendar(store_path=tmp_path / "idem.json")

    first = cal.create_calendar_event("idem-1", "Demo", "2026-09-09T10:00:00", "2026-09-09T10:30:00", [], "desc")
    second = cal.create_calendar_event("idem-1", "Demo", "2026-09-09T10:00:00", "2026-09-09T10:30:00", [], "desc")

    assert first["id"] == second["id"] == "evt_1"
    create_calls = [c for c in fake.tools.calls if c[0] == "GOOGLECALENDAR_CREATE_EVENT"]
    get_calls = [c for c in fake.tools.calls if c[0] == "GOOGLECALENDAR_EVENTS_GET"]
    assert len(create_calls) == 1  # never created twice
    assert len(get_calls) == 1  # replay read back instead


def test_create_calendar_event_failure_raises_typed_error(tmp_path, patch_calendar_client):
    fake = _FakeComposioClient(_FakeToolsResource({"GOOGLECALENDAR_CREATE_EVENT": _fail("400 invalid request")}))
    patch_calendar_client(fake)
    cal = LiveCalendar(store_path=tmp_path / "idem.json")

    with pytest.raises(InvalidArgumentError):
        cal.create_calendar_event("idem-1", "Demo", "2026-09-09T10:00:00", "2026-09-09T10:30:00", [], "desc")


def test_get_event_normalizes_nested_response(tmp_path, patch_calendar_client):
    fake = _FakeComposioClient(_FakeToolsResource({
        "GOOGLECALENDAR_EVENTS_GET": _ok({"event": {"id": "evt_9", "summary": "Standup", "start": {"dateTime": "2026-09-09T09:00:00"}, "end": {"dateTime": "2026-09-09T09:15:00"}, "attendees": [{"email": "a@x.com"}], "description": "d"}}),
    }))
    patch_calendar_client(fake)
    cal = LiveCalendar(store_path=tmp_path / "idem.json")

    record = cal.get_event("evt_9")
    assert record == {"id": "evt_9", "title": "Standup", "start": "2026-09-09T09:00:00", "end": "2026-09-09T09:15:00", "attendees": ["a@x.com"], "description": "d"}


# --- LiveGmailDrafts ----------------------------------------------------

def test_create_email_draft_maps_first_recipient_and_rest_to_cc(tmp_path, patch_gmail_client):
    fake = _FakeComposioClient(_FakeToolsResource({"GMAIL_CREATE_EMAIL_DRAFT": _ok({"id": "draft_1"})}))
    patch_gmail_client(fake)
    gmail = LiveGmailDrafts(store_path=tmp_path / "idem.json")

    record = gmail.create_email_draft("idem-1", ["a@x.com", "b@x.com"], "Subject", "Body")

    assert record["id"] == "draft_1"
    _, args, _ = fake.tools.calls[0]
    assert args["recipient_email"] == "a@x.com"
    assert args["cc"] == ["b@x.com"]


def test_create_email_draft_idempotent_replay(tmp_path, patch_gmail_client):
    responses = {
        "GMAIL_CREATE_EMAIL_DRAFT": _ok({"id": "draft_1"}),
        "GMAIL_GET_DRAFT": _ok({"draft": {"id": "draft_1", "to": ["a@x.com"], "subject": "Subject", "body": "Body"}}),
    }
    fake = _FakeComposioClient(_FakeToolsResource(responses))
    patch_gmail_client(fake)
    gmail = LiveGmailDrafts(store_path=tmp_path / "idem.json")

    gmail.create_email_draft("idem-1", ["a@x.com"], "Subject", "Body")
    second = gmail.create_email_draft("idem-1", ["a@x.com"], "Subject", "Body")

    assert second["id"] == "draft_1"
    assert len([c for c in fake.tools.calls if c[0] == "GMAIL_CREATE_EMAIL_DRAFT"]) == 1


# --- LiveTrello ----------------------------------------------------------

def test_create_task_maps_assignee_to_idmembers_list(tmp_path, patch_trello_client):
    fake = _FakeComposioClient(_FakeToolsResource({"TRELLO_ADD_CARDS": _ok({"id": "card_1"})}))
    patch_trello_client(fake)
    trello = LiveTrello(store_path=tmp_path / "idem.json")

    record = trello.create_task("idem-1", "Draft notes", "member_marcus", "2026-09-04", "list_todo", "desc")

    assert record["id"] == "card_1"
    _, args, _ = fake.tools.calls[0]
    assert args["idList"] == "list_todo"
    assert args["idMembers"] == ["member_marcus"]
    assert args["name"] == "Draft notes"


def test_create_task_with_no_assignee_sends_empty_idmembers(tmp_path, patch_trello_client):
    fake = _FakeComposioClient(_FakeToolsResource({"TRELLO_ADD_CARDS": _ok({"id": "card_1"})}))
    patch_trello_client(fake)
    trello = LiveTrello(store_path=tmp_path / "idem.json")

    trello.create_task("idem-1", "Draft notes", None, None, "list_todo", "desc")
    _, args, _ = fake.tools.calls[0]
    assert args["idMembers"] == []


def test_get_card_normalizes_response(tmp_path, patch_trello_client):
    fake = _FakeComposioClient(_FakeToolsResource({
        "TRELLO_GET_CARDS_BY_ID_CARD": _ok({"card": {"id": "card_1", "name": "Draft notes", "desc": "d", "due": "2026-09-04", "idList": "list_todo", "idMembers": ["member_marcus"]}}),
    }))
    patch_trello_client(fake)
    trello = LiveTrello(store_path=tmp_path / "idem.json")

    record = trello.get_card("card_1")
    assert record == {"id": "card_1", "title": "Draft notes", "assignee_member_id": "member_marcus", "due": "2026-09-04", "list_id": "list_todo", "description": "d"}


def test_create_task_idempotent_replay_does_not_create_twice(tmp_path, patch_trello_client):
    responses = {
        "TRELLO_ADD_CARDS": _ok({"id": "card_1"}),
        "TRELLO_GET_CARDS_BY_ID_CARD": _ok({"card": {"id": "card_1", "name": "x", "desc": "", "due": None, "idList": "list_todo", "idMembers": []}}),
    }
    fake = _FakeComposioClient(_FakeToolsResource(responses))
    patch_trello_client(fake)
    trello = LiveTrello(store_path=tmp_path / "idem.json")

    trello.create_task("idem-1", "x", None, None, "list_todo", "")
    trello.create_task("idem-1", "x", None, None, "list_todo", "")

    assert len([c for c in fake.tools.calls if c[0] == "TRELLO_ADD_CARDS"]) == 1
