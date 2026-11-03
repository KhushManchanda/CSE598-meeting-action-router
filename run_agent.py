#!/usr/bin/env python3
"""
run_agent.py
--------------
CLI entrypoint for Agent A (step 4's real system under test).

    python run_agent.py --input transcript.txt --roster roster.json \
        --meeting-date 2026-09-02 --meeting-id test1 --tools mock [--auto-approve]

--tools mock uses the in-memory fake Calendar/Trello/Gmail-drafts
(agent/tools/mock_backend.py) -- this is what every automated test and
eval run uses. --tools live is step 7 (real Google Calendar/Trello/
Gmail adapters) -- the flag is accepted now so the CLI surface is
stable, but it raises rather than silently falling back to mock.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from agent.audit import AuditLog
from agent.ledger import Ledger
from agent.orchestrator import run_meeting, write_report
from agent.participants import Roster
from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello


def _build_mock_tools() -> dict:
    return {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Agent A on one meeting transcript.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--roster", required=True)
    parser.add_argument("--meeting-date", required=True)
    parser.add_argument("--meeting-id", default=None)
    parser.add_argument("--tools", choices=["mock", "live"], default="mock")
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--budget", type=int, default=40)
    parser.add_argument("--ledger-path", default=None, help="Persist the ledger here (default: runs/<meeting_id>_ledger.sqlite3)")
    parser.add_argument("--report-path", default=None)
    args = parser.parse_args()

    if args.tools == "live":
        raise NotImplementedError("--tools live is step 7 (real Calendar/Trello/Gmail adapters) -- not built yet.")

    transcript_path = Path(args.input)
    meeting_id = args.meeting_id or transcript_path.stem
    transcript_text = transcript_path.read_text(encoding="utf-8")
    roster = Roster.from_file(args.roster)
    tools = _build_mock_tools()

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
