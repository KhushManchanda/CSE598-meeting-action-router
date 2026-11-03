"""
Tests for baselines/b0_adapter.py.

These assert the adapter faithfully captures what B0 *actually* outputs
(including its documented bugs) in our common schema — they are not
testing whether B0's behavior is good.
"""

from pathlib import Path

from baselines.b0_adapter import run_b0_on_transcript

TEST1 = Path(__file__).resolve().parents[1] / "baselines" / "b0_rules" / "examples" / "test1.txt"

EXPECTED_OWNERS = ["Priya", "Priya", "Marcus", "Priya", "Jordan", "Priya", "Marcus"]
EXPECTED_TOOLS = [
    "calendar_event",
    "email_draft",
    "email_draft",
    "email_draft",
    "trello_task",
    "trello_task",
    "trello_task",
]
EXPECTED_EVIDENCE = [["u3"], ["u5"], ["u6"], ["u7"], ["u8"], ["u9"], ["u10"]]


def _predictions():
    return run_b0_on_transcript(TEST1, transcript_id="test1")


def test_detects_all_seven_action_items():
    preds = _predictions()
    assert len(preds) == 7


def test_owners_match_b0s_actual_speaker_based_output():
    preds = _predictions()
    assert [p.owner for p in preds] == EXPECTED_OWNERS


def test_tools_mapped_to_canonical_names():
    preds = _predictions()
    assert [p.tool for p in preds] == EXPECTED_TOOLS


def test_due_is_always_none_b0_never_resolves_dates():
    preds = _predictions()
    assert all(p.due is None for p in preds)


def test_evidence_utterance_ids_align_with_source_lines():
    preds = _predictions()
    assert [p.evidence_utterance_ids for p in preds] == EXPECTED_EVIDENCE


def test_email_recipients_are_the_buggy_owner_not_a_real_recipient():
    preds = _predictions()
    email_preds = [p for p in preds if p.tool == "email_draft"]
    assert len(email_preds) == 3
    for p in email_preds:
        assert p.attendees_or_recipients == [p.owner]


def test_ids_are_stable_and_namespaced_by_transcript():
    preds = _predictions()
    assert [p.id for p in preds] == [f"test1-b0-{i}" for i in range(1, 8)]
    assert all(p.transcript_id == "test1" for p in preds)
