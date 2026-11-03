#!/usr/bin/env python3
"""
scripts/build_ami_excerpts.py
--------------------------------
Reconstructs readable speaker-labeled transcript excerpts from the
official AMI Meeting Corpus manual annotations (CC BY 4.0), and writes
them into data/ami/<excerpt_id>/ alongside a roster.json and meta.json.

Source: https://groups.inf.ed.ac.uk/ami/download/ ->
"AMI manual annotations v1.6.2" (ami_public_manual_1.6.2.zip, 22MB,
released 2017-04-10). License: Creative Commons Attribution 4.0
International (CC BY 4.0) -- see that page for the exact statement.
We do NOT vendor the 22MB annotation archive into this repo (only our
curated excerpts); re-download it from the URL above to --ami-dir to
regenerate or add more excerpts.

AMI's "scenario" meetings (series ES20xx, IS10xx, TS30xx) are
role-played: four participants are assigned the roles Project Manager
(PM), Industrial Designer (ID), User Interface Designer (UI), and
Marketing Expert (ME) for a fictional remote-control design task. The
PM/ID/UI/ME -> speaker-letter mapping is itself part of AMI's public
metadata (corpusResources/meetings.xml), not something we invented; we
use the role title as our roster "name" (rather than inventing or
guessing a personal name) since that's the one stable, documented
identity AMI assigns each speaker.

Fidelity note: these are real recorded (if scripted-scenario) meetings,
transcribed by AMI's own transcribers. We reconstruct the text exactly
as transcribed (filler words, disfluencies, and all) -- we do not clean
up or paraphrase it. A small number of excerpts include a participant
using another participant's actual first name in conversation (that is
how they were recorded, we are not redacting or altering it); flagged
in data/ami/ATTRIBUTION.md for anyone who wants to redact before wider
distribution.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

NITE_NS = {"nite": "http://nite.sourceforge.net/"}

ROLE_DISPLAY = {
    "PM": {"name": "Project Manager", "trello_member_id": "member_pm"},
    "ID": {"name": "Industrial Designer", "trello_member_id": "member_id"},
    "UI": {"name": "User Interface Designer", "trello_member_id": "member_ui"},
    "ME": {"name": "Marketing Expert", "trello_member_id": "member_me"},
}


def _email_for(role_name: str) -> str:
    return role_name.lower().replace(" ", ".") + "@example.com"


@dataclass(frozen=True)
class Utterance:
    start: float
    speaker_letter: str
    text: str


def _parse_words(ami_dir: Path, meeting: str, speaker: str) -> dict:
    path = ami_dir / "words" / f"{meeting}.{speaker}.words.xml"
    tree = ET.parse(path)
    words = {}
    for w in tree.getroot():
        wid = w.attrib.get("{http://nite.sourceforge.net/}id")
        if w.tag == "w":
            words[wid] = (w.text or "", w.attrib.get("punc") == "true")
        else:
            words[wid] = (None, False)
    return words


def _parse_segments(ami_dir: Path, meeting: str, speaker: str) -> list:
    path = ami_dir / "segments" / f"{meeting}.{speaker}.segments.xml"
    tree = ET.parse(path)
    segs = []
    for seg in tree.getroot():
        start = float(seg.attrib["transcriber_start"])
        child = seg.find("nite:child", NITE_NS)
        if child is None:
            continue
        ids = re.findall(r"id\(([^)]+)\)", child.attrib["href"])
        id_range = (ids[0], ids[0]) if len(ids) == 1 else (ids[0], ids[1])
        segs.append((start, id_range))
    return segs


def _word_ids_in_range(meeting: str, speaker: str, id_range: tuple) -> list:
    prefix = f"{meeting}.{speaker}.words"
    start_n = int(id_range[0].replace(prefix, ""))
    end_n = int(id_range[1].replace(prefix, ""))
    return [f"{prefix}{n}" for n in range(start_n, end_n + 1)]


def _render(words: dict, ids: list) -> str:
    parts = []
    for wid in ids:
        if wid not in words:
            continue
        text, punc = words[wid]
        if text is None:
            continue
        parts.append(text if (punc or not parts) else " " + text)
    return "".join(parts).strip()


def build_full_transcript(ami_dir: Path, meeting: str, speakers=("A", "B", "C", "D")) -> list[Utterance]:
    turns = []
    for sp in speakers:
        try:
            words = _parse_words(ami_dir, meeting, sp)
            segs = _parse_segments(ami_dir, meeting, sp)
        except FileNotFoundError:
            continue
        for start, id_range in segs:
            ids = _word_ids_in_range(meeting, sp, id_range)
            text = _render(words, ids)
            if text:
                turns.append(Utterance(start=start, speaker_letter=sp, text=text))
    turns.sort(key=lambda u: u.start)
    return turns


def get_meeting_role_map(ami_dir: Path, meeting: str) -> dict:
    """Returns {speaker_letter: role_code} for `meeting`, read from AMI's
    own corpusResources/meetings.xml -- not guessed, not hardcoded."""
    tree = ET.parse(ami_dir / "corpusResources" / "meetings.xml")
    for m in tree.getroot():
        if m.attrib.get("observation") == meeting:
            mapping = {}
            for sp in m.findall("speaker"):
                mapping[sp.attrib["nxt_agent"]] = sp.attrib["role"]
            date_only = m.attrib.get("dateOnly", "")
            return mapping, date_only
    raise ValueError(f"Meeting {meeting!r} not found in meetings.xml")


def _normalize_date(date_only: str) -> str:
    day, month, year = date_only.split("-")
    if len(year) == 2:
        year = "20" + year
    return f"{year}-{month}-{day}"


def write_excerpt(ami_dir: Path, meeting: str, start_idx: int, end_idx: int, excerpt_id: str, out_root: Path) -> None:
    turns = build_full_transcript(ami_dir, meeting)
    role_map, date_only = get_meeting_role_map(ami_dir, meeting)
    window = turns[start_idx:end_idx]

    out_dir = out_root / excerpt_id
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [f"AMI Meeting Corpus excerpt {meeting} (utterances {start_idx}-{end_idx - 1} of full transcript)"]
    for u in window:
        role = role_map.get(u.speaker_letter, "?")
        display_name = ROLE_DISPLAY.get(role, {}).get("name", role)
        lines.append(f"{display_name}: {u.text}")
    (out_dir / "transcript.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    roster = []
    for letter in ("A", "B", "C", "D"):
        role = role_map.get(letter)
        if role is None:
            continue
        info = ROLE_DISPLAY[role]
        roster.append(
            {
                "name": info["name"],
                "aliases": [role],
                "email": _email_for(info["name"]),
                "trello_member_id": info["trello_member_id"],
            }
        )
    (out_dir / "roster.json").write_text(json.dumps(roster, indent=2) + "\n", encoding="utf-8")

    meta = {
        "source_meeting": meeting,
        "source_corpus": "AMI Meeting Corpus, manual annotations v1.6.2 (CC BY 4.0)",
        "source_url": "https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip",
        "meeting_date": _normalize_date(date_only),
        "utterance_range_in_full_transcript": [start_idx, end_idx],
        "speaker_role_map": role_map,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {excerpt_id}: {len(window)} utterances, meeting_date={meta['meeting_date']}")


# Our curated selection: 7 excerpts across 6 distinct meeting series
# (ES2009, IS1003 x2, ES2008, TS3003, TS3005, ES2011), each a closing
# segment where the Project Manager assigns concrete individual/pair
# follow-up work -- picked by scanning for action-cue density, see the
# step-5 build notes in README.md for how these were selected.
EXCERPTS = [
    ("ES2009c", 313, 378, "ami_es2009c_closing"),
    ("IS1003b", 350, 424, "ami_is1003b_closing"),
    ("IS1003c", 440, 514, "ami_is1003c_closing"),
    ("ES2008c", 350, 396, "ami_es2008c_closing"),
    ("TS3003b", 359, 404, "ami_ts3003b_closing"),
    ("TS3005b", 648, 693, "ami_ts3005b_closing"),
    ("ES2011c", 300, 362, "ami_es2011c_closing"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AMI excerpt transcripts/rosters into data/ami/.")
    parser.add_argument("--ami-dir", required=True, help="Path to the extracted ami_public_manual_1.6.2.zip")
    parser.add_argument("--out-dir", default="data/ami")
    args = parser.parse_args()

    ami_dir = Path(args.ami_dir)
    out_root = Path(args.out_dir)
    for meeting, start, end, excerpt_id in EXCERPTS:
        write_excerpt(ami_dir, meeting, start, end, excerpt_id, out_root)


if __name__ == "__main__":
    main()
