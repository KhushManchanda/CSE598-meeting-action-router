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

def test_create_email_draft_preserves_additional_to_recipients(tmp_path, patch_gmail_client):
    fake = _FakeComposioClient(_FakeToolsResource({"GMAIL_CREATE_EMAIL_DRAFT": _ok({"id": "draft_1"})}))
    patch_gmail_client(fake)
    gmail = LiveGmailDrafts(store_path=tmp_path / "idem.json")

    record = gmail.create_email_draft("idem-1", ["a@x.com", "b@x.com"], "Subject", "Body")

    assert record["id"] == "draft_1"
    _, args, _ = fake.tools.calls[0]
    assert args["recipient_email"] == "a@x.com"
    assert args["extra_recipients"] == ["b@x.com"]
    assert args["cc"] == []
    assert args["include_signature"] is False


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

def test_create_task_serializes_assignee_as_idmembers_string(tmp_path, patch_trello_client):
    fake = _FakeComposioClient(_FakeToolsResource({"TRELLO_ADD_CARDS": _ok({"id": "card_1"})}))
    patch_trello_client(fake)
    trello = LiveTrello(store_path=tmp_path / "idem.json")

    record = trello.create_task("idem-1", "Draft notes", "member_marcus", "2026-09-04", "list_todo", "desc")

    assert record["id"] == "card_1"
    _, args, _ = fake.tools.calls[0]
    assert args["idList"] == "list_todo"
    assert args["idMembers"] == "member_marcus"
    assert args["name"] == "Draft notes"


def test_create_task_with_no_assignee_omits_optional_idmembers(tmp_path, patch_trello_client):
    fake = _FakeComposioClient(_FakeToolsResource({"TRELLO_ADD_CARDS": _ok({"id": "card_1"})}))
    patch_trello_client(fake)
    trello = LiveTrello(store_path=tmp_path / "idem.json")

    trello.create_task("idem-1", "Draft notes", None, None, "list_todo", "desc")
    _, args, _ = fake.tools.calls[0]
    assert "idMembers" not in args


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


def test_trello_create_and_readback_pass_dated_toolkit_version(tmp_path, patch_trello_client):
    class VersionRequiredTools:
        def __init__(self):
            self.slugs = []

        def execute(self, slug, arguments, user_id=None, *, version):
            # Unlike the permissive fake, enforce the SDK version boundary.
            assert version == "20261007_01"
            self.slugs.append(slug)
            return {"successful": True, "data": {"id": "card_versioned"}}

    tools = VersionRequiredTools()
    patch_trello_client(_FakeComposioClient(tools))
    trello = LiveTrello(store_path=tmp_path / "idem.json")
    created = trello.create_task("version-test", "Slides", None, None, "list_test", "demo")
    trello.get_card(created["id"])
    assert tools.slugs == ["TRELLO_ADD_CARDS", "TRELLO_GET_CARDS_BY_ID_CARD"]


def test_trello_verifies_string_member_request_and_timestamp_readback(tmp_path, patch_trello_client):
    from agent.participants import Roster
    from agent.resolver import ResolvedAction
    from agent.schema import ActionItem
    from agent.verifier import execute_with_recovery

    class TrelloContractTools:
        def execute(self, slug, arguments, user_id=None, *, version):
            assert version == "20261007_01"
            if slug == "TRELLO_ADD_CARDS":
                # Reproduce the live tool's text parsing, which fails on lists.
                member = arguments["idMembers"].strip()
                self.card = {
                    "id": "card_contract", "name": arguments["name"],
                    "desc": arguments["desc"], "idList": arguments["idList"],
                    "idMembers": [member], "due": "2026-11-06T12:00:00.000Z",
                }
                return {"successful": True, "data": {"card": self.card}}
            assert slug == "TRELLO_GET_CARDS_BY_ID_CARD"
            assert arguments == {"idCard": "card_contract", "fields": "name,desc,idList,idMembers,due,url"}
            return {"successful": True, "data": {"card": self.card}}

    patch_trello_client(_FakeComposioClient(TrelloContractTools()))
    trello = LiveTrello(store_path=tmp_path / "idem.json")
    roster = Roster([{"name": "Arjun", "email": "", "trello_member_id": "member_test"}])
    item = ActionItem(id="demo-1", transcript_id="demo", task="Prepare slides",
                      owner="Arjun", tool="trello_task", due="2026-11-06")
    resolved = ResolvedAction(owner="Arjun", tool="trello_task", task_text=item.task,
                              description="Demo", due=item.due, attendees_or_recipients=[],
                              confidence_notes="", unresolved=False)
    outcome = execute_with_recovery(item, resolved, roster, {"trello": trello}, "contract-test")
    assert outcome.verified
    assert outcome.created_object["assignee_member_id"] == "member_test"
    assert outcome.created_object["due"] == "2026-11-06"


@pytest.mark.parametrize("returned_due", ["2026-11-07T12:00:00Z", None, "invalid"])
def test_trello_date_normalization_preserves_wrong_or_missing_dates(returned_due):
    from agent.tools.live_trello import _normalize_card

    card = _normalize_card({"id": "card_1", "due": returned_due}, None, "", "")
    assert card["due"] != "2026-11-06"


def test_trello_reproduces_midnight_utc_previous_local_day():
    from agent.tools.live_trello import _normalize_card, trello_due_timestamp

    assert _normalize_card({"due": "2026-11-06T00:00:00.000Z"}, None, "", "")["due"] == "2026-11-05"
    assert trello_due_timestamp("2026-11-06") == "2026-11-06T17:00:00-07:00"
    assert _normalize_card({"due": "2026-11-07T00:00:00Z"}, None, "", "")["due"] == "2026-11-06"
    assert trello_due_timestamp(None) is None


def test_trello_deadline_respects_constructor_timezone(tmp_path, patch_trello_client):
    fake = _FakeComposioClient(_FakeToolsResource({"TRELLO_ADD_CARDS": _ok({"id": "card_1"})}))
    patch_trello_client(fake)
    trello = LiveTrello(store_path=tmp_path / "idem.json", timezone_name="America/New_York")
    trello.create_task("summer", "Slides", None, "2026-07-01", "list_todo", "")
    assert fake.tools.calls[0][1]["due"] == "2026-07-01T17:00:00-04:00"


def test_calendar_create_and_get_require_pinned_version(tmp_path, patch_calendar_client):
    class VersionRequiredTools(_FakeToolsResource):
        def execute(self, slug, arguments, user_id=None, *, version):
            assert version == "20261010_00"
            return super().execute(slug, arguments, user_id)

    tools = VersionRequiredTools({
        "GOOGLECALENDAR_CREATE_EVENT": _ok({"id": "event_versioned"}),
        "GOOGLECALENDAR_EVENTS_GET": _ok({"id": "event_versioned"}),
    })
    patch_calendar_client(_FakeComposioClient(tools))
    calendar = LiveCalendar(store_path=tmp_path / "calendar.json")
    event = calendar.create_calendar_event("pin", "Rehearsal", "2026-11-08T10:00:00",
                                           "2026-11-08T10:30:00", [], "Demo")
    calendar.get_event(event["id"])
    assert [call[0] for call in tools.calls] == ["GOOGLECALENDAR_CREATE_EVENT", "GOOGLECALENDAR_EVENTS_GET"]


def test_gmail_create_and_get_require_pinned_version(tmp_path, patch_gmail_client):
    class VersionRequiredTools(_FakeToolsResource):
        def execute(self, slug, arguments, user_id=None, *, version):
            assert version == "20261029_00"
            return super().execute(slug, arguments, user_id)

    tools = VersionRequiredTools({
        "GMAIL_CREATE_EMAIL_DRAFT": _ok({"id": "draft_versioned"}),
        "GMAIL_GET_DRAFT": _ok({"id": "draft_versioned"}),
    })
    patch_gmail_client(_FakeComposioClient(tools))
    gmail = LiveGmailDrafts(store_path=tmp_path / "gmail.json")
    draft = gmail.create_email_draft("pin", ["self@example.com"], "Agenda", "Demo")
    gmail.get_draft(draft["id"])
    assert [call[0] for call in tools.calls] == ["GMAIL_CREATE_EMAIL_DRAFT", "GMAIL_GET_DRAFT"]


def test_calendar_explicit_timezone_options_and_utc_readback(tmp_path, patch_calendar_client):
    from agent.tools.live_calendar import _normalize_event

    tools = _FakeToolsResource({"GOOGLECALENDAR_CREATE_EVENT": _ok({"id": "evt_demo"})})
    patch_calendar_client(_FakeComposioClient(tools))
    calendar = LiveCalendar(store_path=tmp_path / "calendar.json")
    calendar.create_calendar_event("demo", "Rehearsal", "2026-11-08T10:00:00",
                                   "2026-11-08T10:30:00", ["self@example.com"], "Demo")
    args = tools.calls[0][1]
    assert args["timezone"] == "America/Phoenix"
    assert args["send_updates"] == "none"
    assert args["create_meeting_room"] is False
    assert args["exclude_organizer"] is True
    normalized = _normalize_event({"id": "evt_demo", "summary": "Rehearsal",
        "start": {"dateTime": "2026-11-08T17:00:00Z"},
        "end": {"dateTime": "2026-11-08T17:30:00Z"}}, "", "")
    assert normalized["start"] == "2026-11-08T10:00:00"
    assert normalized["end"] == "2026-11-08T10:30:00"


def test_gmail_raw_mime_roundtrip_html_unicode_and_multiline(tmp_path, patch_gmail_client):
    import base64
    from email.message import EmailMessage

    class MimeTools:
        def execute(self, slug, arguments, user_id=None, *, version):
            assert version == "20261029_00"
            if slug == "GMAIL_CREATE_EMAIL_DRAFT":
                assert arguments["include_signature"] is False
                assert arguments["is_html"] is True
                assert arguments["cc"] == [] and arguments["bcc"] == []
                mail = EmailMessage()
                mail["To"] = ", ".join([arguments["recipient_email"]] + arguments["extra_recipients"])
                mail["Subject"] = arguments["subject"]
                mail.set_content(arguments["body"], subtype="html")
                self.encoded = base64.urlsafe_b64encode(mail.as_bytes()).decode().rstrip("=")
                return {"successful": True, "data": {"id": "draft_mime"}}
            assert slug == "GMAIL_GET_DRAFT"
            assert arguments == {"draft_id": "draft_mime", "format": "raw", "user_id": "me"}
            return {"successful": True, "data": {"id": "draft_mime", "message": {"raw": self.encoded}}}

    patch_gmail_client(_FakeComposioClient(MimeTools()))
    gmail = LiveGmailDrafts(store_path=tmp_path / "gmail.json")
    recipients = ["self@example.com", "second@example.com"]
    body = "Review A & B <notes>\nThen rehearse café demo."
    gmail.create_email_draft("mime", recipients, "Agenda – demo", body)
    assert gmail.get_draft("draft_mime") == {"id": "draft_mime", "to": recipients,
                                           "subject": "Agenda – demo", "body": body}


def test_gmail_missing_mime_fields_are_not_filled_from_intended_content():
    import base64
    from agent.tools.live_gmail import _normalize_draft

    raw = base64.urlsafe_b64encode(b"Subject: Wrong\r\n\r\nDifferent body").decode()
    result = _normalize_draft({"id": "draft_1", "message": {"raw": raw}},
                              ["expected@example.com"], "Expected", "Expected body")
    assert result["to"] == []
    assert result["subject"] == "Wrong"
    assert result["body"] != "Expected body"


def test_calendar_response_data_envelope_is_saved_and_read_back(tmp_path, patch_calendar_client):
    event = {"id": "event_wrapped", "summary": "Schedule a capstone demo rehearsal",
             "start": {"dateTime": "2026-11-08T10:00:00-07:00"},
             "end": {"dateTime": "2026-11-08T10:30:00-07:00"},
             "attendees": [{"email": "self@example.com"}], "description": "Demo rehearsal"}
    tools = _FakeToolsResource({
        "GOOGLECALENDAR_CREATE_EVENT": _ok({"response_data": event, "display_url": "https://calendar.google.com"}),
        "GOOGLECALENDAR_EVENTS_GET": _ok({"response_data": event}),
    })
    patch_calendar_client(_FakeComposioClient(tools))
    calendar = LiveCalendar(store_path=tmp_path / "calendar.json")
    created = calendar.create_calendar_event("wrapped", event["summary"], "2026-11-08T10:00:00",
                                            "2026-11-08T10:30:00", ["self@example.com"], event["description"])
    assert created["id"] == "event_wrapped"
    # Replaying uses the stored object ID, not another create request.
    replay = calendar.create_calendar_event("wrapped", event["summary"], "2026-11-08T10:00:00",
                                           "2026-11-08T10:30:00", ["self@example.com"], event["description"])
    assert replay == created
    assert [call[0] for call in tools.calls] == ["GOOGLECALENDAR_CREATE_EVENT", "GOOGLECALENDAR_EVENTS_GET"]


def test_gmail_response_data_envelope_is_saved_and_read_back(tmp_path, patch_gmail_client):
    tools = _FakeToolsResource({
        "GMAIL_CREATE_EMAIL_DRAFT": _ok({"response_data": {"id": "draft_wrapped"}}),
        "GMAIL_GET_DRAFT": _ok({"response_data": {"draft": {
            "id": "draft_wrapped", "to": ["self@example.com"], "subject": "Agenda", "body": "Demo"}}}),
    })
    patch_gmail_client(_FakeComposioClient(tools))
    gmail = LiveGmailDrafts(store_path=tmp_path / "gmail.json")
    draft = gmail.create_email_draft("wrapped", ["self@example.com"], "Agenda", "Demo")
    assert gmail.get_draft(draft["id"]) == draft
