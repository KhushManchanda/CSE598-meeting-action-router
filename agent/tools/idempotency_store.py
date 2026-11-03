"""
agent/tools/idempotency_store.py
-----------------------------------
Unlike the mock backend (an in-memory dict), none of the real APIs
this project targets (Google Calendar, Gmail, Trello) accept a client-
supplied idempotency key natively. Each live adapter (step 7) needs to
implement the same guarantee itself: a small local JSON file mapping
idempotency_key -> object_id, checked before every create call.

This is the one piece of local state a live adapter keeps -- small,
human-readable, and specific to idempotency bookkeeping only (not a
cache of the object's content, which the real API remains the source
of truth for; read-back still goes to the real API every time).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class IdempotencyStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            self._data: dict[str, str] = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def get(self, idempotency_key: str) -> Optional[str]:
        return self._data.get(idempotency_key)

    def set(self, idempotency_key: str, object_id: str) -> None:
        self._data[idempotency_key] = object_id
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
