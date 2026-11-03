"""
agent/verifier.py
--------------------
Verifier. Per spec: "read the created object back (Calendar events.get,
Trello GET /1/cards/{id}) and compare it to what we intended. Retry
transient errors (429, 5xx, timeout) with backoff using the same
idempotency key, max 3 times. Send invalid-argument errors back to the
resolver. Send expired auth or an exhausted budget to manual review."

(Budget exhaustion is enforced by agent/orchestrator.py before this
module is ever called for a given item -- this module only handles the
per-call error types above.)

Retry reuses the SAME idempotency_key on every attempt, which is what
makes the "created but response lost" fault safe to retry: the mock
backend's idempotency check (agent/tools/mock_backend.py) means a retry
either creates the object once or recovers the one that already exists
-- never a duplicate.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from agent.router import build_tool_args, call_tool
from agent.tools.errors import TRANSIENT_ERRORS, ExpiredAuthError, InvalidArgumentError

MAX_RETRIES = 3


@dataclass
class VerifyOutcome:
    verified: bool
    outcome: str  # "verified" | "needs_resolver_repair" | "escalate"
    created_object: Optional[dict] = None
    error: Optional[str] = None
    attempts: int = 0
    mismatches: list[str] = field(default_factory=list)


def _get_record(tool: str, tools: dict, object_id: str) -> dict:
    if tool == "calendar_event":
        return tools["calendar"].get_event(object_id)
    if tool == "trello_task":
        return tools["trello"].get_card(object_id)
    if tool == "email_draft":
        return tools["gmail"].get_draft(object_id)
    raise ValueError(f"Unknown canonical tool: {tool!r}")


def _compare(intended_args: dict, created_object: dict) -> list[str]:
    mismatches = []
    for key, expected in intended_args.items():
        actual = created_object.get(key)
        if isinstance(expected, list):
            if set(expected) != set(actual or []):
                mismatches.append(f"{key}: expected {expected}, got {actual}")
        elif actual != expected:
            mismatches.append(f"{key}: expected {expected!r}, got {actual!r}")
    return mismatches


def execute_with_recovery(
    resolved_item,
    resolved_action,
    roster,
    tools: dict,
    idem_key: str,
    max_retries: int = MAX_RETRIES,
    sleep_fn: Callable[[float], None] = time.sleep,
    backoff_fn: Callable[[int], float] = lambda attempt: 0.5 * (2 ** (attempt - 1)),
) -> VerifyOutcome:
    tool = resolved_item.tool
    attempt = 0
    last_error: Optional[BaseException] = None

    while attempt < max_retries:
        attempt += 1
        try:
            # build_tool_args is deliberately INSIDE the try: it can raise
            # too (e.g. a calendar_event with due=None, which the validator
            # normally prevents from ever reaching here -- but A-noval
            # skips the validator, and this must escalate, not crash the
            # whole eval run, when that guarantee doesn't hold).
            args = build_tool_args(resolved_item, resolved_action, roster)
            created = call_tool(tool, args, tools, idem_key)
        except InvalidArgumentError as exc:
            return VerifyOutcome(verified=False, outcome="needs_resolver_repair", error=str(exc), attempts=attempt)
        except ExpiredAuthError as exc:
            return VerifyOutcome(verified=False, outcome="escalate", error=str(exc), attempts=attempt)
        except TRANSIENT_ERRORS as exc:
            last_error = exc
            if attempt < max_retries:
                sleep_fn(backoff_fn(attempt))
            continue
        except Exception as exc:  # unknown error type: escalate, never swallow silently
            return VerifyOutcome(
                verified=False, outcome="escalate", error=f"{type(exc).__name__}: {exc}", attempts=attempt
            )
        else:
            try:
                read_back = _get_record(tool, tools, created["id"])
            except Exception as exc:
                # A write may already exist. Preserve its identity and escalate;
                # never crash or retry creation just because reading failed.
                return VerifyOutcome(
                    verified=False, outcome="escalate", created_object=created,
                    error=f"read-back failed ({type(exc).__name__}): {exc}", attempts=attempt,
                )
            mismatches = _compare(args, read_back)
            if mismatches:
                return VerifyOutcome(
                    verified=False, outcome="escalate", created_object=read_back,
                    error="read-back did not match what was intended", mismatches=mismatches, attempts=attempt,
                )
            return VerifyOutcome(verified=True, outcome="verified", created_object=read_back, attempts=attempt)

    return VerifyOutcome(
        verified=False, outcome="escalate", attempts=attempt,
        error=f"transient error persisted after {max_retries} attempts: {last_error}",
    )
