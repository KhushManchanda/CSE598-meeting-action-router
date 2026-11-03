from agent.participants import Roster
from agent.resolver import ResolvedAction
from agent.schema import ActionItem
from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello
from agent.verifier import execute_with_recovery

ROSTER = Roster(
    [{"name": "Marcus", "aliases": [], "email": "marcus@example.com", "trello_member_id": "member_marcus"}]
)


def _item(**kwargs):
    defaults = dict(
        id="t1-1", transcript_id="t1", task="Draft release notes", owner="Marcus",
        tool="trello_task", due="2026-09-04", attendees_or_recipients=[], evidence_utterance_ids=["u10"],
    )
    defaults.update(kwargs)
    return ActionItem(**defaults)


def _resolved_action(**kwargs):
    defaults = dict(
        owner="Marcus", tool="trello_task", task_text="Draft release notes", description="desc",
        due="2026-09-04", attendees_or_recipients=[], confidence_notes="", unresolved=False,
    )
    defaults.update(kwargs)
    return ResolvedAction(**defaults)


def _tools():
    return {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}


def _no_sleep(_seconds):
    pass


def test_success_path_verifies_and_reads_back():
    tools = _tools()
    outcome = execute_with_recovery(_item(), _resolved_action(), ROSTER, tools, "idem-1", sleep_fn=_no_sleep)
    assert outcome.verified is True
    assert outcome.outcome == "verified"
    assert outcome.attempts == 1
    assert outcome.created_object["title"] == "Draft release notes"


def test_invalid_argument_goes_back_to_resolver_without_retry():
    # agent/schema.py's own validation already rejects an empty title, so to
    # exercise a *backend-rejected* invalid argument (something our schema
    # wouldn't catch but a real API might, e.g. a title the API considers
    # malformed) we fault-inject it directly rather than via ActionItem.
    tools = _tools()
    tools["trello"].set_fault_plan("idem-1", ["invalid_argument"])
    outcome = execute_with_recovery(_item(), _resolved_action(), ROSTER, tools, "idem-1", sleep_fn=_no_sleep)
    assert outcome.verified is False
    assert outcome.outcome == "needs_resolver_repair"
    assert outcome.attempts == 1


def test_expired_token_escalates_without_retry():
    tools = _tools()
    tools["trello"].set_fault_plan("idem-1", ["expired_token"])
    outcome = execute_with_recovery(_item(), _resolved_action(), ROSTER, tools, "idem-1", sleep_fn=_no_sleep)
    assert outcome.verified is False
    assert outcome.outcome == "escalate"
    assert outcome.attempts == 1


def test_transient_error_is_retried_and_eventually_succeeds():
    tools = _tools()
    tools["trello"].set_fault_plan("idem-1", ["429", "503"])
    sleeps = []
    outcome = execute_with_recovery(_item(), _resolved_action(), ROSTER, tools, "idem-1", sleep_fn=sleeps.append)
    assert outcome.verified is True
    assert outcome.attempts == 3
    assert len(sleeps) == 2  # slept before attempts 2 and 3, not after the final success
    assert len(tools["trello"].all_objects()) == 1  # no duplicates from the retries


def test_transient_error_persisting_past_max_retries_escalates():
    tools = _tools()
    tools["trello"].set_fault_plan("idem-1", ["429", "503", "timeout", "429"])
    outcome = execute_with_recovery(_item(), _resolved_action(), ROSTER, tools, "idem-1", max_retries=3, sleep_fn=_no_sleep)
    assert outcome.verified is False
    assert outcome.outcome == "escalate"
    assert outcome.attempts == 3
    assert "persisted after 3 attempts" in outcome.error


def test_lost_response_recovers_the_same_object_on_retry_not_a_duplicate():
    tools = _tools()
    tools["trello"].set_fault_plan("idem-1", ["lost_response"])
    outcome = execute_with_recovery(_item(), _resolved_action(), ROSTER, tools, "idem-1", sleep_fn=_no_sleep)
    assert outcome.verified is True
    assert outcome.attempts == 2
    assert len(tools["trello"].all_objects()) == 1


def test_backoff_fn_is_called_with_increasing_attempt_numbers():
    tools = _tools()
    tools["trello"].set_fault_plan("idem-1", ["429", "503"])
    backoff_calls = []
    execute_with_recovery(
        _item(), _resolved_action(), ROSTER, tools, "idem-1",
        sleep_fn=_no_sleep, backoff_fn=lambda attempt: backoff_calls.append(attempt) or 0,
    )
    assert backoff_calls == [1, 2]


def test_readback_mismatch_escalates():
    class _MismatchTrello:
        def create_task(self, idem_key, **kwargs):
            return {"id": "card_1", **kwargs}

        def get_card(self, card_id):
            return {"id": card_id, "title": "WRONG TITLE", "assignee_member_id": None, "due": None, "list_id": "x", "description": ""}

    tools = {"calendar": MockCalendar(), "trello": _MismatchTrello(), "gmail": MockGmailDrafts()}
    outcome = execute_with_recovery(_item(), _resolved_action(), ROSTER, tools, "idem-1", sleep_fn=_no_sleep)
    assert outcome.verified is False
    assert outcome.outcome == "escalate"
    assert any("title" in m for m in outcome.mismatches)


def test_calendar_event_with_no_due_date_escalates_instead_of_crashing():
    """Regression: build_tool_args raises for tool=calendar_event with
    due=None (agent/router.py's _calendar_start_end needs a real date).
    The validator normally prevents this from ever reaching here, but
    A-noval skips the validator -- this must escalate, not propagate an
    unhandled exception and crash the whole eval run (found via a real
    eval/run_eval.py run exercising A-noval for real)."""
    tools = _tools()
    item = _item(tool="calendar_event", due=None)
    outcome = execute_with_recovery(item, _resolved_action(tool="calendar_event", due=None), ROSTER, tools, "idem-1", sleep_fn=_no_sleep)
    assert outcome.verified is False
    assert outcome.outcome == "escalate"
    assert "due_date" in outcome.error or "NoneType" in outcome.error or "None" in outcome.error
    assert len(tools["calendar"].all_objects()) == 0
