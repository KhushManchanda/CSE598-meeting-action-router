#!/usr/bin/env python3
"""
scripts/review_gold.py
-------------------------
CLI to review draft gold labels (data/gold_draft/<transcript_id>.json)
one item at a time -- accept, fix, or skip -- writing only reviewed
items into data/gold/<transcript_id>.json. Per spec: "Build a small
CLI so Arjun and I can accept or fix each one. Only reviewed labels go
into gold/."

Usage:
    python scripts/review_gold.py --transcript-id synth_eng_sync_01

Already-reviewed items (matched by id) are skipped on a rerun, so
review can happen in multiple sittings, or by a different person than
whoever wrote the draft.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent.schema import ActionItem  # noqa: E402

EDITABLE_FIELDS = ("task", "owner", "tool", "due", "attendees_or_recipients", "category")


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


def _render(item: dict, print_fn: Callable[[str], None]) -> None:
    print_fn("-" * 60)
    print_fn(f"id: {item['id']}")
    print_fn(f"task: {item['task']}")
    print_fn(f"owner: {item.get('owner')}")
    print_fn(f"tool: {item.get('tool')}")
    print_fn(f"due: {item.get('due')}")
    print_fn(f"attendees_or_recipients: {item.get('attendees_or_recipients')}")
    print_fn(f"evidence_utterance_ids: {item.get('evidence_utterance_ids')}")
    print_fn(f"category: {item.get('category')}")


def review_items(
    draft_items: list[dict],
    already_reviewed_ids: set[str],
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> list[dict]:
    """Returns the newly-reviewed (accepted or fixed) items only --
    excludes items already in already_reviewed_ids and anything
    skipped this pass (it'll be re-prompted next run, not lost)."""
    reviewed: list[dict] = []
    for item in draft_items:
        if item["id"] in already_reviewed_ids:
            continue
        _render(item, print_fn)
        raw = input_fn("Accept / Fix / Skip? [a/f/s, default a]: ").strip().lower()

        if raw in ("", "a", "accept"):
            ActionItem(**item)  # validate before accepting
            reviewed.append(item)
            continue
        if raw in ("s", "skip"):
            print_fn(f"Skipped {item['id']} -- it will be re-prompted next run.")
            continue
        if raw in ("f", "fix"):
            fixed = dict(item)
            while True:
                field = input_fn("Field to fix (blank to finish): ").strip()
                if not field:
                    break
                if field not in EDITABLE_FIELDS:
                    print_fn(f"Unknown field {field!r}, skipping.")
                    continue
                new_value = input_fn(f"New value for {field} (blank = null): ").strip()
                if field == "attendees_or_recipients":
                    fixed[field] = [v.strip() for v in new_value.split(",") if v.strip()]
                else:
                    fixed[field] = new_value or None
            ActionItem(**fixed)  # validate the fix before accepting it
            reviewed.append(fixed)
            continue
        print_fn(f"Unrecognized input {raw!r} -- treating as skip.")
    return reviewed


def main() -> None:
    parser = argparse.ArgumentParser(description="Review draft gold labels into data/gold/.")
    parser.add_argument("--transcript-id", required=True)
    parser.add_argument("--draft-dir", default="data/gold_draft")
    parser.add_argument("--gold-dir", default="data/gold")
    args = parser.parse_args()

    draft_path = Path(args.draft_dir) / f"{args.transcript_id}.json"
    gold_path = Path(args.gold_dir) / f"{args.transcript_id}.json"

    draft_items = _load_json(draft_path)
    if not draft_items:
        print(f"No draft items found at {draft_path}")
        return

    existing_gold = _load_json(gold_path)
    already_reviewed_ids = {item["id"] for item in existing_gold}

    # Pass input/print explicitly (rather than relying on review_items'
    # own defaults) so tests that monkeypatch builtins.input/print take
    # effect -- a default parameter value is bound once at module
    # import time, before any test's monkeypatch runs, and would
    # otherwise still point at the original builtin.
    newly_reviewed = review_items(draft_items, already_reviewed_ids, input_fn=input, print_fn=print)
    if newly_reviewed:
        _save_json(gold_path, existing_gold + newly_reviewed)
        print(f"Wrote {len(newly_reviewed)} newly-reviewed item(s) to {gold_path}")
    else:
        print("No new items reviewed.")


if __name__ == "__main__":
    main()
