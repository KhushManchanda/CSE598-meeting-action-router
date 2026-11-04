"""
Tests for eval/score.py, exercised against B0's real output on test1.txt.

Two owner-accuracy checks on purpose:

  test_owner_accuracy_raw_matches_readme_claim_on_reference_fixture
      Sanity-checks the SCORER's arithmetic against a literal
      transcription of baselines/b0_rules/README.md's own claim
      ("4 of 7 items, i.e. 57.1%"). This fixture is NOT our gold — see
      tests/fixtures/b0_readme_reference_owners.json and
      data/gold/test1.NOTES.md for why it encodes an inconsistency we
      don't want to inherit into real gold.

  test_owner_accuracy_raw_on_our_gold
      The real number using our own, consistently cross-turn-resolved
      gold (data/gold/test1.json): 3 of 7 (42.9%), one lower than the
      README's claim, because our gold also flags B0's raw-item 3 as
      mis-attributed (see NOTES.md). We report this honestly rather
      than forcing a match to the README's number.
"""

from pathlib import Path

import pytest

from baselines.b0_adapter import run_b0_on_transcript
from eval.score import load_items, owner_accuracy_raw, score

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST1 = REPO_ROOT / "baselines" / "b0_rules" / "examples" / "test1.txt"
GOLD = REPO_ROOT / "data" / "gold" / "test1.json"
README_REFERENCE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "b0_readme_reference_owners.json"


@pytest.fixture
def b0_predictions():
    return run_b0_on_transcript(TEST1, transcript_id="test1")


def test_owner_accuracy_raw_matches_readme_claim_on_reference_fixture(b0_predictions):
    reference = load_items(README_REFERENCE_FIXTURE)
    result = owner_accuracy_raw(b0_predictions, reference)
    assert result["correct"] == 4
    assert result["total"] == 7
    assert result["accuracy"] == pytest.approx(4 / 7)  # 0.5714285714285714 ~= 57.1%


def test_owner_accuracy_raw_on_our_gold(b0_predictions):
    gold = load_items(GOLD)
    result = owner_accuracy_raw(b0_predictions, gold)
    assert result["correct"] == 3
    assert result["total"] == 7
    assert result["accuracy"] == pytest.approx(3 / 7)  # 0.4286 -- see docstring above


def test_full_score_matched_metrics_on_our_gold(b0_predictions):
    gold = load_items(GOLD)
    result = score(b0_predictions, gold)
    # 7 predictions, 6 real gold items. G3 and G5 each attract two B0
    # predictions (the duplicate-prediction bug); greedy matching claims
    # the better-scoring one per gold item and leaves the other as an
    # unmatched extra, so true_positives == n_gold, not n_predictions.
    assert result["n_predictions"] == 7
    assert result["n_gold"] == 6
    assert result["true_positives"] == 6
    assert result["false_positives"] == 1  # one duplicate prediction left over
    assert result["false_negatives"] == 0
    assert result["recall"] == pytest.approx(1.0)
    assert result["precision"] == pytest.approx(6 / 7)


def test_f1_is_zero_not_none_when_precision_is_zero():
    # Regression: `if precision and recall` treated a real 0.0 (tp=0,
    # fp>0 -- predictions exist but none match gold) as "undefined" and
    # returned None instead of the correct F1=0.0. Found while
    # preparing results for sponsor review.
    from agent.schema import ActionItem

    pred = ActionItem(id="p1", transcript_id="t", task="totally unrelated", owner="Nobody", evidence_utterance_ids=["u99"])
    gold_item = ActionItem(id="g1", transcript_id="t", task="Schedule a demo", owner="Marcus", evidence_utterance_ids=["u3"])
    result = score([pred], [gold_item])
    assert result["precision"] == 0.0
    assert result["f1"] == 0.0


def test_f1_is_none_when_no_predictions_and_no_gold():
    result = score([], [])
    assert result["precision"] is None
    assert result["recall"] is None
    assert result["f1"] is None
