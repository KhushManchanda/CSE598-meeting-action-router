"""
agent/orchestrator.py
------------------------
Ties every stage together into the full pipeline for one meeting:

  ingest -> extract -> [per candidate:
      resolve -> validate -> (repair loop, max 2 extra resolver calls)
      -> human approval (approve/edit/reject)
      -> execute + verify (retry/escalate per agent/verifier.py)
  ] -> report

Budget: max 40 tool calls per meeting (spec). Counts real execution
attempts (agent/verifier.py's internal retries count too -- each is a
real call against the backend). Once exhausted, remaining approved-but-
not-yet-executed items are escalated, never silently dropped.

Rerun safety: if `ledger` is a persisted Ledger (not the default
in-memory one) and this meeting_id was already run against it, any
candidate whose action_id already reached a TERMINAL state (verified/
escalated/rejected) is skipped entirely rather than re-resolved/
re-approved/re-executed -- see agent/ledger.py's module docstring for
why this, plus idempotency keys, is what satisfies "rerunning a
meeting must never create duplicate events or cards."
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from agent import ledger as ledger_module
from agent.approval_cli import review_item
from agent.audit import AuditLog
from agent.extractor import extract
from agent.ingestion import parse_transcript
from agent.ledger import Ledger
from agent.participants import Roster
from agent.resolver import ResolvedAction, resolve
from agent.router import idempotency_key
from agent.validator import validate
from agent.verifier import execute_with_recovery

MAX_REPAIR_ATTEMPTS = 2
DEFAULT_BUDGET = 40


@dataclass
class RunReport:
    meeting_id: str
    verified: list[dict] = field(default_factory=list)
    escalated: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    skipped_already_done: list[dict] = field(default_factory=list)
    budget_exhausted_remaining: list[str] = field(default_factory=list)
    tool_calls_used: int = 0
    total_cost_usd: float = 0.0

    def summary_text(self) -> str:
        lines = [
            f"Meeting: {self.meeting_id}",
            f"  Verified:  {len(self.verified)}",
            f"  Escalated: {len(self.escalated)}",
            f"  Rejected:  {len(self.rejected)}",
            f"  Skipped (already done in a prior run): {len(self.skipped_already_done)}",
            f"  Tool calls used: {self.tool_calls_used}",
            f"  Total LLM cost: ${self.total_cost_usd:.6f}",
        ]
        if self.budget_exhausted_remaining:
            lines.append(f"  BUDGET EXHAUSTED -- {len(self.budget_exhausted_remaining)} item(s) escalated unexecuted")
        return "\n".join(lines)

    def to_json(self) -> dict:
        return asdict(self)


def write_report(report: RunReport, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_json(), indent=2, default=str), encoding="utf-8")


def _resolved_action_from_item(item) -> ResolvedAction:
    """router/verifier need a ResolvedAction (for .description); after an
    edit, we only have the edited ActionItem -- description is lost on
    edit, which is an accepted, disclosed limitation of the approval
    CLI's edit flow (it edits owner/due/tool/task/recipients, not the
    longer description text)."""
    return ResolvedAction(
        owner=item.owner, tool=item.tool, task_text=item.task, description="",
        due=item.due, attendees_or_recipients=item.attendees_or_recipients,
        confidence_notes="", unresolved=False,
    )


def _apply_edits(item, edits: dict):
    return item.model_copy(update=edits) if edits else item


def _resolve_validate_with_repair(
    candidate, meeting_date, roster, utterances, transcript_text, ledger, action_id,
    audit_log, meeting_id, llm_client, report, max_repair_attempts=MAX_REPAIR_ATTEMPTS,
):
    repair_feedback: Optional[str] = None
    for attempt in range(max_repair_attempts + 1):
        resolved_action = resolve(candidate, meeting_date, roster, utterances, llm_client=llm_client, repair_feedback=repair_feedback)
        for llm_call in resolved_action.llm_calls:
            audit_log.log_model_call(meeting_id, action_id, "resolver", llm_call)
            report.total_cost_usd += llm_call.cost_usd or 0.0

        ledger.set_resolved(action_id, resolved_action.owner, resolved_action.due, resolved_action.tool, resolved_action.attendees_or_recipients)

        validation = validate(candidate, resolved_action, meeting_date, roster, transcript_text, llm_client=llm_client)
        if validation.grounding_llm_call is not None:
            audit_log.log_model_call(meeting_id, action_id, "validator_grounding", validation.grounding_llm_call)
            report.total_cost_usd += validation.grounding_llm_call.cost_usd or 0.0

        ledger.set_validation_result(action_id, validation.errors)

        if validation.passed:
            resolved_item = validation.resolved_item.model_copy(update={"id": action_id, "transcript_id": meeting_id})
            return resolved_item, resolved_action

        if attempt < max_repair_attempts:
            ledger.increment_repair_attempt(action_id)
            repair_feedback = "; ".join(validation.errors)
            audit_log.log_decision(meeting_id, action_id, "validator", "repair_requested", {"errors": validation.errors, "attempt": attempt + 1})
        else:
            ledger.escalate(action_id, f"validation failed after {max_repair_attempts} repair attempts: {validation.errors}")
            audit_log.log_decision(meeting_id, action_id, "validator", "escalated", {"errors": validation.errors})
            report.escalated.append({"id": action_id, "reason": validation.errors})

    return None, None


def _append_existing_to_report(report: RunReport, record) -> None:
    report.skipped_already_done.append({"id": record.id, "state": record.state, "task": record.task})
    if record.state == ledger_module.VERIFIED:
        report.verified.append({"id": record.id, "task": record.task, "created_object": record.created_object})
    elif record.state == ledger_module.ESCALATED:
        report.escalated.append({"id": record.id, "reason": record.escalation_reason})
    elif record.state == ledger_module.REJECTED:
        report.rejected.append({"id": record.id, "task": record.task})


def run_meeting(
    transcript_text: str,
    meeting_date: str,
    roster: Roster,
    tools: dict,
    meeting_id: str,
    ledger: Optional[Ledger] = None,
    audit_log: Optional[AuditLog] = None,
    llm_client: Any = None,
    auto_approve: bool = False,
    budget: int = DEFAULT_BUDGET,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> RunReport:
    own_ledger = ledger is None
    ledger = ledger or Ledger(":memory:")
    own_audit = audit_log is None
    audit_log = audit_log or AuditLog(f"runs/{meeting_id}_audit.jsonl")

    utterances = parse_transcript(transcript_text)
    report = RunReport(meeting_id=meeting_id)

    try:
        extraction = extract(transcript_text, llm_client=llm_client)
        audit_log.log_model_call(meeting_id, None, "extractor", extraction.llm_call)
        report.total_cost_usd += extraction.llm_call.cost_usd or 0.0

        for idx, candidate in enumerate(extraction.candidates, start=1):
            action_id = ledger.action_id(meeting_id, idx)
            existing = ledger.get(action_id)
            if existing is not None and existing.state in ledger_module.TERMINAL_STATES:
                _append_existing_to_report(report, existing)
                continue

            ledger.propose(
                meeting_id, idx, candidate.task, candidate.raw_owner_mention, candidate.raw_due_mention,
                candidate.evidence_quote, candidate.evidence_utterance_ids,
            )

            resolved_item, resolved_action = _resolve_validate_with_repair(
                candidate, meeting_date, roster, utterances, transcript_text, ledger, action_id,
                audit_log, meeting_id, llm_client, report,
            )
            if resolved_item is None:
                continue  # escalated inside the repair loop

            decision = review_item(resolved_item, resolved_action, auto_approve=auto_approve, input_fn=input_fn, print_fn=print_fn)
            audit_log.log_decision(meeting_id, action_id, "approval", decision.decision, {"auto_approved": decision.auto_approved})

            if decision.decision == "rejected":
                ledger.set_approval(action_id, "rejected", decision.auto_approved)
                report.rejected.append({"id": action_id, "task": resolved_item.task})
                continue

            if decision.decision == "edited":
                resolved_item = _apply_edits(resolved_item, decision.edits)
                ledger.set_approval(
                    action_id, "edited", decision.auto_approved, owner=resolved_item.owner, due=resolved_item.due,
                    tool=resolved_item.tool, attendees_or_recipients=resolved_item.attendees_or_recipients,
                )
                revalidation = validate(
                    candidate, _resolved_action_from_item(resolved_item), meeting_date, roster, transcript_text,
                    llm_client=llm_client, run_grounding_check=False,
                )
                ledger.set_validation_result(action_id, revalidation.errors)
                if not revalidation.passed:
                    ledger.escalate(action_id, f"edited item failed re-validation: {revalidation.errors}")
                    report.escalated.append({"id": action_id, "reason": revalidation.errors})
                    continue
                ledger.mark_approved_after_revalidation(action_id)
            else:
                ledger.set_approval(action_id, "approved", decision.auto_approved)

            if report.tool_calls_used >= budget:
                ledger.escalate(action_id, "budget exhausted (max tool calls per meeting reached)")
                report.budget_exhausted_remaining.append(action_id)
                continue

            idem_key = idempotency_key(meeting_id, action_id)
            ledger.set_idempotency_key(action_id, idem_key)
            resolved_action_for_router = resolved_action if decision.decision != "edited" else _resolved_action_from_item(resolved_item)
            outcome = execute_with_recovery(resolved_item, resolved_action_for_router, roster, tools, idem_key)
            report.tool_calls_used += outcome.attempts

            ledger.record_execution_attempt(action_id, success=outcome.verified, created_object=outcome.created_object, error=outcome.error)
            audit_log.log_tool_call(
                meeting_id, action_id, "router", resolved_item.tool, {}, idem_key,
                success=outcome.verified, result=outcome.created_object, error=outcome.error,
            )

            if outcome.outcome == "verified":
                ledger.set_verified(action_id, True)
                report.verified.append({"id": action_id, "task": resolved_item.task, "created_object": outcome.created_object})
            else:
                reason = outcome.error or "verification failed"
                ledger.escalate(action_id, reason)
                report.escalated.append({"id": action_id, "reason": reason})

        return report
    finally:
        if own_audit:
            audit_log.close()
        if own_ledger:
            ledger.close()
