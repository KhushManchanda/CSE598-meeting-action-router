import json

import pytest

from agent.extractor import Candidate
from agent.ingestion import parse_transcript
from agent.llm import LLMCallResult
from agent.participants import Roster
from agent.resolver import resolve

ROSTER = Roster(
    [
        {"name": "Marcus", "aliases": [], "email": "marcus@example.com", "trello_member_id": "member_marcus"},
        {"name": "Priya", "aliases": [], "email": "priya@example.com", "trello_member_id": "member_priya"},
    ]
)

TRANSCRIPT = (
    "Priya: Thanks everyone for joining.\n"
    "Marcus: Also, someone should follow up with legal about the vendor contract.\n"
    "Priya: I'll handle that one. Priya will email the legal team about the vendor contract.\n"
)
UTTERANCES = parse_transcript(TRANSCRIPT)


class _SequentialFakeLLMClient:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def complete(self, messages, tools=None, tool_choice=None, response_format=None):
        self.calls.append(messages)
        if not self._results:
            raise AssertionError("fake LLM client ran out of pre-programmed results")
        return self._results.pop(0)


def _tool_call(id_, tool_name, **kwargs):
    return {"id": id_, "name": tool_name, "arguments": json.dumps(kwargs)}


def _finalize_result(**kwargs):
    defaults = dict(
        owner=None, tool="trello_task", task_text="x", description="", due=None,
        attendees_or_recipients=[], confidence_notes="",
    )
    defaults.update(kwargs)
    return LLMCallResult(content=None, tool_calls=[_tool_call("call_f", "finalize_resolution", **defaults)], model="gpt-4o-mini")


def _candidate(**kwargs):
    defaults = dict(task="x", raw_owner_mention=None, raw_due_mention=None, evidence_quote="q", evidence_utterance_ids=["u1"])
    defaults.update(kwargs)
    return Candidate(**defaults)


def test_immediate_finalize_with_no_lookups():
    fake = _SequentialFakeLLMClient([_finalize_result(owner="Marcus", tool="trello_task", task_text="Draft notes")])
    result = resolve(_candidate(), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake)
    assert result.unresolved is False
    assert result.owner == "Marcus"
    assert result.tool == "trello_task"
    assert result.tool_call_log == []


def test_lookup_participant_then_finalize():
    lookup_result = LLMCallResult(
        content=None, tool_calls=[_tool_call("call_1", "lookup_participant", name="Marcus")], model="gpt-4o-mini"
    )
    fake = _SequentialFakeLLMClient([lookup_result, _finalize_result(owner="Marcus")])

    result = resolve(_candidate(raw_owner_mention="Marcus"), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake)

    assert result.unresolved is False
    assert result.owner == "Marcus"
    assert len(result.tool_call_log) == 1
    assert result.tool_call_log[0].name == "lookup_participant"
    assert result.tool_call_log[0].output == {
        "found": True, "name": "Marcus", "aliases": [], "email": "marcus@example.com", "trello_member_id": "member_marcus",
    }
    # the tool result must be fed back into the conversation for the 2nd call
    second_call_messages = fake.calls[1]
    tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert json.loads(tool_messages[0]["content"])["found"] is True


def test_lookup_participant_not_found():
    lookup_result = LLMCallResult(
        content=None, tool_calls=[_tool_call("call_1", "lookup_participant", name="Nobody")], model="gpt-4o-mini"
    )
    fake = _SequentialFakeLLMClient([lookup_result, _finalize_result(owner=None)])
    result = resolve(_candidate(raw_owner_mention="Nobody"), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake)
    assert result.tool_call_log[0].output == {"found": False}
    assert result.owner is None


def test_resolve_date_tool_call():
    date_result = LLMCallResult(
        content=None, tool_calls=[_tool_call("call_1", "resolve_date", expression="Friday")], model="gpt-4o-mini"
    )
    fake = _SequentialFakeLLMClient([date_result, _finalize_result(due="2026-09-04")])
    result = resolve(_candidate(raw_due_mention="Friday"), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake)
    assert result.tool_call_log[0].output == {"resolved_date": "2026-09-04"}
    assert result.due == "2026-09-04"


def test_resolve_date_ambiguous_returns_none_with_reason():
    date_result = LLMCallResult(
        content=None, tool_calls=[_tool_call("call_1", "resolve_date", expression="next week")], model="gpt-4o-mini"
    )
    fake = _SequentialFakeLLMClient([date_result, _finalize_result(due=None)])
    result = resolve(_candidate(raw_due_mention="next week"), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake)
    assert result.tool_call_log[0].output == {"resolved_date": None, "reason": "ambiguous or unparseable"}
    assert result.due is None


def test_get_context_resolves_cross_turn_delegation():
    context_result = LLMCallResult(
        content=None,
        tool_calls=[_tool_call("call_1", "get_context", utterance_id="u2", window=1)],
        model="gpt-4o-mini",
    )
    fake = _SequentialFakeLLMClient([context_result, _finalize_result(owner="Priya")])
    result = resolve(
        _candidate(raw_owner_mention="someone", evidence_utterance_ids=["u2"]),
        "2026-09-02", ROSTER, UTTERANCES, llm_client=fake,
    )
    output = result.tool_call_log[0].output
    assert [u["id"] for u in output["utterances"]] == ["u1", "u2", "u3"]
    assert result.owner == "Priya"


def test_multiple_tool_calls_in_one_turn_are_all_executed():
    both_calls = LLMCallResult(
        content=None,
        tool_calls=[
            _tool_call("call_1", "lookup_participant", name="Marcus"),
            _tool_call("call_2", "resolve_date", expression="Friday"),
        ],
        model="gpt-4o-mini",
    )
    fake = _SequentialFakeLLMClient([both_calls, _finalize_result(owner="Marcus", due="2026-09-04")])
    result = resolve(_candidate(), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake)
    assert len(result.tool_call_log) == 2
    assert result.owner == "Marcus" and result.due == "2026-09-04"


def test_never_finalizing_within_max_iterations_is_unresolved():
    lookup_result = LLMCallResult(
        content=None, tool_calls=[_tool_call("call_1", "lookup_participant", name="Marcus")], model="gpt-4o-mini"
    )
    fake = _SequentialFakeLLMClient([lookup_result] * 3)
    result = resolve(_candidate(), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake, max_tool_iterations=3)
    assert result.unresolved is True
    assert "max_tool_iterations" in result.confidence_notes


def test_no_tool_calls_at_all_is_unresolved():
    fake = _SequentialFakeLLMClient([LLMCallResult(content="I don't know", tool_calls=[], model="gpt-4o-mini")])
    result = resolve(_candidate(), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake)
    assert result.unresolved is True


def test_repair_feedback_is_included_in_the_prompt():
    fake = _SequentialFakeLLMClient([_finalize_result(owner="Marcus")])
    resolve(
        _candidate(), "2026-09-02", ROSTER, UTTERANCES, llm_client=fake,
        repair_feedback="owner could not be determined",
    )
    first_call_messages = fake.calls[0]
    user_message = next(m for m in first_call_messages if m["role"] == "user")
    assert "owner could not be determined" in user_message["content"]


def test_email_resolution_receives_agenda_outside_short_candidate_quote():
    from pathlib import Path
    from agent.router import build_tool_args
    from agent.schema import ActionItem

    root = Path(__file__).resolve().parents[1]
    transcript = (root / "data/demo/arjun_google/gmail.txt").read_text()
    roster = Roster.from_file(root / "data/demo/arjun_google/roster.json")
    utterances = parse_transcript(transcript)
    quote = utterances[0].text.split(". The agenda")[0] + "."
    candidate = _candidate(task="Draft an email about the rehearsal agenda", raw_owner_mention="Arjun Ranjan",
                           evidence_quote=quote, evidence_utterance_ids=["u1"])
    assert "inspect verified tool outputs" not in quote
    body = "Here is the rehearsal agenda:\n- Review the transcript.\n- Demonstrate the approval step.\n- Inspect verified tool outputs."

    class ContextCheckingClient:
        def complete(self, messages, **kwargs):
            content = messages[1]["content"]
            assert "inspect verified tool outputs" in content
            assert "demonstrate the approval step" in content
            assert "untrusted source data" in content
            assert "actual recipient-facing email body" in messages[0]["content"]
            return _finalize_result(owner="Arjun Ranjan", tool="email_draft", due=None,
                task_text="Capstone demo rehearsal agenda", description=body,
                attendees_or_recipients=["arjunranjanwork@gmail.com"])

    resolved = resolve(candidate, "2026-11-03", roster, utterances, llm_client=ContextCheckingClient())
    item = ActionItem(id="email-1", transcript_id="email", task=resolved.task_text,
                      owner=resolved.owner, tool=resolved.tool, attendees_or_recipients=resolved.attendees_or_recipients)
    args = build_tool_args(item, resolved, roster)
    assert args["subject"] == "Capstone demo rehearsal agenda"
    assert args["body"] == body
