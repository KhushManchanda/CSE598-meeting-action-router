import json

from agent.extractor import extract
from agent.llm import LLMCallResult


class _FakeLLMClient:
    def __init__(self, result):
        self._result = result
        self.last_call = None

    def complete(self, messages, tools=None, tool_choice=None, response_format=None):
        self.last_call = {"messages": messages, "tools": tools, "tool_choice": tool_choice}
        return self._result


def _tool_call(candidates):
    return [{"id": "call_1", "name": "propose_action_items", "arguments": json.dumps({"candidates": candidates})}]


def test_extracts_candidates_with_all_fields():
    candidates_json = [
        {
            "task": "Schedule a demo with the design team",
            "raw_owner_mention": "Marcus",
            "raw_due_mention": "next week",
            "evidence_quote": "Marcus will schedule a demo with the design team next week.",
            "evidence_utterance_ids": ["u3"],
        }
    ]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=_tool_call(candidates_json), model="gpt-4o-mini"))

    result = extract("Priya: Great. Marcus will schedule a demo...", llm_client=fake)

    assert len(result.candidates) == 1
    c = result.candidates[0]
    assert c.raw_owner_mention == "Marcus"
    assert c.raw_due_mention == "next week"
    assert c.evidence_utterance_ids == ["u3"]


def test_multiple_candidates_from_one_call():
    candidates_json = [
        {"task": "A", "raw_owner_mention": "Marcus", "raw_due_mention": None, "evidence_quote": "q1", "evidence_utterance_ids": ["u1"]},
        {"task": "B", "raw_owner_mention": "Priya", "raw_due_mention": "Friday", "evidence_quote": "q2", "evidence_utterance_ids": ["u2"]},
    ]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=_tool_call(candidates_json), model="gpt-4o-mini"))

    result = extract("transcript", llm_client=fake)

    assert [c.task for c in result.candidates] == ["A", "B"]


def test_empty_candidates_array_means_no_action_items():
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=_tool_call([]), model="gpt-4o-mini"))
    result = extract("transcript", llm_client=fake)
    assert result.candidates == []


def test_no_tool_call_at_all_means_no_candidates():
    fake = _FakeLLMClient(LLMCallResult(content="nothing", tool_calls=[], model="gpt-4o-mini"))
    result = extract("transcript", llm_client=fake)
    assert result.candidates == []


def test_forces_the_propose_action_items_tool_choice():
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=_tool_call([]), model="gpt-4o-mini"))
    extract("transcript", llm_client=fake)
    assert fake.last_call["tool_choice"] == {"type": "function", "function": {"name": "propose_action_items"}}


def test_evidence_quote_defaults_to_empty_string_if_missing():
    candidates_json = [{"task": "A", "raw_owner_mention": None, "raw_due_mention": None, "evidence_utterance_ids": ["u1"]}]
    fake = _FakeLLMClient(LLMCallResult(content=None, tool_calls=_tool_call(candidates_json), model="gpt-4o-mini"))
    result = extract("transcript", llm_client=fake)
    assert result.candidates[0].evidence_quote == ""
