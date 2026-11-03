import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from review_gold import _load_json, _save_json, main, review_items

DRAFT_ITEMS = [
    {
        "id": "t1-gold-1", "transcript_id": "t1", "task": "Schedule a demo", "owner": "Marcus",
        "tool": "calendar_event", "due": None, "attendees_or_recipients": [],
        "evidence_utterance_ids": ["u3"], "category": "baseline",
    },
    {
        "id": "t1-gold-2", "transcript_id": "t1", "task": "Email legal", "owner": "Priya",
        "tool": "email_draft", "due": None, "attendees_or_recipients": [],
        "evidence_utterance_ids": ["u7"], "category": "baseline",
    },
]


def _scripted_input(responses):
    it = iter(responses)
    return lambda prompt: next(it)


def test_accept_default_keeps_item_unchanged():
    reviewed = review_items(DRAFT_ITEMS, already_reviewed_ids=set(), input_fn=_scripted_input(["", ""]), print_fn=lambda s: None)
    assert len(reviewed) == 2
    assert reviewed[0] == DRAFT_ITEMS[0]


def test_already_reviewed_ids_are_skipped_without_prompting():
    calls = []
    reviewed = review_items(
        DRAFT_ITEMS, already_reviewed_ids={"t1-gold-1"},
        input_fn=lambda p: (calls.append(p) or "a"), print_fn=lambda s: None,
    )
    assert len(reviewed) == 1
    assert reviewed[0]["id"] == "t1-gold-2"
    assert len(calls) == 1  # only prompted once, for the non-reviewed item


def test_skip_excludes_item_from_results():
    reviewed = review_items(DRAFT_ITEMS, already_reviewed_ids=set(), input_fn=_scripted_input(["s", "a"]), print_fn=lambda s: None)
    assert len(reviewed) == 1
    assert reviewed[0]["id"] == "t1-gold-2"


def test_fix_changes_a_field_and_validates_before_accepting():
    reviewed = review_items(
        DRAFT_ITEMS, already_reviewed_ids=set(),
        input_fn=_scripted_input(["f", "owner", "SomeoneElse", "", "a"]), print_fn=lambda s: None,
    )
    assert reviewed[0]["owner"] == "SomeoneElse"
    assert reviewed[0]["id"] == "t1-gold-1"


def test_fix_with_invalid_result_raises_instead_of_silently_accepting():
    import pytest

    with pytest.raises(Exception):
        review_items(
            DRAFT_ITEMS, already_reviewed_ids=set(),
            input_fn=_scripted_input(["f", "tool", "not_a_real_tool", ""]), print_fn=lambda s: None,
        )


def test_unrecognized_input_is_treated_as_skip():
    reviewed = review_items(DRAFT_ITEMS, already_reviewed_ids=set(), input_fn=_scripted_input(["blah", "a"]), print_fn=lambda s: None)
    assert len(reviewed) == 1
    assert reviewed[0]["id"] == "t1-gold-2"


def test_end_to_end_cli_writes_only_newly_reviewed_items(tmp_path, monkeypatch):
    draft_dir = tmp_path / "gold_draft"
    gold_dir = tmp_path / "gold"
    draft_dir.mkdir()
    (draft_dir / "t1.json").write_text(json.dumps(DRAFT_ITEMS), encoding="utf-8")

    inputs = iter(["a", "s"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    monkeypatch.setattr(sys, "argv", ["review_gold.py", "--transcript-id", "t1", "--draft-dir", str(draft_dir), "--gold-dir", str(gold_dir)])

    main()

    gold_items = _load_json(gold_dir / "t1.json")
    assert len(gold_items) == 1
    assert gold_items[0]["id"] == "t1-gold-1"


def test_rerunning_the_cli_does_not_reprompt_already_reviewed_items(tmp_path, monkeypatch):
    draft_dir = tmp_path / "gold_draft"
    gold_dir = tmp_path / "gold"
    draft_dir.mkdir()
    (draft_dir / "t1.json").write_text(json.dumps(DRAFT_ITEMS), encoding="utf-8")
    _save_json(gold_dir / "t1.json", [DRAFT_ITEMS[0]])  # item 1 already reviewed

    prompts = []
    monkeypatch.setattr("builtins.input", lambda prompt="": (prompts.append(prompt) or "a"))
    monkeypatch.setattr(sys, "argv", ["review_gold.py", "--transcript-id", "t1", "--draft-dir", str(draft_dir), "--gold-dir", str(gold_dir)])

    main()

    gold_items = _load_json(gold_dir / "t1.json")
    assert len(gold_items) == 2
    assert len(prompts) == 1  # only item 2 prompted
