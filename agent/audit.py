"""
agent/audit.py
-----------------
JSONL audit log: one line per event. Spec: "a JSONL audit log of every
model call, tool call, result, decision, token count and latency."
Append-only, one AuditLog per orchestrator run (agent/orchestrator.py).
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TextIO


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):  # pydantic model (e.g. ActionItem)
        return value.model_dump()
    return value


class AuditLog:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: TextIO = open(self._path, "a", encoding="utf-8")

    def close(self) -> None:
        self._fh.close()

    def _write(self, event: dict) -> None:
        self._fh.write(json.dumps(_jsonable(event), default=str) + "\n")
        self._fh.flush()

    def log_model_call(self, meeting_id: str, action_id: Optional[str], stage: str, llm_call_result) -> None:
        self._write(
            {
                "ts": _now(), "event": "model_call", "meeting_id": meeting_id, "action_id": action_id,
                "stage": stage, "model": llm_call_result.model, "input_tokens": llm_call_result.input_tokens,
                "output_tokens": llm_call_result.output_tokens, "latency_seconds": llm_call_result.latency_seconds,
                "cost_usd": llm_call_result.cost_usd,
                "tool_calls": [tc["name"] for tc in llm_call_result.tool_calls],
            }
        )

    def log_tool_call(
        self, meeting_id: str, action_id: str, stage: str, tool_name: str, args: dict,
        idempotency_key: str, success: bool, result: Optional[dict] = None, error: Optional[str] = None,
    ) -> None:
        self._write(
            {
                "ts": _now(), "event": "tool_call", "meeting_id": meeting_id, "action_id": action_id,
                "stage": stage, "tool_name": tool_name, "args": args, "idempotency_key": idempotency_key,
                "success": success, "result": result, "error": error,
            }
        )

    def log_decision(self, meeting_id: str, action_id: str, stage: str, decision: str, details: Optional[dict] = None) -> None:
        self._write(
            {
                "ts": _now(), "event": "decision", "meeting_id": meeting_id, "action_id": action_id,
                "stage": stage, "decision": decision, "details": details or {},
            }
        )
