"""
baselines/b1_single_call.py
------------------------------
B1: a single-call LLM baseline. Per spec: "one tool-calling request with
the full transcript and the same tool schemas, same model as our agent,
temperature 0. No validator, no approval loop, no read-back, no retry.
Its tool calls run once against the same adapters."

One LLMClient.complete() call, with the whole transcript + roster +
meeting date in the prompt and agent/tool_schemas.TOOLS as the tool
list. Every tool call the model makes is executed exactly once against
whatever tool backend is passed in (the mock backend for this step; the
same call sites will work against the live step-7 adapters because both
expose the same method names/signatures). If a tool call raises, B1
records it as a failed execution and moves on — by design, it never
retries, never asks a human, and never reads anything back to check it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent.config import LLM_MODEL, LLM_TEMPERATURE
from agent.ingestion import Utterance, parse_transcript
from agent.llm import LLMClient, LLMCallResult
from agent.schema import ActionItem
from agent.tool_schemas import BOOKKEEPING_ARG_NAMES, DEFAULT_TRELLO_LIST_ID, TOOL_NAME_TO_CANONICAL, TOOLS

SYSTEM_PROMPT = f"""You are an assistant that reads a meeting transcript and creates \
follow-up actions by calling tools. Rules:
- Only act on concrete commitments ("X will do Y", "X needs to do Y"), never on \
  suggestions, questions, hypotheticals, negations, or already-completed actions.
- The owner of an action is the person who will actually DO it, which may differ \
  from whoever is speaking. For example, in "Priya: Marcus will schedule a demo", \
  the owner is Marcus, not Priya (the speaker).
- If someone's commitment is vague at first ("someone should...", "we must...") and \
  a specific person claims it in a nearby turn, that later turn's person is the \
  true owner — cite evidence_utterance_ids from both turns.
- Resolve relative dates ("next Friday", "before Friday's launch") into absolute \
  ISO-8601 dates using the meeting date provided. If a date is too vague to resolve \
  confidently (e.g. "next week" with no specific day), pass due=null rather than \
  guessing.
- Use the participant roster to resolve names/aliases to the right person's email \
  (calendar attendees / email recipients) or Trello member id (tasks). Never invent \
  an email address or member id that is not in the roster.
- Always pass list_id="{DEFAULT_TRELLO_LIST_ID}" for create_task.
- Use create_calendar_event for scheduling a meeting/call/demo, create_email_draft \
  for things that should be followed up by email, and create_task for everything \
  else that should be tracked as a to-do.
- If an action item's true owner cannot be determined from the transcript and \
  roster, skip it rather than guessing.
- For every tool call, set evidence_utterance_ids to the utterance id(s) (e.g. \
  "u3") that support it.
"""


@dataclass
class ExecutionRecord:
    """Behavior-metric bookkeeping for one tool call, kept separate from
    ActionItem (which is semantic-only — see agent/schema.py)."""

    index: int
    tool_name: str
    arguments: dict
    idempotency_key: str
    success: bool
    error: Optional[str] = None
    created_object: Optional[dict] = None


@dataclass
class B1Result:
    predictions: list[ActionItem]
    execution_log: list[ExecutionRecord]
    llm_call: LLMCallResult
    raw_tool_call_count: int = field(default=0)
    unparseable_tool_calls: list[dict] = field(default_factory=list)


def _roster_block(roster: list[dict]) -> str:
    lines = ["Participant roster (name | aliases | email | trello_member_id):"]
    for p in roster:
        aliases = ", ".join(p.get("aliases", []))
        lines.append(f"- {p['name']} | {aliases} | {p.get('email', '')} | {p.get('trello_member_id', '')}")
    return "\n".join(lines)


def _transcript_block(utterances: list[Utterance]) -> str:
    return "\n".join(f"{u.id}: {u.speaker}: {u.text}" for u in utterances)


def build_messages(transcript_text: str, meeting_date: str, roster: list[dict]) -> tuple[list[dict], list[Utterance]]:
    utterances = parse_transcript(transcript_text)
    user_content = (
        f"Meeting date: {meeting_date}\n\n"
        f"{_roster_block(roster)}\n\n"
        "Transcript (utterance id: speaker: text):\n"
        f"{_transcript_block(utterances)}\n\n"
        "Create the appropriate tool call for every real action item you find."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    return messages, utterances


def _idempotency_key(transcript_id: str, index: int) -> str:
    return hashlib.sha256(f"{transcript_id}:{index}".encode()).hexdigest()[:16]


def _execute_tool_call(tools: dict, name: str, args: dict, idempotency_key: str) -> dict:
    """Calls the right backend method with the exact real-API argument
    shape (bookkeeping args already stripped by the caller). Raises
    whatever the backend raises — B1 does not catch/retry here, the
    caller does, by design (no recovery logic in B1)."""
    if name == "create_calendar_event":
        return tools["calendar"].create_calendar_event(idempotency_key, **args)
    if name == "create_task":
        return tools["trello"].create_task(idempotency_key, **args)
    if name == "create_email_draft":
        return tools["gmail"].create_email_draft(idempotency_key, **args)
    raise ValueError(f"Unknown tool name from model: {name!r}")


def _task_text_from_args(name: str, args: dict) -> str:
    """ActionItem.task requires non-empty text (agent/schema.py). The model
    is instructed to always fill title/subject, but a failed tool call
    (e.g. the model emitted an empty title, which the backend rejected)
    must still produce a valid, non-empty ActionItem so the failure is
    visible in predictions/execution_log instead of silently vanishing
    behind a pydantic ValidationError."""
    primary = args.get("subject") if name == "create_email_draft" else args.get("title")
    if primary:
        return primary
    fallback = args.get("description") or args.get("body")
    if fallback:
        return fallback
    return f"(empty title/subject from model for {name})"


def _recipients_from_args(name: str, args: dict) -> list[str]:
    if name == "create_calendar_event":
        return list(args.get("attendees") or [])
    if name == "create_email_draft":
        return list(args.get("to") or [])
    return []


def run_b1(
    transcript_text: str,
    meeting_date: str,
    roster: list[dict],
    tools: dict,
    transcript_id: str,
    llm_client: Any = None,
) -> B1Result:
    """`tools` must provide tools["calendar"].create_calendar_event(...),
    tools["trello"].create_task(...), tools["gmail"].create_email_draft(...)
    — the mock backends from agent/tools/mock_backend.py satisfy this, and
    so will the live step-7 adapters."""
    messages, _utterances = build_messages(transcript_text, meeting_date, roster)
    client = llm_client or LLMClient(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    llm_result = client.complete(messages=messages, tools=TOOLS)

    predictions: list[ActionItem] = []
    execution_log: list[ExecutionRecord] = []
    unparseable: list[dict] = []

    for idx, tc in enumerate(llm_result.tool_calls, start=1):
        name = tc["name"]
        try:
            full_args = json.loads(tc["arguments"])
        except json.JSONDecodeError as exc:
            unparseable.append({**tc, "parse_error": str(exc)})
            continue

        owner = full_args.get("owner")
        evidence = full_args.get("evidence_utterance_ids") or []
        api_args = {k: v for k, v in full_args.items() if k not in BOOKKEEPING_ARG_NAMES}
        idem_key = _idempotency_key(transcript_id, idx)
        canonical_tool = TOOL_NAME_TO_CANONICAL.get(name)

        try:
            record = _execute_tool_call(tools, name, api_args, idem_key)
        except Exception as exc:  # noqa: BLE001 — B1 has no retry/recovery by design
            execution_log.append(
                ExecutionRecord(
                    index=idx, tool_name=name, arguments=api_args, idempotency_key=idem_key,
                    success=False, error=f"{type(exc).__name__}: {exc}",
                )
            )
            predictions.append(
                ActionItem(
                    id=f"{transcript_id}-b1-{idx}",
                    transcript_id=transcript_id,
                    task=_task_text_from_args(name, api_args),
                    owner=owner,
                    tool=canonical_tool,
                    due=api_args.get("due"),
                    attendees_or_recipients=_recipients_from_args(name, api_args),
                    evidence_utterance_ids=evidence,
                )
            )
            continue

        execution_log.append(
            ExecutionRecord(
                index=idx, tool_name=name, arguments=api_args, idempotency_key=idem_key,
                success=True, created_object=record,
            )
        )
        predictions.append(
            ActionItem(
                id=f"{transcript_id}-b1-{idx}",
                transcript_id=transcript_id,
                task=_task_text_from_args(name, api_args),
                owner=owner,
                tool=canonical_tool,
                due=record.get("due"),
                attendees_or_recipients=_recipients_from_args(name, api_args),
                evidence_utterance_ids=evidence,
            )
        )

    return B1Result(
        predictions=predictions,
        execution_log=execution_log,
        llm_call=llm_result,
        raw_tool_call_count=len(llm_result.tool_calls),
        unparseable_tool_calls=unparseable,
    )


def run_b1_on_transcript(
    transcript_path: str | Path,
    roster_path: str | Path,
    meeting_date: str,
    tools: dict,
    transcript_id: Optional[str] = None,
    llm_client: Any = None,
) -> B1Result:
    path = Path(transcript_path)
    transcript_text = path.read_text(encoding="utf-8")
    roster = json.loads(Path(roster_path).read_text(encoding="utf-8"))
    transcript_id = transcript_id or path.stem
    return run_b1(transcript_text, meeting_date, roster, tools, transcript_id, llm_client)


if __name__ == "__main__":
    import argparse

    from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello

    parser = argparse.ArgumentParser(description="Run B1 (single-call LLM baseline) against mock tool backends.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--roster", required=True)
    parser.add_argument("--meeting-date", required=True)
    parser.add_argument("--transcript-id", default=None)
    args = parser.parse_args()

    mock_tools = {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}
    result = run_b1_on_transcript(args.input, args.roster, args.meeting_date, mock_tools, args.transcript_id)

    print(json.dumps([p.model_dump() for p in result.predictions], indent=2))
    print(f"\n--- execution log ({len(result.execution_log)} tool calls) ---")
    for rec in result.execution_log:
        status = "OK" if rec.success else f"FAILED: {rec.error}"
        print(f"[{rec.index}] {rec.tool_name} -> {status}")
    print(f"\nLLM: model={result.llm_call.model} tokens_in={result.llm_call.input_tokens} "
          f"tokens_out={result.llm_call.output_tokens} cost_usd={result.llm_call.cost_usd} "
          f"latency_s={round(result.llm_call.latency_seconds, 2)}")
