from agent.approval_cli import review_item
from agent.resolver import ResolvedAction
from agent.schema import ActionItem


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
        due="2026-09-04", attendees_or_recipients=[], confidence_notes="high confidence", unresolved=False,
    )
    defaults.update(kwargs)
    return ResolvedAction(**defaults)


def _scripted_input(responses):
    it = iter(responses)
    return lambda prompt: next(it)


def test_auto_approve_skips_prompting_and_logs_it():
    printed = []
    decision = review_item(_item(), _resolved_action(), auto_approve=True, print_fn=printed.append)
    assert decision.decision == "approved"
    assert decision.auto_approved is True
    assert any("auto-approve" in line for line in printed)


def test_default_empty_input_approves():
    decision = review_item(_item(), _resolved_action(), input_fn=_scripted_input([""]), print_fn=lambda s: None)
    assert decision.decision == "approved"
    assert decision.auto_approved is False


def test_explicit_approve():
    decision = review_item(_item(), _resolved_action(), input_fn=_scripted_input(["a"]), print_fn=lambda s: None)
    assert decision.decision == "approved"


def test_reject():
    decision = review_item(_item(), _resolved_action(), input_fn=_scripted_input(["r"]), print_fn=lambda s: None)
    assert decision.decision == "rejected"


def test_edit_a_single_field():
    decision = review_item(
        _item(), _resolved_action(),
        input_fn=_scripted_input(["e", "owner", "Priya", ""]),
        print_fn=lambda s: None,
    )
    assert decision.decision == "edited"
    assert decision.edits == {"owner": "Priya"}


def test_edit_attendees_or_recipients_is_parsed_as_a_list():
    decision = review_item(
        _item(), _resolved_action(),
        input_fn=_scripted_input(["edit", "attendees_or_recipients", "a@x.com, b@x.com", ""]),
        print_fn=lambda s: None,
    )
    assert decision.edits == {"attendees_or_recipients": ["a@x.com", "b@x.com"]}


def test_edit_unknown_field_is_skipped_but_loop_continues():
    decision = review_item(
        _item(), _resolved_action(),
        input_fn=_scripted_input(["e", "not_a_real_field", "owner", "Priya", ""]),
        print_fn=lambda s: None,
    )
    assert decision.edits == {"owner": "Priya"}


def test_unrecognized_top_level_input_defaults_to_reject():
    decision = review_item(_item(), _resolved_action(), input_fn=_scripted_input(["blah"]), print_fn=lambda s: None)
    assert decision.decision == "rejected"


def test_render_includes_key_fields():
    printed = []
    review_item(_item(), _resolved_action(), input_fn=_scripted_input(["a"]), print_fn=printed.append)
    rendered = "\n".join(printed)
    assert "Draft release notes" in rendered
    assert "Marcus" in rendered
    assert "trello_task" in rendered
    assert "high confidence" in rendered
