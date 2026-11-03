"""
agent/tools/mock_backend.py
------------------------------
In-memory fake Calendar, Trello, and Gmail-drafts backends for
`--tools mock`. Used by every automated test and by eval/run_eval.py —
never touches the network, never needs credentials.

These mocks are built to mirror the real APIs closely enough that the
router and verifier (step 4) can be written once against this interface
and swapped onto the live adapters in step 7 without changing their
logic:

  - every create_* call assigns a real-looking id and is fully
    read-back-able afterwards via the matching get_* (events.get / cards
    GET equivalents), so the verifier's "read it back and compare"
    step works identically against mock and live.
  - every create_* call takes an idempotency_key. A second create_* call
    using a key that already produced a committed object returns that
    SAME object instead of creating a new one. This is what guarantees
    the spec's "rerunning the same meeting must never create duplicate
    events or cards."
  - fault injection is PRE-PROGRAMMED per idempotency_key via
    set_fault_plan(), not randomized — so tests and the eval runner can
    deterministically exercise 429 / 503 / timeout / invalid_argument /
    expired_token / "created but response lost" and assert on the exact
    recovery behavior each should trigger.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from agent.tools.errors import (
    ExpiredAuthError,
    InvalidArgumentError,
    RateLimitError,
    ResponseLostError,
    ServiceUnavailableError,
    ToolTimeoutError,
)

# fault name (as used by set_fault_plan) -> exception raised for it
_FAULT_EXCEPTIONS = {
    "429": RateLimitError,
    "503": ServiceUnavailableError,
    "timeout": ToolTimeoutError,
    "invalid_argument": InvalidArgumentError,
    "expired_token": ExpiredAuthError,
    "lost_response": ResponseLostError,
}


@dataclass
class _Store:
    objects: dict = field(default_factory=dict)  # id -> record dict
    idempotency_index: dict = field(default_factory=dict)  # idem_key -> id
    fault_plans: dict = field(default_factory=dict)  # idem_key -> list[fault_name|None]
    id_counter: itertools.count = field(default_factory=lambda: itertools.count(1))


class MockToolBackend:
    """Generic create/read-back/idempotency/fault engine shared by
    MockCalendar, MockTrello, and MockGmailDrafts below. `id_prefix` only
    affects the cosmetic id string (e.g. "evt_3")."""

    def __init__(self, id_prefix: str):
        self._id_prefix = id_prefix
        self._store = _Store()

    # --- test / eval-runner control -----------------------------------
    def set_fault_plan(self, idempotency_key: str, faults: list[Optional[str]]) -> None:
        """Schedules faults for future create calls made with this exact
        idempotency_key. `faults` is consumed one entry per call, in
        order (e.g. ["429", "503", None] fails twice then succeeds on the
        3rd attempt). Once exhausted, calls succeed. Valid fault names:
        "429", "503", "timeout", "invalid_argument", "expired_token",
        "lost_response"."""
        self._store.fault_plans[idempotency_key] = list(faults)

    def reset(self) -> None:
        self._store = _Store()

    def all_objects(self) -> dict:
        """For test assertions: every object ever committed, by id."""
        return dict(self._store.objects)

    # --- shared create / get machinery ----------------------------------
    def _create(self, idempotency_key: str, payload: dict) -> dict:
        existing_id = self._store.idempotency_index.get(idempotency_key)
        if existing_id is not None:
            # Idempotent replay: never create a second object for a key
            # that already succeeded, regardless of any fault plan left.
            return self._store.objects[existing_id]

        fault = self._next_fault(idempotency_key)
        if fault is not None and fault != "lost_response":
            raise _FAULT_EXCEPTIONS[fault](
                f"{self._id_prefix}: simulated {fault} on create (idempotency_key={idempotency_key!r})"
            )

        new_id = f"{self._id_prefix}_{next(self._store.id_counter)}"
        record = {"id": new_id, **payload}
        self._store.objects[new_id] = record
        self._store.idempotency_index[idempotency_key] = new_id

        if fault == "lost_response":
            # The write above DID commit. Only the response back to the
            # caller is "lost" (e.g. a dropped connection after the server
            # finished). A caller that retries with the same idempotency
            # key will hit the branch above and get this same object back.
            raise ResponseLostError(
                f"{self._id_prefix}: simulated lost_response on create "
                f"(idempotency_key={idempotency_key!r}); object WAS committed server-side as {new_id}"
            )
        return record

    def _get(self, object_id: str) -> dict:
        try:
            return self._store.objects[object_id]
        except KeyError:
            raise InvalidArgumentError(f"{self._id_prefix}: no object with id={object_id!r}") from None

    def _next_fault(self, idempotency_key: str) -> Optional[str]:
        plan = self._store.fault_plans.get(idempotency_key)
        if not plan:
            return None
        return plan.pop(0)


class MockCalendar(MockToolBackend):
    """Fakes just enough of Google Calendar for this project: creating an
    event and reading it back (the real adapter's events.insert / events.get)."""

    def __init__(self):
        super().__init__(id_prefix="evt")

    def create_calendar_event(self, idempotency_key, title, start, end, attendees, description):
        if not title or not start or not end:
            raise InvalidArgumentError("create_calendar_event requires title, start, and end")
        return self._create(
            idempotency_key,
            {
                "title": title,
                "start": start,
                "end": end,
                "attendees": list(attendees or []),
                "description": description,
            },
        )

    def get_event(self, event_id):
        return self._get(event_id)


class MockTrello(MockToolBackend):
    """Fakes just enough of Trello for this project: creating a card and
    reading it back (the real adapter's POST /1/cards / GET /1/cards/{id})."""

    def __init__(self):
        super().__init__(id_prefix="card")

    def create_task(self, idempotency_key, title, assignee_member_id, due, list_id, description):
        if not title or not list_id:
            raise InvalidArgumentError("create_task requires title and list_id")
        return self._create(
            idempotency_key,
            {
                "title": title,
                "assignee_member_id": assignee_member_id,
                "due": due,
                "list_id": list_id,
                "description": description,
            },
        )

    def get_card(self, card_id):
        return self._get(card_id)


class MockGmailDrafts(MockToolBackend):
    """Stretch-goal tool. Drafts only — this mock never "sends" anything,
    matching the real adapter's scope limit from the spec (gmail.compose
    scope only, draft creation, never send)."""

    def __init__(self):
        super().__init__(id_prefix="draft")

    def create_email_draft(self, idempotency_key, to, subject, body):
        if not to or not subject:
            raise InvalidArgumentError("create_email_draft requires to and subject")
        return self._create(idempotency_key, {"to": list(to or []), "subject": subject, "body": body})

    def get_draft(self, draft_id):
        return self._get(draft_id)
