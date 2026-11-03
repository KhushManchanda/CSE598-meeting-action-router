"""Thread-safe controller. Worker threads never call Streamlit APIs.

No dotenv loading at import or during offline runs. Configuration is read
only after an explicit in-app choice; key values are not persisted in runs.
"""
from __future__ import annotations

import copy
import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from agent.approval_cli import ApprovalDecision
from agent.audit import AuditLog
from agent.ingestion import evidence_context, parse_transcript
from agent.ledger import Ledger
from agent.orchestrator import run_meeting
from agent.participants import Roster
from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs" / "ui"
MODES = ("Offline walkthrough", "OpenAI + mock tools", "OpenAI + live tools")
CONFIG_NAMES = ("OPENAI_API_KEY", "LLM_MODEL", "COMPOSIO_API_KEY", "COMPOSIO_USER_ID", "TRELLO_LIST_ID")


def read_local_config(allowed: bool, path: Path | None = None) -> dict:
    if not allowed:
        raise PermissionError("Allow this app to read local configuration before starting an OpenAI run.")
    from dotenv import dotenv_values
    values = dotenv_values(path or ROOT / ".env", interpolate=False)
    return {key: values.get(key) or "" for key in CONFIG_NAMES}


def validate_roster(rows: list[dict]) -> list[dict]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("Add at least one participant to the roster.")
    used = set()
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Roster entries must be objects with a name and identity fields.")
        name = str(row.get("name") or "").strip()
        aliases = row.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [s.strip() for s in aliases.split(",") if s.strip()]
        if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
            raise ValueError("Aliases must be a list of names or comma-separated text.")
        aliases = list(dict.fromkeys(a.strip() for a in aliases if a.strip() and a.strip().casefold() != name.casefold()))
        if not name:
            raise ValueError("Every participant needs a name.")
        identities = [name.casefold()] + [a.casefold() for a in aliases]
        if used.intersection(identities):
            raise ValueError("Participant names and aliases must be unique.")
        used.update(identities)
        email = str(row.get("email") or "").strip()
        if email and (not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)):
            raise ValueError(f"Enter a valid email for {name}, or leave it blank for Trello-only work.")
        result.append({"name": name, "aliases": aliases, "email": email,
                       "trello_member_id": str(row.get("trello_member_id") or "").strip()})
    return result


@dataclass(frozen=True)
class RunRequest:
    title: str
    transcript: str
    meeting_date: str
    roster: list[dict]
    mode: str
    budget: int = 40


class RunCancelled(Exception):
    pass


class RunController:
    def __init__(self, request: RunRequest, config: dict | None = None, runs_dir: Path = RUNS,
                 llm_client=None, tools=None, review_timeout: float = 1800):
        if request.mode not in MODES:
            raise ValueError("Choose a supported run mode.")
        date.fromisoformat(request.meeting_date)
        if not request.title.strip() or not parse_transcript(request.transcript):
            raise ValueError("Add a meeting title and at least one Speaker: utterance line.")
        if len(request.transcript) > 100_000:
            raise ValueError("Keep a meeting transcript under 100,000 characters.")
        if not 1 <= request.budget <= 200:
            raise ValueError("Execution budget must be between 1 and 200.")
        roster = validate_roster(request.roster)
        if request.mode == MODES[0]:
            from ui.demo import TRANSCRIPT, ROSTER, MEETING_DATE
            if request.transcript != TRANSCRIPT or roster != ROSTER or request.meeting_date != MEETING_DATE:
                raise ValueError("The offline walkthrough uses its fixed transcript, date, and fictional roster.")
        self.request = RunRequest(request.title, request.transcript, request.meeting_date, roster, request.mode, request.budget)
        self._config = dict(config or {})
        if request.mode != MODES[0] and not self._config.get("OPENAI_API_KEY") and llm_client is None:
            raise ValueError("OPENAI_API_KEY is not configured in the local .env file.")
        if request.mode == MODES[2] and tools is None:
            if not self._config.get("COMPOSIO_API_KEY") or not self._config.get("TRELLO_LIST_ID"):
                raise ValueError("Live mode needs COMPOSIO_API_KEY and TRELLO_LIST_ID in local configuration.")
        self.id = "ui-" + uuid.uuid4().hex[:12]
        self.path = runs_dir / self.id
        self._condition = threading.Condition(threading.RLock())
        self._thread = None
        self._decision = None
        self._cancelled = False
        self._llm_client = llm_client
        self._tools = tools
        self.review_timeout = review_timeout
        self._state = {"id": self.id, "title": request.title, "mode": request.mode, "status": "ready",
            "stage": "Ready", "started_at": datetime.now(timezone.utc).isoformat(), "actions": [],
            "reviewed": {}, "pending": None, "events": [], "cost": 0.0, "tokens": 0, "model_calls": 0,
            "report": None, "error": None, "elapsed": 0.0}

    def _clean(self, value):
        if isinstance(value, str):
            for key in ("OPENAI_API_KEY", "COMPOSIO_API_KEY"):
                secret = self._config.get(key)
                if secret:
                    value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, dict):
            return {key: self._clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clean(item) for item in value]
        return value

    def snapshot(self):
        with self._condition:
            return self._clean(copy.deepcopy(self._state))

    def start(self):
        with self._condition:
            if self._thread is not None:
                return False  # Streamlit reruns must never dispatch a second worker.
            self.path.mkdir(parents=True, exist_ok=False)
            (self.path / "input.json").write_text(json.dumps(asdict(self.request), indent=2))
            self._state.update(status="running", stage="Extracting actions")
            self._thread = threading.Thread(target=self._run, daemon=True, name=self.id)
            self._thread.start()
            return True

    def _persist(self):
        state = self.snapshot()
        target = self.path / "state.json"
        temp = self.path / "state.tmp"
        temp.write_text(json.dumps(self._clean(state), indent=2, default=str))
        temp.replace(target)

    def _event(self, event):
        event = self._clean(event)
        with self._condition:
            self._state["events"].append(event)
            if event.get("event") == "model_call":
                self._state["cost"] += event.get("cost_usd") or 0
                self._state["tokens"] += (event.get("input_tokens") or 0) + (event.get("output_tokens") or 0)
                self._state["model_calls"] += 1

    def _check_cancelled(self):
        with self._condition:
            if self._cancelled:
                raise RunCancelled("Stopped before the next model call or approval.")

    def cancel(self):
        with self._condition:
            self._cancelled = True
            self._condition.notify_all()

    def _review(self, item, resolved):
        self._check_cancelled()
        source = evidence_context(parse_transcript(self.request.transcript), item.evidence_utterance_ids)
        pending = {**item.model_dump(), "description": resolved.description,
                   "notes": resolved.confidence_notes, "evidence": source}
        with self._condition:
            self._state.update(status="awaiting_review", stage="Your review", pending=pending)
            self._state["reviewed"][item.id] = pending
            self._condition.notify_all()
        self._persist()
        deadline = time.monotonic() + self.review_timeout
        with self._condition:
            while self._decision is None:
                if self._cancelled or time.monotonic() >= deadline:
                    raise RunCancelled("Review stopped or timed out; remaining actions were not executed.")
                self._condition.wait(timeout=min(1.0, max(0.01, deadline - time.monotonic())))
            decision = self._decision
            self._decision = None
            self._state.update(status="running", stage="Validating edits and executing", pending=None)
            return decision

    def submit(self, action_id: str, approve: bool, edits: dict | None = None):
        edits = edits or {}
        allowed = {"task", "owner", "due", "tool", "attendees_or_recipients", "description"}
        if set(edits) - allowed:
            raise ValueError("Unsupported action edit.")
        if edits.get("due"):
            date.fromisoformat(edits["due"])
        with self._condition:
            pending = self._state.get("pending")
            if not pending or pending["id"] != action_id or self._decision is not None:
                return False  # ignore stale/double-clicked submissions
            if approve:
                self._state["reviewed"][action_id] = {**pending, **edits}
            self._decision = ApprovalDecision("edited" if approve and edits else "approved" if approve else "rejected", False, edits)
            self._state["pending"] = None
            self._state.update(status="running", stage="Applying your decision")
            self._condition.notify_all()
            return True

    def _build_clients(self):
        if self.request.mode == MODES[0]:
            from ui.demo import WalkthroughClient
            return self._llm_client or WalkthroughClient(), self._tools or {
                "calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}
        from agent.llm import LLMClient
        from openai import OpenAI
        client = self._llm_client
        if client is None:
            client = LLMClient(model=self._config.get("LLM_MODEL") or "gpt-4o-mini")
            client._client = OpenAI(api_key=self._config["OPENAI_API_KEY"], max_retries=1, timeout=45)
        if self._tools is not None:
            return client, self._tools
        if self.request.mode == MODES[1]:
            return client, {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}
        from composio import Composio
        from agent.tools.live_calendar import LiveCalendar
        from agent.tools.live_gmail import LiveGmailDrafts
        from agent.tools.live_trello import LiveTrello
        composio = Composio(api_key=self._config["COMPOSIO_API_KEY"])
        user_id = self._config.get("COMPOSIO_USER_ID") or "meeting-action-router"
        # Adapter bookkeeping is app-owned run state, never an OAuth-token store.
        cache = self.path.parent / "adapter_state"
        return client, {
            "calendar": LiveCalendar(cache / "calendar.json", user_id, client=composio),
            "trello": LiveTrello(cache / "trello.json", user_id, client=composio,
                                  list_id=self._config["TRELLO_LIST_ID"]),
            "gmail": LiveGmailDrafts(cache / "gmail.json", user_id, client=composio),
        }

    def _run(self):
        started = time.monotonic()
        controller = self
        ledger = audit = None

        class ObservedLedger(Ledger):
            def refresh(self):
                with controller._condition:
                    controller._state["actions"] = [asdict(r) for r in self.list_for_meeting(controller.id)]

            def propose(self, *args, **kwargs):
                result = super().propose(*args, **kwargs)
                self.refresh()
                return result

            def _update(self, *args, **kwargs):
                super()._update(*args, **kwargs)
                self.refresh()

        class ObservedAudit(AuditLog):
            def _write(self, event):
                safe = controller._clean(event)
                super()._write(safe)
                controller._event(safe)

        class TrackedClient:
            def __init__(self, client):
                self.client = client

            def complete(self, *args, **kwargs):
                controller._check_cancelled()
                name = (kwargs.get("tool_choice") or {}).get("function", {}).get("name")
                stage = {"propose_action_items": "Extracting actions", "report_grounding": "Checking source evidence"}.get(name, "Resolving owner and details")
                with controller._condition:
                    controller._state["stage"] = stage
                return self.client.complete(*args, **kwargs)

        try:
            client, tools = self._build_clients()
            ledger = ObservedLedger(self.path / "ledger.sqlite3")
            audit = ObservedAudit(self.path / "audit.jsonl")
            self._persist()
            report = run_meeting(self.request.transcript, self.request.meeting_date, Roster(self.request.roster),
                tools, self.id, ledger=ledger, audit_log=audit, llm_client=TrackedClient(client),
                auto_approve=False, budget=self.request.budget, review_fn=self._review, print_fn=lambda text: None)
            safe_report = self._clean(report.to_json())
            (self.path / "report.json").write_text(json.dumps(safe_report, indent=2, default=str))
            with self._condition:
                self._state.update(status="complete", stage="Run complete", report=safe_report, pending=None)
        except RunCancelled as exc:
            with self._condition:
                self._state.update(status="stopped", stage="Stopped", error=str(exc), pending=None)
        except Exception as exc:
            # No raw provider error text is rendered. It may contain key material.
            with self._condition:
                self._state.update(status="failed", stage="Run stopped", pending=None,
                    error=f"{type(exc).__name__}: the run could not finish. Review completed objects before starting another live run.")
        finally:
            if ledger:
                ledger.refresh()
                ledger.close()
            if audit:
                audit.close()
            with self._condition:
                self._state["elapsed"] = round(time.monotonic() - started, 2)
                self._state = self._clean(self._state)
            self._persist()
            self._config.clear()


def load_history(runs_dir: Path = RUNS) -> list[dict]:
    items = []
    if runs_dir.exists():
        for path in runs_dir.glob("ui-*/state.json"):
            try:
                record = json.loads(path.read_text())
                if record.get("id") == path.parent.name:
                    items.append(record)
            except (OSError, ValueError):
                continue
    return sorted(items, key=lambda item: item.get("started_at", ""), reverse=True)
