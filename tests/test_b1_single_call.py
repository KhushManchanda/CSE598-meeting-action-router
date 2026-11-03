"""
Tests for baselines/b1_single_call.py, driven by a FAKE LLMClient (no
real/paid API calls) so B1's tool-execution/schema-conversion logic is
tested deterministically, independent of actual model behavior.
"""

import json

import pytest

from agent.llm import LLMCallResult
from agent.tools.errors import InvalidArgumentError
from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello
from baselines.b1_single_call import run_b1


class _FakeLLMClient:
    """Returns a pre-built LLMCallResult regardless of the messages/tools
    passed in — lets tests drive run_b1()'s downstream logic exactly."""

    def __init__(self, result: LLMCallResult):
        self._result = result

    def complete(self, messages, tools=None, response_format=None):
        return self._result


def _tool_call(id_, name, **kwargs):
    return {"id": id_, "name": name, "arguments": json.dumps(kwargs)}


def _mock_tools():
    return {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}


ROSTER = [
    {"name": "Marcus", "aliases": [], "email": "marcus@example.com", "trello_member_id": "member_marcus"},
    {"name": "Priya", "aliases": [], "email": "priya@example.com", "trello_member_id": "member_priya"},
]


def test_single_successful_calendar_tool_call_becomes_one_prediction():
    tool_calls = [
        _tool_call(
            "call_1", "create_calendar_event",
            title="Demo with design team", start="2026-09-09T10:00:00", end="2026-09-09T10:30:00",
            attendees=["marcus@example.com"], description="demo",
            owner="Marcus", evidence_utterance_ids=["u3"],
        )
    ]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=tool_calls, model="gpt-4o-mini"))
    tools = _mock_tools()

    result = run_b1("transcript text", "2026-09-02", ROSTER, tools, "t1", llm_client=fake)

    assert len(result.predictions) == 1
    pred = result.predictions[0]
    assert pred.owner == "Marcus"
    assert pred.tool == "calendar_event"
    assert pred.evidence_utterance_ids == ["u3"]
    assert pred.attendees_or_recipients == ["marcus@example.com"]
    assert result.execution_log[0].success is True
    # bookkeeping args must never reach the mock backend's stored record
    created = next(iter(tools["calendar"].all_objects().values()))
    assert "owner" not in created and "evidence_utterance_ids" not in created


def test_task_and_email_tool_calls_map_to_canonical_tools_and_fields():
    tool_calls = [
        _tool_call(
            "call_1", "create_task",
            title="Draft release notes", assignee_member_id="member_marcus", due="2026-09-04",
            list_id="list_todo", description="release notes",
            owner="Marcus", evidence_utterance_ids=["u9", "u10"],
        ),
        _tool_call(
            "call_2", "create_email_draft",
            to=["legal@example.com"], subject="Vendor contract", body="...",
            owner="Priya", evidence_utterance_ids=["u6", "u7"],
        ),
    ]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=tool_calls, model="gpt-4o-mini"))
    tools = _mock_tools()

    result = run_b1("transcript text", "2026-09-02", ROSTER, tools, "t1", llm_client=fake)

    assert len(result.predictions) == 2
    task_pred, email_pred = result.predictions
    assert task_pred.tool == "trello_task"
    assert task_pred.owner == "Marcus"
    assert task_pred.due == "2026-09-04"
    assert email_pred.tool == "email_draft"
    assert email_pred.owner == "Priya"
    assert email_pred.attendees_or_recipients == ["legal@example.com"]
    assert all(rec.success for rec in result.execution_log)


def test_idempotency_key_is_derived_from_transcript_id_and_index_deterministically():
    tool_calls = [
        _tool_call(
            "call_1", "create_task",
            title="A", assignee_member_id="member_marcus", due=None, list_id="list_todo", description="x",
            owner="Marcus", evidence_utterance_ids=["u1"],
        )
    ]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=tool_calls, model="gpt-4o-mini"))

    result_a = run_b1("t", "2026-09-02", ROSTER, _mock_tools(), "t1", llm_client=fake)
    result_b = run_b1("t", "2026-09-02", ROSTER, _mock_tools(), "t1", llm_client=fake)

    assert result_a.execution_log[0].idempotency_key == result_b.execution_log[0].idempotency_key


def test_rerunning_same_transcript_against_same_backend_never_duplicates():
    tool_calls = [
        _tool_call(
            "call_1", "create_task",
            title="A", assignee_member_id="member_marcus", due=None, list_id="list_todo", description="x",
            owner="Marcus", evidence_utterance_ids=["u1"],
        )
    ]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=tool_calls, model="gpt-4o-mini"))
    tools = _mock_tools()  # SAME backend instance reused across both "runs"

    run_b1("t", "2026-09-02", ROSTER, tools, "t1", llm_client=fake)
    run_b1("t", "2026-09-02", ROSTER, tools, "t1", llm_client=fake)

    assert len(tools["trello"].all_objects()) == 1  # not 2


def test_tool_call_failure_is_recorded_but_does_not_crash_or_retry():
    tool_calls = [
        _tool_call(
            "call_1", "create_task",
            title="", assignee_member_id="member_marcus", due=None, list_id="list_todo", description="x",
            owner="Marcus", evidence_utterance_ids=["u1"],
        )  # empty title -> MockTrello raises InvalidArgumentError
    ]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=tool_calls, model="gpt-4o-mini"))
    tools = _mock_tools()

    result = run_b1("t", "2026-09-02", ROSTER, tools, "t1", llm_client=fake)

    assert len(result.predictions) == 1  # still reported as a semantic prediction
    assert result.execution_log[0].success is False
    assert "InvalidArgumentError" in result.execution_log[0].error
    assert len(tools["trello"].all_objects()) == 0  # nothing was actually created


def test_unparseable_tool_call_arguments_are_skipped_not_crashed_on():
    tool_calls = [{"id": "call_1", "name": "create_task", "arguments": "{not valid json"}]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=tool_calls, model="gpt-4o-mini"))

    result = run_b1("t", "2026-09-02", ROSTER, _mock_tools(), "t1", llm_client=fake)

    assert result.predictions == []
    assert len(result.unparseable_tool_calls) == 1


def test_no_tool_calls_means_no_predictions():
    fake = _FakeLLMClient(LLMCallResult(content="No action items found.", tool_calls=[], model="gpt-4o-mini"))
    result = run_b1("t", "2026-09-02", ROSTER, _mock_tools(), "t1", llm_client=fake)
    assert result.predictions == []
    assert result.raw_tool_call_count == 0
