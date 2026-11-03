"""
agent/participants.py
------------------------
Roster lookup -- backs the resolver's lookup_participant(name) tool.
Matches a name or alias (case-insensitively, exact match only) against
the roster loaded from a roster JSON file (see data/rosters/*.json for
the {name, aliases, email, trello_member_id} shape).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _normalize(name: str) -> str:
    return name.strip().lower()


class Roster:
    def __init__(self, participants: list[dict]):
        self._participants = participants
        self._index: dict[str, dict] = {}
        for p in participants:
            self._index[_normalize(p["name"])] = p
            for alias in p.get("aliases", []):
                self._index[_normalize(alias)] = p

    @classmethod
    def from_file(cls, path: str | Path) -> "Roster":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data)

    def lookup(self, name: str) -> Optional[dict]:
        """Exact (case-insensitive) name/alias match. Returns the full
        participant record, or None -- "not found" per the spec's
        lookup_participant(name) tool contract, not an exception."""
        return self._index.get(_normalize(name))

    def all(self) -> list[dict]:
        return list(self._participants)
