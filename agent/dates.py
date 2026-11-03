"""
agent/dates.py
----------------
Deterministic date resolution -- backs the resolver's
resolve_date(expression, meeting_date, timezone) tool. Per spec:
"deterministic parsing (dateparser plus our own rules for 'next week',
'before Friday'), LLM fallback only if needed."

LLM fallback is NOT implemented in this pass -- every phrase this
project's data actually exercises is covered by the rules below. That's
a disclosed gap, not a silent one: if a transcript uses a date
expression these rules can't resolve, resolve_date returns None (the
validator then treats a missing-but-required due date as something to
ask the resolver to retry or to escalate — see agent/validator.py), it
never fabricates a plausible-looking wrong date.

Key design choice, consistent with our own gold-labeling convention
(data/gold/test1.NOTES.md): a bare, dayless "next week" (or "this
week"/"soon"/"later") is too vague to resolve to one specific day, so
it resolves to None rather than guessing "+7 days" the way dateparser's
own relative parser does by default.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

import dateparser

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
_WEEKDAY_RE = re.compile(r"\b(" + "|".join(_WEEKDAYS) + r")\b", re.IGNORECASE)

_AMBIGUOUS_PATTERNS = [
    re.compile(r"^\s*next week\s*$", re.IGNORECASE),
    re.compile(r"^\s*this week\s*$", re.IGNORECASE),
    re.compile(r"^\s*soon\s*$", re.IGNORECASE),
    re.compile(r"^\s*later\s*$", re.IGNORECASE),
    re.compile(r"^\s*eventually\s*$", re.IGNORECASE),
]


def resolve_date(expression: str, meeting_date: str, timezone: str = "UTC") -> Optional[str]:
    """Returns an ISO-8601 date string on or after meeting_date, or None
    if `expression` is too vague to resolve confidently. `timezone` is
    accepted for interface parity with the spec but unused: every date
    this project resolves is a calendar date, not a timestamp."""
    text = expression.strip()
    if not text:
        return None
    if any(p.match(text) for p in _AMBIGUOUS_PATTERNS):
        return None

    base = date.fromisoformat(meeting_date)

    weekday_match = _WEEKDAY_RE.search(text)
    if weekday_match:
        target = _WEEKDAYS[weekday_match.group(1).lower()]
        offset = (target - base.weekday()) % 7  # 0 if the meeting IS that weekday
        return (base + timedelta(days=offset)).isoformat()

    base_dt = datetime(base.year, base.month, base.day)
    parsed = dateparser.parse(text, settings={"RELATIVE_BASE": base_dt, "PREFER_DATES_FROM": "future"})
    if parsed is None:
        return None

    resolved = parsed.date()
    if resolved < base:
        # Defense in depth: PREFER_DATES_FROM should already prevent this,
        # but the validator's "due must be >= meeting_date" rule is a hard
        # requirement -- never hand back a date that would fail it.
        return None
    return resolved.isoformat()
