"""
agent/resolver.py
--------------------
Resolver: for one extractor candidate, a ReAct-style tool-calling loop
where the model can call:
  lookup_participant(name)        -- agent/participants.py, roster lookup w/ aliases
  resolve_date(expression, ...)   -- agent/dates.py, deterministic parsing
  get_context(utterance_id, window) -- nearby turns, for pronouns/delegation
and must eventually call finalize_resolution(...) exactly once to report
the resolved owner, tool, due date, and routing fields.

Each lookup/resolve_date/get_context call is executed locally (never by
the model) and its result fed back as a "tool" message, standard
multi-turn tool-calling. The loop is capped (max_tool_iterations) -- if
the model never calls finalize_resolution, the candidate comes back
unresolved=True, which the orchestrator treats as a validation failure
(repair attempt, then escalate if still stuck), never as a silent drop.

Deliberate simplification, disclosed: for tool=calendar_event, no
transcript in this project's data states an exact meeting TIME (only a
day, sometimes not even that -- see data/gold/test1.NOTES.md on "next
week"). start_time is therefore optional; when a confident day IS
resolved but no time is stated, a fixed default (10:00, 30 minutes) is
applied by the caller (agent/router.py), not guessed here. When no
confident day is resolved either, start/end stay null, which the
validator correctly rejects -- intentionally, this is the same "don't
guess, escalate instead" policy applied to due dates generally.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.config import LLM_MODEL, LLM_TEMPERATURE
from agent.dates import resolve_date
from agent.ingestion import Utterance
from agent.llm import LLMCallResult, LLMClient
from agent.participants import Roster

MAX_TOOL_ITERATIONS = 6
DEFAULT_CONTEXT_WINDOW = 2

LOOKUP_PARTICIPANT_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_participant",
        "description": "Look up a person by name or alias in the meeting roster.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}

RESOLVE_DATE_TOOL = {
    "type": "function",
    "function": {
        "name": "resolve_date",
        "description": "Resolve a relative or absolute date expression into an ISO-8601 date, "
        "relative to the meeting date. Returns null if the expression is too vague to resolve "
        "confidently (e.g. a bare 'next week' with no specific day) -- do not guess if this happens.",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
            "additionalProperties": False,
        },
    },
}

GET_CONTEXT_TOOL = {
    "type": "function",
    "function": {
        "name": "get_context",
        "description": "Get the utterances surrounding a given utterance id, to resolve pronouns "
        "or check whether someone claims a vague commitment in a nearby turn.",
        "parameters": {
            "type": "object",
            "properties": {
                "utterance_id": {"type": "string"},
                "window": {"type": "integer", "description": "How many turns before/after to include."},
            },
            "required": ["utterance_id", "window"],
            "additionalProperties": False,
        },
    },
}

FINALIZE_RESOLUTION_TOOL = {
    "type": "function",
    "function": {
        "name": "finalize_resolution",
        "description": "Report the fully resolved action item. Call exactly once, after using "
        "lookup_participant/resolve_date/get_context as needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": ["string", "null"],
                    "description": "Resolved owner's name exactly as it appears in the roster "
                    "(as returned by lookup_participant), or null if it cannot be determined.",
                },
                "tool": {"type": "string", "enum": ["calendar_event", "trello_task", "email_draft"]},
                "task_text": {"type": "string", "description": "Final, clean title/subject for the action."},
                "description": {"type": "string", "description": "Longer description/body for the tool call."},
                "due": {
                    "type": ["string", "null"],
                    "description": "ISO-8601 date from resolve_date, or null if not confidently resolvable.",
                },
                "attendees_or_recipients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Resolved email addresses (from lookup_participant) of calendar "
                    "attendees or email recipients. Empty array for trello_task.",
                },
                "confidence_notes": {
                    "type": "string",
                    "description": "Brief note on anything uncertain -- helps the validator and human reviewer.",
                },
            },
            "required": [
                "owner", "tool", "task_text", "description", "due",
                "attendees_or_recipients", "confidence_notes",
            ],
            "additionalProperties": False,
        },
    },
}

RESOLVER_TOOLS = [LOOKUP_PARTICIPANT_TOOL, RESOLVE_DATE_TOOL, GET_CONTEXT_TOOL, FINALIZE_RESOLUTION_TOOL]

SYSTEM_PROMPT = """You resolve ONE candidate meeting action item into a concrete, routable \
action. Use lookup_participant, resolve_date, and get_context as needed, then call \
finalize_resolution exactly once. Rules:
- The owner is whoever will actually DO the action, which may differ from who raised it. \
  If the candidate's raw owner mention is vague ("someone", "we") or a pronoun, use \
  get_context on its evidence utterances to check whether a specific person claims it in \
  a nearby turn -- if so, that person is the true owner.
- Only report an owner that lookup_participant actually found in the roster. If no \
  candidate name resolves, set owner to null rather than guessing.
- Only call resolve_date if raw_due_mention is non-null. Trust its result; if it returns \
  null, set due to null in finalize_resolution rather than guessing a date yourself.
- Choose tool: calendar_event for scheduling a meeting/call/demo, email_draft for things \
  that should be followed up by email, trello_task for everything else to track as a to-do.
- attendees_or_recipients must only contain emails returned by lookup_participant -- never \
  invent one.
"""


@dataclass
class ToolCallLogEntry:
    name: str
    arguments: dict
    output: Any


@dataclass
class ResolvedAction:
    owner: Optional[str]
    tool: Optional[str]
    task_text: str
    description: str
    due: Optional[str]
    attendees_or_recipients: list[str]
    confidence_notes: str
    unresolved: bool
    tool_call_log: list[ToolCallLogEntry] = field(default_factory=list)
    llm_calls: list[LLMCallResult] = field(default_factory=list)


def _execute_tool(name: str, args: dict, meeting_date: str, roster: Roster, utterances: list[Utterance]) -> dict:
    if name == "lookup_participant":
        match = roster.lookup(args["name"])
        return {"found": True, **match} if match else {"found": False}
    if name == "resolve_date":
        resolved = resolve_date(args["expression"], meeting_date)
        return {"resolved_date": resolved} if resolved else {"resolved_date": None, "reason": "ambiguous or unparseable"}
    if name == "get_context":
        window = int(args.get("window", DEFAULT_CONTEXT_WINDOW))
        by_id = {u.id: idx for idx, u in enumerate(utterances)}
        center = by_id.get(args["utterance_id"])
        if center is None:
            return {"utterances": []}
        lo, hi = max(0, center - window), min(len(utterances), center + window + 1)
        return {"utterances": [{"id": u.id, "speaker": u.speaker, "text": u.text} for u in utterances[lo:hi]]}
    raise ValueError(f"Unknown resolver tool: {name!r}")


def _candidate_block(candidate) -> str:
    return (
        f"Candidate action item:\n"
        f"  task: {candidate.task}\n"
        f"  raw_owner_mention: {candidate.raw_owner_mention}\n"
        f"  raw_due_mention: {candidate.raw_due_mention}\n"
        f"  evidence_quote: {candidate.evidence_quote!r}\n"
        f"  evidence_utterance_ids: {candidate.evidence_utterance_ids}\n"
    )


def _roster_block(roster: Roster) -> str:
    lines = ["Participant roster (for reference; use lookup_participant to resolve names):"]
    for p in roster.all():
        lines.append(f"- {p['name']}")
    return "\n".join(lines)


def resolve(
    candidate,
    meeting_date: str,
    roster: Roster,
    utterances: list[Utterance],
    llm_client: Any = None,
    max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    repair_feedback: Optional[str] = None,
) -> ResolvedAction:
    """`repair_feedback`: when the orchestrator's repair loop re-calls
    resolve() after a validation failure (spec: "max 2 repair attempts"),
    it passes the validator's errors here so the model actually has a
    chance of fixing them -- otherwise a retry would just repeat the
    same mistake, since nothing else about the conversation changes."""
    client = llm_client or LLMClient(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    user_content = _candidate_block(candidate) + "\n" + _roster_block(roster)
    if repair_feedback:
        user_content += (
            f"\nYour previous attempt failed validation: {repair_feedback}\n"
            "Fix this and call finalize_resolution again."
        )
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    tool_call_log: list[ToolCallLogEntry] = []
    llm_calls: list[LLMCallResult] = []

    for _ in range(max_tool_iterations):
        result = client.complete(messages=messages, tools=RESOLVER_TOOLS)
        llm_calls.append(result)

        if not result.tool_calls:
            break  # model gave up without finalizing -- unresolved

        messages.append(
            {
                "role": "assistant",
                "content": result.content,
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in result.tool_calls
                ],
            }
        )

        finalize_call = None
        for tc in result.tool_calls:
            args = json.loads(tc["arguments"])
            if tc["name"] == "finalize_resolution":
                finalize_call = args
                # finalize_resolution needs no execution/tool-result message: it's
                # the terminal answer, not a lookup.
                continue
            output = _execute_tool(tc["name"], args, meeting_date, roster, utterances)
            tool_call_log.append(ToolCallLogEntry(name=tc["name"], arguments=args, output=output))
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(output)})

        if finalize_call is not None:
            return ResolvedAction(
                owner=finalize_call.get("owner"),
                tool=finalize_call.get("tool"),
                task_text=finalize_call.get("task_text", candidate.task),
                description=finalize_call.get("description", ""),
                due=finalize_call.get("due"),
                attendees_or_recipients=finalize_call.get("attendees_or_recipients") or [],
                confidence_notes=finalize_call.get("confidence_notes", ""),
                unresolved=False,
                tool_call_log=tool_call_log,
                llm_calls=llm_calls,
            )

    return ResolvedAction(
        owner=None, tool=None, task_text=candidate.task, description="", due=None,
        attendees_or_recipients=[], confidence_notes="resolver did not finalize within max_tool_iterations",
        unresolved=True, tool_call_log=tool_call_log, llm_calls=llm_calls,
    )
