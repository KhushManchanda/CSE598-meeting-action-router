import json

from agent.audit import AuditLog
from agent.llm import LLMCallResult


def test_log_model_call_writes_expected_fields(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    result = LLMCallResult(
        content=None, tool_calls=[{"id": "c1", "name": "finalize_resolution", "arguments": "{}"}],
        model="gpt-4o-mini", input_tokens=100, output_tokens=20, latency_seconds=1.2, cost_usd=0.0001,
    )
    log.log_model_call("t1", "t1-1", "resolver", result)
    log.close()

    lines = [json.loads(l) for l in path.read_text().splitlines()]
    assert len(lines) == 1
    entry = lines[0]
    assert entry["event"] == "model_call"
    assert entry["meeting_id"] == "t1"
    assert entry["action_id"] == "t1-1"
    assert entry["stage"] == "resolver"
    assert entry["input_tokens"] == 100
    assert entry["output_tokens"] == 20
    assert entry["cost_usd"] == 0.0001
    assert entry["tool_calls"] == ["finalize_resolution"]
    assert "ts" in entry


def test_log_tool_call_writes_expected_fields(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.log_tool_call(
        "t1", "t1-1", "router", "create_task", {"title": "x"}, "idem-1",
        success=True, result={"id": "card_1"},
    )
    log.close()
    entry = json.loads(path.read_text().splitlines()[0])
    assert entry["event"] == "tool_call"
    assert entry["tool_name"] == "create_task"
    assert entry["success"] is True
    assert entry["result"] == {"id": "card_1"}
    assert entry["error"] is None


def test_log_decision_writes_expected_fields(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.log_decision("t1", "t1-1", "approval", "approved", {"auto_approved": True})
    log.close()
    entry = json.loads(path.read_text().splitlines()[0])
    assert entry["event"] == "decision"
    assert entry["decision"] == "approved"
    assert entry["details"] == {"auto_approved": True}


def test_multiple_events_append_as_separate_lines(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.log_decision("t1", "t1-1", "approval", "approved")
    log.log_decision("t1", "t1-2", "approval", "rejected")
    log.close()
    lines = path.read_text().splitlines()
    assert len(lines) == 2


def test_reopening_the_same_path_appends_not_overwrites(tmp_path):
    path = tmp_path / "audit.jsonl"
    log1 = AuditLog(path)
    log1.log_decision("t1", "t1-1", "approval", "approved")
    log1.close()

    log2 = AuditLog(path)
    log2.log_decision("t1", "t1-2", "approval", "rejected")
    log2.close()

    assert len(path.read_text().splitlines()) == 2


def test_pydantic_action_item_is_json_serialized_via_model_dump(tmp_path):
    from agent.schema import ActionItem

    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    item = ActionItem(id="t1-1", transcript_id="t1", task="x", owner="Marcus")
    log.log_decision("t1", "t1-1", "approval", "approved", {"item": item})
    log.close()
    entry = json.loads(path.read_text().splitlines()[0])
    assert entry["details"]["item"]["owner"] == "Marcus"
