"""
eval/dataset.py
------------------
Locates a transcript's text, roster, meeting date, and (if reviewed)
gold labels by transcript_id, bridging this project's two directory
conventions:
  - legacy (step 1): test1's transcript/roster live where step 1 and
    b0_adapter's tests already reference them -- hardcoded here rather
    than retrofitted into a meta.json, so nothing already committed
    has to move.
  - step 5: data/{synthetic,ami}/<transcript_id>/{transcript.txt,
    roster.json,meta.json}.

load_gold() returns None (not an error) when a transcript_id has no
reviewed data/gold/<id>.json yet -- most of step 5's drafts are still
unreviewed, and the eval runner must keep working (generating and
saving predictions) for those, just skipping the scoring step for them
rather than crashing or pretending to have gold it doesn't.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agent.schema import ActionItem

REPO_ROOT = Path(__file__).resolve().parent.parent

_LEGACY_TRANSCRIPTS = {
    "test1": {
        "transcript_path": REPO_ROOT / "baselines" / "b0_rules" / "examples" / "test1.txt",
        "roster_path": REPO_ROOT / "data" / "rosters" / "test1_roster.json",
        "meeting_date": "2026-09-02",
    }
}

_DATASET_DIRS = ("synthetic", "ami")


@dataclass
class TranscriptBundle:
    transcript_id: str
    transcript_text: str
    roster: list[dict]
    meeting_date: str
    dataset: str  # "test1" | "synthetic" | "ami" -- which table this transcript belongs in


def find_transcript_dir(transcript_id: str) -> Optional[Path]:
    for dataset_dir in _DATASET_DIRS:
        candidate = REPO_ROOT / "data" / dataset_dir / transcript_id
        if candidate.is_dir():
            return candidate
    return None


def load_bundle(transcript_id: str) -> TranscriptBundle:
    if transcript_id in _LEGACY_TRANSCRIPTS:
        info = _LEGACY_TRANSCRIPTS[transcript_id]
        return TranscriptBundle(
            transcript_id=transcript_id,
            transcript_text=info["transcript_path"].read_text(encoding="utf-8"),
            roster=json.loads(info["roster_path"].read_text(encoding="utf-8")),
            meeting_date=info["meeting_date"],
            dataset="test1",
        )

    transcript_dir = find_transcript_dir(transcript_id)
    if transcript_dir is None:
        raise FileNotFoundError(
            f"No transcript found for transcript_id={transcript_id!r} "
            f"(checked legacy test1 location and data/{{synthetic,ami}}/)"
        )
    meta = json.loads((transcript_dir / "meta.json").read_text(encoding="utf-8"))
    return TranscriptBundle(
        transcript_id=transcript_id,
        transcript_text=(transcript_dir / "transcript.txt").read_text(encoding="utf-8"),
        roster=json.loads((transcript_dir / "roster.json").read_text(encoding="utf-8")),
        meeting_date=meta["meeting_date"],
        dataset=transcript_dir.parent.name,
    )


def load_gold(transcript_id: str) -> Optional[list[ActionItem]]:
    path = REPO_ROOT / "data" / "gold" / f"{transcript_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return [ActionItem(**row) for row in data]


def load_split(name: str) -> list[str]:
    splits = json.loads((REPO_ROOT / "data" / "splits.json").read_text(encoding="utf-8"))
    return splits[name]
