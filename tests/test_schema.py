import pytest
from pydantic import ValidationError

from agent.schema import ActionItem


def test_valid_action_item_roundtrips():
    item = ActionItem(
        id="t-1",
        transcript_id="t",
        task="Do the thing",
        owner="Priya",
        tool="trello_task",
        due="2026-09-04",
        attendees_or_recipients=["priya@example.com"],
        evidence_utterance_ids=["u1"],
    )
    assert item.model_dump()["due"] == "2026-09-04"


def test_minimal_action_item_defaults():
    item = ActionItem(id="t-1", transcript_id="t", task="Do the thing")
    assert item.owner is None
    assert item.tool is None
    assert item.due is None
    assert item.attendees_or_recipients == []
    assert item.evidence_utterance_ids == []


def test_rejects_non_canonical_tool():
    with pytest.raises(ValidationError):
        ActionItem(id="t-1", transcript_id="t", task="x", tool="schedule_event")


def test_rejects_non_iso_due_date():
    with pytest.raises(ValidationError):
        ActionItem(id="t-1", transcript_id="t", task="x", due="next Friday")


def test_rejects_empty_task():
    with pytest.raises(ValidationError):
        ActionItem(id="t-1", transcript_id="t", task="")


def test_rejects_unknown_extra_field():
    with pytest.raises(ValidationError):
        ActionItem(id="t-1", transcript_id="t", task="x", unexpected_field="nope")


def test_category_accepts_known_value():
    item = ActionItem(id="t-1", transcript_id="t", task="x", category="ambiguous_escalate")
    assert item.category == "ambiguous_escalate"


def test_category_defaults_to_none():
    item = ActionItem(id="t-1", transcript_id="t", task="x")
    assert item.category is None


def test_category_rejects_unknown_value():
    with pytest.raises(ValidationError):
        ActionItem(id="t-1", transcript_id="t", task="x", category="not_a_real_category")


def test_due_with_full_datetime_is_normalized_to_date_only():
    # Regression: B1 returned "2026-10-08T17:00:00Z" for a trello_task
    # due date in a real eval run; this must normalize, not crash.
    item = ActionItem(id="t-1", transcript_id="t", task="x", due="2026-10-08T17:00:00Z")
    assert item.due == "2026-10-08"


def test_due_with_datetime_no_timezone_is_normalized():
    item = ActionItem(id="t-1", transcript_id="t", task="x", due="2026-10-08T09:00:00")
    assert item.due == "2026-10-08"


def test_due_with_invalid_date_part_after_t_still_raises():
    with pytest.raises(ValidationError):
        ActionItem(id="t-1", transcript_id="t", task="x", due="not-a-date T whatever")
