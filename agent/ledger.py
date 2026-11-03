"""
agent/ledger.py
-----------------
The action ledger: one SQLite row per candidate action item, tracking it
through proposed -> resolved -> validated -> approved -> executed ->
verified | escalated | rejected (spec's state machine), plus retry
counters and tool results.

Why SQLite, and why persisted to a file by default (not :memory:): the
spec requires "rerunning the same meeting must never create duplicate
events or cards." The primary guarantee is the tool backend's own
idempotency-key dedup (agent/tools/mock_backend.py), but that only helps
if a RETRY actually reuses the same idempotency key. A persisted ledger
lets the orchestrator recognize "this exact action item already reached
EXECUTED/VERIFIED last time" and skip re-running that item's resolver/
validator/router/verifier stages entirely on a re-run — a second,
independent line of defense, not just a cache.

Action ids are deterministic: f"{meeting_id}-{extraction_index}". This
is what lets a re-run line a prior run's rows up with this run's
candidates (same transcript + temperature 0 extraction is *usually*
stable in ordering, though LLMs are not perfectly deterministic even at
temperature 0 — this is a best-effort guarantee, documented here rather
than overclaimed).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# --- states -----------------------------------------------------------
PROPOSED = "proposed"
RESOLVED = "resolved"
VALIDATED = "validated"
APPROVED = "approved"
EXECUTED = "executed"
VERIFIED = "verified"
ESCALATED = "escalated"
REJECTED = "rejected"

TERMINAL_SUCCESS_STATES = {VERIFIED}
TERMINAL_STATES = {VERIFIED, ESCALATED, REJECTED}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    state TEXT NOT NULL,

    task TEXT,
    raw_owner_text TEXT,
    raw_due_text TEXT,
    evidence_quote TEXT,
    evidence_utterance_ids TEXT,   -- JSON array

    owner TEXT,
    due TEXT,
    tool TEXT,
    attendees_or_recipients TEXT,  -- JSON array

    validation_errors TEXT,        -- JSON array
    repair_attempts INTEGER NOT NULL DEFAULT 0,

    approval_decision TEXT,        -- 'approved' | 'edited' | 'rejected'
    auto_approved INTEGER NOT NULL DEFAULT 0,

    idempotency_key TEXT,
    execution_attempts INTEGER NOT NULL DEFAULT 0,
    execution_error TEXT,
    created_object TEXT,           -- JSON, the tool backend's record

    verified INTEGER,
    escalation_reason TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> Optional[str]:
    return None if value is None else json.dumps(value)


def _loads(value: Optional[str], default: Any) -> Any:
    return default if value is None else json.loads(value)


@dataclass
class ActionRecord:
    """A read-only snapshot of one ledger row."""

    id: str
    meeting_id: str
    state: str
    task: Optional[str]
    raw_owner_text: Optional[str]
    raw_due_text: Optional[str]
    evidence_quote: Optional[str]
    evidence_utterance_ids: list[str]
    owner: Optional[str]
    due: Optional[str]
    tool: Optional[str]
    attendees_or_recipients: list[str]
    validation_errors: list[str]
    repair_attempts: int
    approval_decision: Optional[str]
    auto_approved: bool
    idempotency_key: Optional[str]
    execution_attempts: int
    execution_error: Optional[str]
    created_object: Optional[dict]
    verified: Optional[bool]
    escalation_reason: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> "ActionRecord":
        return cls(
            id=row["id"],
            meeting_id=row["meeting_id"],
            state=row["state"],
            task=row["task"],
            raw_owner_text=row["raw_owner_text"],
            raw_due_text=row["raw_due_text"],
            evidence_quote=row["evidence_quote"],
            evidence_utterance_ids=_loads(row["evidence_utterance_ids"], []),
            owner=row["owner"],
            due=row["due"],
            tool=row["tool"],
            attendees_or_recipients=_loads(row["attendees_or_recipients"], []),
            validation_errors=_loads(row["validation_errors"], []),
            repair_attempts=row["repair_attempts"],
            approval_decision=row["approval_decision"],
            auto_approved=bool(row["auto_approved"]),
            idempotency_key=row["idempotency_key"],
            execution_attempts=row["execution_attempts"],
            execution_error=row["execution_error"],
            created_object=_loads(row["created_object"], None),
            verified=None if row["verified"] is None else bool(row["verified"]),
            escalation_reason=row["escalation_reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class Ledger:
    def __init__(self, db_path: str | Path = ":memory:"):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        with closing(self._conn.cursor()) as cur:
            cur.execute(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- creation / lookup ---------------------------------------------
    def action_id(self, meeting_id: str, extraction_index: int) -> str:
        return f"{meeting_id}-{extraction_index}"

    def propose(
        self,
        meeting_id: str,
        extraction_index: int,
        task: str,
        raw_owner_text: Optional[str],
        raw_due_text: Optional[str],
        evidence_quote: str,
        evidence_utterance_ids: list[str],
    ) -> str:
        action_id = self.action_id(meeting_id, extraction_index)
        now = _now()
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """INSERT INTO action_items
                   (id, meeting_id, state, task, raw_owner_text, raw_due_text,
                    evidence_quote, evidence_utterance_ids, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       task=excluded.task, raw_owner_text=excluded.raw_owner_text,
                       raw_due_text=excluded.raw_due_text, evidence_quote=excluded.evidence_quote,
                       evidence_utterance_ids=excluded.evidence_utterance_ids, updated_at=excluded.updated_at
                   WHERE action_items.state = ?""",
                (
                    action_id, meeting_id, PROPOSED, task, raw_owner_text, raw_due_text,
                    evidence_quote, _dumps(evidence_utterance_ids), now, now, PROPOSED,
                ),
            )
        self._conn.commit()
        return action_id

    def get(self, action_id: str) -> Optional[ActionRecord]:
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT * FROM action_items WHERE id = ?", (action_id,))
            row = cur.fetchone()
        return ActionRecord._from_row(row) if row else None

    def list_for_meeting(self, meeting_id: str) -> list[ActionRecord]:
        with closing(self._conn.cursor()) as cur:
            cur.execute("SELECT * FROM action_items WHERE meeting_id = ? ORDER BY id", (meeting_id,))
            rows = cur.fetchall()
        return [ActionRecord._from_row(r) for r in rows]

    # --- internal update helper -----------------------------------------
    def _update(self, action_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = _now()
        columns = ", ".join(f"{k} = ?" for k in fields)
        with closing(self._conn.cursor()) as cur:
            cur.execute(f"UPDATE action_items SET {columns} WHERE id = ?", (*fields.values(), action_id))
        self._conn.commit()

    # --- stage transitions ----------------------------------------------
    def set_resolved(self, action_id: str, owner: Optional[str], due: Optional[str], tool: Optional[str],
                      attendees_or_recipients: list[str]) -> None:
        self._update(
            action_id, state=RESOLVED, owner=owner, due=due, tool=tool,
            attendees_or_recipients=_dumps(attendees_or_recipients),
        )

    def set_validation_result(self, action_id: str, errors: list[str]) -> None:
        state = VALIDATED if not errors else RESOLVED  # failed validation -> back for repair
        self._update(action_id, state=state, validation_errors=_dumps(errors))

    def increment_repair_attempt(self, action_id: str) -> int:
        record = self.get(action_id)
        attempts = (record.repair_attempts if record else 0) + 1
        self._update(action_id, repair_attempts=attempts)
        return attempts

    def escalate(self, action_id: str, reason: str) -> None:
        self._update(action_id, state=ESCALATED, escalation_reason=reason)

    def set_approval(self, action_id: str, decision: str, auto_approved: bool,
                      owner: Optional[str] = None, due: Optional[str] = None,
                      tool: Optional[str] = None, attendees_or_recipients: Optional[list[str]] = None) -> None:
        """decision: 'approved' | 'edited' | 'rejected'. For 'edited', pass the
        human's corrected fields — caller is responsible for re-validating
        before calling this with state APPROVED (edits go back through the
        validator per spec, so this method alone does not re-validate)."""
        if decision == "rejected":
            self._update(action_id, state=REJECTED, approval_decision=decision, auto_approved=int(auto_approved))
            return
        fields: dict[str, Any] = {"approval_decision": decision, "auto_approved": int(auto_approved)}
        if owner is not None:
            fields["owner"] = owner
        if due is not None or decision == "edited":
            fields["due"] = due
        if tool is not None:
            fields["tool"] = tool
        if attendees_or_recipients is not None:
            fields["attendees_or_recipients"] = _dumps(attendees_or_recipients)
        if decision == "approved":
            fields["state"] = APPROVED
        else:  # 'edited' goes back to RESOLVED so the validator re-checks the edited fields
            fields["state"] = RESOLVED
        self._update(action_id, **fields)

    def mark_approved_after_revalidation(self, action_id: str) -> None:
        self._update(action_id, state=APPROVED)

    def set_idempotency_key(self, action_id: str, key: str) -> None:
        self._update(action_id, idempotency_key=key)

    def record_execution_attempt(self, action_id: str, success: bool,
                                  created_object: Optional[dict] = None, error: Optional[str] = None) -> int:
        record = self.get(action_id)
        attempts = (record.execution_attempts if record else 0) + 1
        fields: dict[str, Any] = {"execution_attempts": attempts}
        if success:
            fields.update(state=EXECUTED, created_object=_dumps(created_object), execution_error=None)
        else:
            fields["execution_error"] = error
        self._update(action_id, **fields)
        return attempts

    def set_verified(self, action_id: str, verified: bool, error: Optional[str] = None) -> None:
        fields: dict[str, Any] = {"verified": int(verified)}
        if verified:
            fields["state"] = VERIFIED
        if error:
            fields["execution_error"] = error
        self._update(action_id, **fields)
