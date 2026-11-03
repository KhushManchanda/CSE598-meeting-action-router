"""
Tests for agent/tools/mock_backend.py — idempotency and fault injection.

Parametrized across all three fake backends (Calendar, Trello, Gmail
drafts) via the _CASES table below, since the idempotency/fault-plan
machinery they share is the thing actually under test.
"""

import pytest

from agent.tools.errors import (
    ExpiredAuthError,
    InvalidArgumentError,
    RateLimitError,
    ResponseLostError,
    ServiceUnavailableError,
    ToolTimeoutError,
)
from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello


def _make_calendar():
    backend = MockCalendar()
    call = lambda key: backend.create_calendar_event(
        key, title="Demo", start="2026-09-09T10:00:00", end="2026-09-09T10:30:00",
        attendees=["marcus@example.com"], description="demo"
    )
    return backend, call, backend.get_event


def _make_trello():
    backend = MockTrello()
    call = lambda key: backend.create_task(
        key, title="Draft notes", assignee_member_id="member_1", due="2026-09-04",
        list_id="list_1", description="release notes"
    )
    return backend, call, backend.get_card


def _make_gmail():
    backend = MockGmailDrafts()
    call = lambda key: backend.create_email_draft(
        key, to=["legal@example.com"], subject="Vendor contract", body="..."
    )
    return backend, call, backend.get_draft


_CASES = [_make_calendar, _make_trello, _make_gmail]


@pytest.mark.parametrize("make", _CASES)
def test_create_then_read_back_matches(make):
    backend, call, get = make()
    record = call("idem-1")
    fetched = get(record["id"])
    assert fetched == record


@pytest.mark.parametrize("make", _CASES)
def test_same_idempotency_key_never_creates_a_duplicate(make):
    backend, call, get = make()
    first = call("idem-1")
    second = call("idem-1")
    third = call("idem-1")
    assert first["id"] == second["id"] == third["id"]
    assert len(backend.all_objects()) == 1


@pytest.mark.parametrize("make", _CASES)
def test_different_idempotency_keys_create_different_objects(make):
    backend, call, get = make()
    a = call("idem-a")
    b = call("idem-b")
    assert a["id"] != b["id"]
    assert len(backend.all_objects()) == 2


@pytest.mark.parametrize(
    "fault_name,expected_exc",
    [
        ("429", RateLimitError),
        ("503", ServiceUnavailableError),
        ("timeout", ToolTimeoutError),
        ("invalid_argument", InvalidArgumentError),
        ("expired_token", ExpiredAuthError),
    ],
)
@pytest.mark.parametrize("make", _CASES)
def test_fault_plan_raises_expected_exception_and_commits_nothing(make, fault_name, expected_exc):
    backend, call, get = make()
    backend.set_fault_plan("idem-1", [fault_name])
    with pytest.raises(expected_exc):
        call("idem-1")
    assert backend.all_objects() == {}  # non-lost_response faults must not commit anything


@pytest.mark.parametrize("make", _CASES)
def test_lost_response_commits_object_but_raises(make):
    backend, call, get = make()
    backend.set_fault_plan("idem-1", ["lost_response"])
    with pytest.raises(ResponseLostError):
        call("idem-1")
    # The object WAS committed server-side even though the call raised.
    assert len(backend.all_objects()) == 1


@pytest.mark.parametrize("make", _CASES)
def test_retry_after_lost_response_recovers_the_same_object_not_a_duplicate(make):
    backend, call, get = make()
    backend.set_fault_plan("idem-1", ["lost_response"])
    with pytest.raises(ResponseLostError):
        call("idem-1")

    # Caller retries with the SAME idempotency key, as the spec's verifier
    # is required to do. No fault left scheduled -> should now succeed by
    # returning the object that was already committed, not a new one.
    recovered = call("idem-1")
    assert len(backend.all_objects()) == 1
    assert recovered["id"] in backend.all_objects()


@pytest.mark.parametrize("make", _CASES)
def test_fault_plan_is_consumed_in_order_then_succeeds(make):
    backend, call, get = make()
    backend.set_fault_plan("idem-1", ["429", "503", None])
    with pytest.raises(RateLimitError):
        call("idem-1")
    with pytest.raises(ServiceUnavailableError):
        call("idem-1")
    record = call("idem-1")  # 3rd attempt: plan exhausted to None -> succeeds
    assert len(backend.all_objects()) == 1
    assert record["id"].startswith(backend._id_prefix)


@pytest.mark.parametrize("make", _CASES)
def test_get_unknown_id_raises_invalid_argument(make):
    backend, call, get = make()
    with pytest.raises(InvalidArgumentError):
        get("does-not-exist")


def test_calendar_missing_required_field_raises_invalid_argument_before_any_fault():
    backend = MockCalendar()
    with pytest.raises(InvalidArgumentError):
        backend.create_calendar_event(
            "idem-1", title="", start="2026-09-09T10:00:00", end="2026-09-09T10:30:00",
            attendees=[], description="x"
        )
    assert backend.all_objects() == {}


def test_trello_missing_required_field_raises_invalid_argument():
    backend = MockTrello()
    with pytest.raises(InvalidArgumentError):
        backend.create_task(
            "idem-1", title="Task", assignee_member_id="m1", due=None, list_id="", description=""
        )


def test_gmail_missing_required_field_raises_invalid_argument():
    backend = MockGmailDrafts()
    with pytest.raises(InvalidArgumentError):
        backend.create_email_draft("idem-1", to=[], subject="", body="x")


def test_reset_clears_all_state():
    backend = MockCalendar()
    backend.create_calendar_event(
        "idem-1", title="Demo", start="2026-09-09T10:00:00", end="2026-09-09T10:30:00",
        attendees=[], description="x"
    )
    backend.reset()
    assert backend.all_objects() == {}
