"""
agent/extractor.py
---------------------
Extractor: one structured-output LLM call over the full transcript,
proposing candidate action items. Per spec, each candidate must include
evidence_utterance_ids and a verbatim evidence_quote -- the validator
(agent/validator.py) checks the quote actually appears in the
transcript and that it actually supports the claimed action/owner.

Implemented as a single forced tool call (propose_action_items) rather
than response_format JSON-schema mode, for consistency with how every
other LLM-calling stage in this project (resolver, B1) already works.

Deliberately NOT resolving owner/due here -- the extractor reports only
what the transcript literally says (raw_owner_mention, raw_due_mention);
agent/resolver.py turns those into a real roster owner and an ISO date.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.config import LLM_MODEL, LLM_TEMPERATURE
from agent.ingestion import Utterance, parse_transcript
from agent.llm import LLMCallResult, LLMClient
from agent.prompts import load_prompt

PROMPT_NAME = "extractor_v1"

EXTRACTOR_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_action_items",
        "description": "Propose every candidate follow-up action item found in the transcript.",
        "parameters": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "Short, self-contained description of the action "
                                "(e.g. 'Schedule a demo with the design team', not 'do it').",
                            },
                            "raw_owner_mention": {
                                "type": ["string", "null"],
                                "description": "The name/pronoun the transcript uses for who will do "
                                "this (e.g. 'Marcus', 'someone', 'we'). Null if nobody is mentioned.",
                            },
                            "raw_due_mention": {
                                "type": ["string", "null"],
                                "description": "The date/time expression the transcript uses, verbatim "
                                "(e.g. 'next Friday', \"before Friday's launch\"). Null if none.",
                            },
                            "evidence_quote": {
                                "type": "string",
                                "description": "A verbatim quote (exact substring) from the transcript "
                                "that supports this action item.",
                            },
                            "evidence_utterance_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Utterance id(s) (e.g. 'u3') the evidence_quote comes "
                                "from. Cite more than one when the action is only clear from combining "
                                "turns (a vague commitment claimed by a named person a turn later).",
                            },
                        },
                        "required": [
                            "task", "raw_owner_mention", "raw_due_mention",
                            "evidence_quote", "evidence_utterance_ids",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["candidates"],
            "additionalProperties": False,
        },
    },
}

SYSTEM_PROMPT = load_prompt(PROMPT_NAME)


@dataclass
class Candidate:
    task: str
    raw_owner_mention: Optional[str]
    raw_due_mention: Optional[str]
    evidence_quote: str
    evidence_utterance_ids: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    candidates: list[Candidate]
    llm_call: LLMCallResult


def _transcript_block(utterances: list[Utterance]) -> str:
    return "\n".join(f"{u.id}: {u.speaker}: {u.text}" for u in utterances)


def build_messages(transcript_text: str) -> tuple[list[dict], list[Utterance]]:
    utterances = parse_transcript(transcript_text)
    user_content = "Transcript (utterance id: speaker: text):\n" + _transcript_block(utterances)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    return messages, utterances


def extract(transcript_text: str, llm_client: Any = None) -> ExtractionResult:
    messages, _utterances = build_messages(transcript_text)
    client = llm_client or LLMClient(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    result = client.complete(
        messages=messages,
        tools=[EXTRACTOR_TOOL],
        tool_choice={"type": "function", "function": {"name": "propose_action_items"}},
    )

    candidates: list[Candidate] = []
    for tc in result.tool_calls:
        if tc["name"] != "propose_action_items":
            continue
        try:
            args = json.loads(tc["arguments"])
        except json.JSONDecodeError:
            continue
        for raw in args.get("candidates", []):
            candidates.append(
                Candidate(
                    task=raw.get("task", ""),
                    raw_owner_mention=raw.get("raw_owner_mention"),
                    raw_due_mention=raw.get("raw_due_mention"),
                    evidence_quote=raw.get("evidence_quote", ""),
                    evidence_utterance_ids=raw.get("evidence_utterance_ids") or [],
                )
            )

    return ExtractionResult(candidates=candidates, llm_call=result)
