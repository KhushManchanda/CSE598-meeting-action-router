"""
agent/approval_cli.py
------------------------
Human approval loop. Per spec: "CLI where the user can approve, edit
(goes back through the validator) or reject each item. Add an
--auto-approve flag for batch testing that is clearly logged."

Kept test-friendly by injecting input_fn/print_fn rather than calling
input()/print() directly -- tests drive it with canned input lists
instead of needing a real terminal; agent/orchestrator.py's CLI
entrypoint passes the real input()/print() (or rich's console.print).

Safety default: unrecognized input is treated as REJECT, never as a
silent approve -- an action with external side effects should never go
through on ambiguous human input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

EDITABLE_FIELDS = ("owner", "due", "tool", "task", "attendees_or_recipients")


@dataclass
class ApprovalDecision:
    decision: str  # "approved" | "edited" | "rejected"
    auto_approved: bool
    edits: dict = field(default_factory=dict)


def _render_item(resolved_item, resolved_action, print_fn: Callable[[str], None]) -> None:
    print_fn("-" * 60)
    print_fn(f"Action [{resolved_item.id}]: {resolved_item.task}")
    print_fn(f"  Owner: {resolved_item.owner}")
    print_fn(f"  Tool: {resolved_item.tool}")
    print_fn(f"  Due: {resolved_item.due}")
    print_fn(f"  Attendees/recipients: {resolved_item.attendees_or_recipients}")
    print_fn(f"  Evidence utterances: {resolved_item.evidence_utterance_ids}")
    if resolved_action is not None and getattr(resolved_action, "confidence_notes", None):
        print_fn(f"  Resolver notes: {resolved_action.confidence_notes}")


def review_item(
    resolved_item: Any,
    resolved_action: Any = None,
    auto_approve: bool = False,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> ApprovalDecision:
    if auto_approve:
        print_fn(f"[auto-approve] {resolved_item.id}: approved without human review (--auto-approve)")
        return ApprovalDecision(decision="approved", auto_approved=True)

    _render_item(resolved_item, resolved_action, print_fn)
    raw = input_fn("Approve / Edit / Reject? [a/e/r, default a]: ").strip().lower()

    if raw in ("", "a", "approve"):
        return ApprovalDecision(decision="approved", auto_approved=False)
    if raw in ("r", "reject"):
        return ApprovalDecision(decision="rejected", auto_approved=False)
    if raw in ("e", "edit"):
        print_fn(f"Editable fields: {', '.join(EDITABLE_FIELDS)}")
        edits: dict = {}
        while True:
            field_name = input_fn("Field to edit (blank to finish): ").strip()
            if not field_name:
                break
            if field_name not in EDITABLE_FIELDS:
                print_fn(f"Unknown field {field_name!r}, skipping.")
                continue
            new_value: Any = input_fn(f"New value for {field_name}: ").strip()
            if field_name == "attendees_or_recipients":
                new_value = [v.strip() for v in new_value.split(",") if v.strip()]
            edits[field_name] = new_value
        return ApprovalDecision(decision="edited", auto_approved=False, edits=edits)

    print_fn(f"Unrecognized input {raw!r} -- treating as reject (safe default).")
    return ApprovalDecision(decision="rejected", auto_approved=False)
