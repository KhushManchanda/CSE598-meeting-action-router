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

    @field_validator("due")
    @classmethod
    def _due_must_be_iso_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            date_cls.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"due={v!r} is not an ISO-8601 date (YYYY-MM-DD)") from exc
        return v
