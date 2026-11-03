"""
agent/ingestion.py
-------------------
Step 1 of the pipeline: PERCEIVE. Parses a speaker-labeled transcript
("Speaker: utterance" per line) into addressable Utterance objects with
stable IDs (u1, u2, ...), so every later stage (extractor evidence,
resolver's get_context, validator's verbatim-quote check) can refer to
"u7" instead of re-matching raw text.

This module is intentionally tiny and dependency-free so it can be reused
by both baselines/b0_adapter.py (to recover evidence_utterance_ids for B0,
which has no notion of utterance IDs) and the real agent in step 4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# "Name: rest of the line." — speaker name is text before the FIRST colon.
# Header/title lines with no colon (e.g. "Weekly Product Sync - Sept 2, 2026")
# do not match and are skipped, matching B0's own documented input format.
_SPEAKER_LINE_RE = re.compile(r"^([^:]{1,60}):\s*(.*)$")


@dataclass(frozen=True)
class Utterance:
    id: str  # "u1", "u2", ... in document order
    speaker: str
    text: str  # content after the speaker's colon, stripped
    raw: str  # the full stripped line ("Speaker: text"), for verbatim checks
    line_no: int  # 1-indexed line number in the original transcript file


def parse_transcript(transcript_text: str) -> list[Utterance]:
    """Parses transcript text into a list of Utterance, skipping blank lines
    and any line that isn't "Speaker: text" (e.g. a title/date header)."""
    utterances: list[Utterance] = []
    counter = 0
    for line_no, raw_line in enumerate(transcript_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        match = _SPEAKER_LINE_RE.match(line)
        if not match:
            continue
        speaker, text = match.group(1).strip(), match.group(2).strip()
        if not speaker or not text:
            continue
        counter += 1
        utterances.append(
            Utterance(id=f"u{counter}", speaker=speaker, text=text, raw=line, line_no=line_no)
        )
    return utterances


def evidence_context(utterances: list[Utterance], evidence_ids: list[str], window: int = 2) -> list[dict]:
    """Original source turns near evidence, deduplicated in document order.

    Keep full turns: a short extraction quote can omit content later in
    the same utterance. Unknown IDs never imply a guessed source span.
    """
    by_id = {u.id: index for index, u in enumerate(utterances)}
    indexes = set()
    for evidence_id in evidence_ids:
        center = by_id.get(evidence_id)
        if center is not None:
            indexes.update(range(max(0, center - max(0, window)),
                                 min(len(utterances), center + max(0, window) + 1)))
    return [{"id": utterances[i].id, "speaker": utterances[i].speaker, "text": utterances[i].text}
            for i in sorted(indexes)]
