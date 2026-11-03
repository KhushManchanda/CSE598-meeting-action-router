import pytest

from agent.ledger import (
    APPROVED, ESCALATED, EXECUTED, PROPOSED, REJECTED, RESOLVED, VALIDATED, VERIFIED, Ledger,
)


@pytest.fixture
def ledger():
    led = Ledger(":memory:")
    yield led
    led.close()


def test_propose_creates_row_in_proposed_state(ledger):
    action_id = ledger.propose(
        meeting_id="t1", extraction_index=1, task="Schedule a demo",
        raw_owner_text="Marcus", raw_due_text="next week",
        evidence_quote="Marcus will schedule a demo", evidence_utterance_ids=["u3"],
    )
    assert action_id == "t1-1"
    record = ledger.get(action_id)
    assert record.state == PROPOSED
    assert record.task == "Schedule a demo"
    assert record.evidence_utterance_ids == ["u3"]
    assert record.repair_attempts == 0
    assert record.execution_attempts == 0


def test_action_id_is_deterministic_from_meeting_and_index(ledger):
    assert ledger.action_id("t1", 3) == "t1-3"


def test_set_resolved_transitions_to_resolved(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.set_resolved(aid, owner="Marcus", due=None, tool="calendar_event", attendees_or_recipients=[])
    record = ledger.get(aid)
    assert record.state == RESOLVED
    assert record.owner == "Marcus"
    assert record.tool == "calendar_event"


def test_validation_with_no_errors_moves_to_validated(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.set_resolved(aid, "Marcus", None, "calendar_event", [])
    ledger.set_validation_result(aid, errors=[])
    assert ledger.get(aid).state == VALIDATED
    assert ledger.get(aid).validation_errors == []


def test_validation_with_errors_sends_back_to_resolved_for_repair(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.set_resolved(aid, "Marcus", None, "calendar_event", [])
    ledger.set_validation_result(aid, errors=["owner not in roster"])
    record = ledger.get(aid)
    assert record.state == RESOLVED
    assert record.validation_errors == ["owner not in roster"]


def test_repair_attempts_increment(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    assert ledger.increment_repair_attempt(aid) == 1
    assert ledger.increment_repair_attempt(aid) == 2
    assert ledger.get(aid).repair_attempts == 2


def test_escalate_sets_state_and_reason(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.escalate(aid, reason="ambiguous owner after 2 repair attempts")
    record = ledger.get(aid)
    assert record.state == ESCALATED
    assert record.escalation_reason == "ambiguous owner after 2 repair attempts"


def test_approval_approved_moves_to_approved(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.set_resolved(aid, "Marcus", None, "calendar_event", [])
    ledger.set_validation_result(aid, [])
    ledger.set_approval(aid, decision="approved", auto_approved=False)
    record = ledger.get(aid)
    assert record.state == APPROVED
    assert record.approval_decision == "approved"
    assert record.auto_approved is False


def test_approval_rejected_moves_to_rejected(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.set_approval(aid, decision="rejected", auto_approved=False)
    record = ledger.get(aid)
    assert record.state == REJECTED
    assert record.approval_decision == "rejected"


def test_approval_edited_goes_back_to_resolved_with_new_fields(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.set_resolved(aid, "Marcus", None, "calendar_event", [])
    ledger.set_validation_result(aid, [])
    ledger.set_approval(aid, decision="edited", auto_approved=False, owner="Priya")
    record = ledger.get(aid)
    assert record.state == RESOLVED  # edits must re-enter the validator
    assert record.owner == "Priya"
    assert record.approval_decision == "edited"


def test_record_execution_attempt_success_moves_to_executed(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    attempts = ledger.record_execution_attempt(aid, success=True, created_object={"id": "evt_1"})
    record = ledger.get(aid)
    assert attempts == 1
    assert record.state == EXECUTED
    assert record.created_object == {"id": "evt_1"}


def test_record_execution_attempt_failure_keeps_state_for_retry(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.set_resolved(aid, "Marcus", None, "calendar_event", [])
    ledger._update(aid, state=APPROVED)
    ledger.record_execution_attempt(aid, success=False, error="RateLimitError: simulated 429")
    record = ledger.get(aid)
    assert record.state == APPROVED  # unchanged -- caller decides whether to retry
    assert record.execution_attempts == 1
    assert record.execution_error == "RateLimitError: simulated 429"


def test_set_verified_true_moves_to_verified(ledger):
    aid = ledger.propose("t1", 1, "x", None, None, "q", ["u1"])
    ledger.record_execution_attempt(aid, success=True, created_object={"id": "evt_1"})
    ledger.set_verified(aid, verified=True)
    record = ledger.get(aid)
    assert record.state == VERIFIED
    assert record.verified is True


def test_list_for_meeting_orders_by_id(ledger):
    ledger.propose("t1", 2, "b", None, None, "q", [])
    ledger.propose("t1", 1, "a", None, None, "q", [])
    ledger.propose("t2", 1, "c", None, None, "q", [])
    records = ledger.list_for_meeting("t1")
    assert [r.id for r in records] == ["t1-1", "t1-2"]


def test_reproposing_an_already_advanced_item_is_a_no_op():
    """Rerunning the same meeting re-extracts (cheap, side-effect-free) but
    must not reset progress already made on an action_id that's moved past
    PROPOSED -- this is what lets a persisted ledger skip re-executing
    already-EXECUTED items on a rerun."""
    ledger = Ledger(":memory:")
    aid = ledger.propose("t1", 1, "original task", None, None, "q", ["u1"])
    ledger.set_resolved(aid, "Marcus", None, "calendar_event", [])
    ledger.record_execution_attempt(aid, success=True, created_object={"id": "evt_1"})

    # Simulate a rerun's extractor proposing the "same" item again with
    # (possibly slightly different, since LLM re-extraction isn't perfectly
    # deterministic) task text at the same index.
    ledger.propose("t1", 1, "reworded task", None, None, "q2", ["u3"])

    record = ledger.get(aid)
    assert record.state == EXECUTED  # NOT reset back to proposed
    assert record.task == "original task"  # NOT overwritten
    ledger.close()
