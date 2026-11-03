#!/usr/bin/env python3
"""
run_agent.py
--------------
CLI entrypoint for Agent A (step 4's real system under test).

    python run_agent.py --input transcript.txt --roster roster.json \
        --meeting-date 2026-09-02 --meeting-id test1 --tools mock [--auto-approve]

--tools mock uses the in-memory fake Calendar/Trello/Gmail-drafts
(agent/tools/mock_backend.py) -- this is what every automated test and
eval run uses. --tools live (step 7) uses the real Google Calendar/
Gmail/Trello accounts connected via Composio -- see
agent/tools/composio_client.py's module docstring for one-time setup
(scripts/composio_connect.py, run once per toolkit, requires a human
to approve a browser consent screen) and
scripts/verify_composio_tools.py (run once before the first live
run). --tools live makes REAL writes to whatever account is connected
-- never run it against a production calendar/board.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

# Must run before any `agent.*` import: agent/config.py and
# agent/tool_schemas.py read os.environ at MODULE IMPORT time (not
# lazily), so .env has to be loaded first or those reads silently see
# nothing. python-dotenv has been in requirements.txt since step 1 but
# nothing ever actually called load_dotenv() -- every real run so far
# only worked because .env was sourced manually in the shell first.
load_dotenv()

from agent.audit import AuditLog  # noqa: E402
from agent.ledger import Ledger  # noqa: E402
from agent.orchestrator import run_meeting, write_report  # noqa: E402
from agent.participants import Roster  # noqa: E402
from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello  # noqa: E402


def _build_mock_tools() -> dict:
    return {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}


def _build_live_tools() -> dict:
    from agent.tools.live_calendar import LiveCalendar
    from agent.tools.live_gmail import LiveGmailDrafts
    from agent.tools.live_trello import LiveTrello

    return {"calendar": LiveCalendar(), "trello": LiveTrello(), "gmail": LiveGmailDrafts()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Agent A on one meeting transcript.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--roster", required=True)
    parser.add_argument("--meeting-date", required=True)
    parser.add_argument("--meeting-id", default=None)
    parser.add_argument("--tools", choices=["mock", "live"], default="mock")
    parser.add_argument(
        "--confirm-live", action="store_true",
        help="Required alongside --tools live, as an extra guard against accidentally writing to a real account.",
    )
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--budget", type=int, default=40)
    parser.add_argument("--ledger-path", default=None, help="Persist the ledger here (default: runs/<meeting_id>_ledger.sqlite3)")
    parser.add_argument("--report-path", default=None)
    args = parser.parse_args()

    if args.tools == "live" and not args.confirm_live:
        raise SystemExit(
            "--tools live makes REAL writes to whatever account scripts/composio_connect.py connected. "
            "Pass --confirm-live too if that's really what you want."
        )

    transcript_path = Path(args.input)
    meeting_id = args.meeting_id or transcript_path.stem
    transcript_text = transcript_path.read_text(encoding="utf-8")
    roster = Roster.from_file(args.roster)
    tools = _build_live_tools() if args.tools == "live" else _build_mock_tools()

    ledger_path = args.ledger_path or f"runs/{meeting_id}_ledger.sqlite3"
    report_path = args.report_path or f"runs/{meeting_id}_report.json"
    audit_path = f"runs/{meeting_id}_audit.jsonl"

    ledger = Ledger(ledger_path)
    audit_log = AuditLog(audit_path)

    report = run_meeting(
        transcript_text, args.meeting_date, roster, tools, meeting_id,
        ledger=ledger, audit_log=audit_log, auto_approve=args.auto_approve, budget=args.budget,
    )
    ledger.close()
    audit_log.close()

    write_report(report, report_path)
    print(report.summary_text())
    print(f"\nFull JSON report: {report_path}")
    print(f"Audit log: {audit_path}")
    print(f"Ledger: {ledger_path}")


if __name__ == "__main__":
    main()
