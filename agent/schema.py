"""
agent/schema.py
----------------
The common schema that every system in this project (B0, B1, our agent A,
and gold labels) is converted into before scoring. Keeping one strict,
shared shape is what lets eval/score.py compare apples to apples.

    {id, transcript_id, task, owner, tool, due, attendees_or_recipients[],
     evidence_utterance_ids[]}
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Canonical tool names used everywhere downstream (router, scorer, reports).
# B0/B1 use their own tool-name spellings; adapters are responsible for
# mapping into this set, not the schema.
ALLOWED_TOOLS = {
    "calendar_event",  # create_calendar_event (Google Calendar)
    "trello_task",  # create_task (Trello)
    "email_draft",  # create_email_draft (Gmail, stretch goal, draft-only)
}

# Spec (step 5): "Tag each gold item with a category" -- this is the fixed
# vocabulary, used only on GOLD items (predictions never set this). One
# gold item may genuinely earn more than one category (e.g. a multi-turn
# delegation that's also an alias case) -- callers pick the single most
# salient one; this is a label for humans reviewing/auditing the dataset,
# not itself a scored field.
ALLOWED_CATEGORIES = {
    "baseline",  # a normal, unambiguous case -- not every item needs an edge case
    "speaker_differs_from_owner",
    "multi_turn_delegation",
    "multiple_actions_one_line",
    "relative_date",
    "absolute_date",
    "pronoun_or_alias",
    "non_action",  # suggestion / negation / hypothetical / already-completed -- should NOT be extracted
    "ambiguous_escalate",  # owner/action genuinely unresolvable from the transcript alone
    "prompt_injection",
}


class ActionItem(BaseModel):
    """One action item, in gold OR predicted form, from any system."""

    model_config = {"extra": "forbid"}

    id: str
    transcript_id: str
    task: str = Field(min_length=1)
    owner: Optional[str] = None
    tool: Optional[str] = None
    due: Optional[str] = None  # ISO 8601 date string ("YYYY-MM-DD"), or None
    attendees_or_recipients: list[str] = Field(default_factory=list)
    evidence_utterance_ids: list[str] = Field(default_factory=list)
    category: Optional[str] = None  # gold-only, see ALLOWED_CATEGORIES

    @field_validator("tool")
    @classmethod
    def _tool_must_be_canonical(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_TOOLS:
            raise ValueError(
                f"tool={v!r} is not one of the canonical tool names {sorted(ALLOWED_TOOLS)}. "
                "Map provider/baseline-specific tool names onto these in the adapter, "
                "not here."
            )
        return v

    @field_validator("category")
    @classmethod
    def _category_must_be_known(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_CATEGORIES:
            raise ValueError(f"category={v!r} is not one of {sorted(ALLOWED_CATEGORIES)}")
        return v

    @field_validator("due")
    @classmethod
    def _due_must_be_iso_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Tolerate a full ISO-8601 datetime (LLM output occasionally
        # includes a time/timezone even when asked for a bare date --
        # found via a real eval/run_eval.py run where B1 returned
        # "2026-10-08T17:00:00Z" for a trello_task due date) by
        # normalizing to just the date part, rather than rejecting it
        # outright. Every downstream consumer (agent/router.py's
        # calendar start/end construction, eval/score.py's date
        # comparisons) assumes `due` is exactly YYYY-MM-DD, so
        # normalizing at this one shared boundary is safer than
        # trusting every caller to pre-sanitize its own LLM output.
        date_part = v.split("T")[0] if "T" in v else v
        try:
            return date_cls.fromisoformat(date_part).isoformat()
        except ValueError as exc:
            raise ValueError(f"due={v!r} is not an ISO-8601 date (YYYY-MM-DD)") from exc
