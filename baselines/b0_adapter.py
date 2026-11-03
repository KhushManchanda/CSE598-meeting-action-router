"""
baselines/b0_adapter.py
------------------------
Runs Neha's vendored B0 baseline (baselines/b0_rules/, pinned at commit
3c6a693, logic untouched) on any transcript and converts its output into
our common ActionItem schema (agent/schema.py), so eval/score.py can
compare B0 against gold, B1, and our agent A on equal footing.

B0 itself has no notion of utterance IDs — it just scans raw lines — so
this adapter re-derives which utterance each B0 result came from by
applying B0's OWN ACTION_CUES regex (imported, not re-implemented) to our
parsed Utterance list, in document order. Since B0 is single-line and
one-result-per-matched-line, the two orderings line up 1:1; if a future
change to b0_rules breaks that assumption, this adapter raises loudly
rather than silently mis-aligning evidence.

Known, intentional fidelity to B0's real (buggy) behavior — we are
converting its output, not fixing it:
  - owner is whatever B0 reported (usually the speaker, not the true
    doer — that's the bug under test).
  - due is always None: B0 never resolves dates.
  - attendees_or_recipients is [owner] for email_draft items, because
    B0's send_email stub literally sends the confirmation "to {owner}"
    rather than to a real recipient — a faithful capture of the
    "sets email recipients wrong" bug, not a fix for it.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_B0_DIR = _THIS_DIR / "b0_rules"
_REPO_ROOT = _THIS_DIR.parent

# Our own package is named "agent" (agent/schema.py, agent/ingestion.py) and
# B0's vendored module is ALSO named "agent" (b0_rules/agent.py). Both can't
# share the "agent" name in sys.modules at once, so B0's module is loaded
# directly from its file path under a private name instead of via a bare
# `import agent`, which would silently bind to the wrong one depending on
# sys.path order.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from agent.ingestion import parse_transcript  # noqa: E402  (OUR agent/ package)
from agent.schema import ActionItem  # noqa: E402


def _load_b0_agent_module():
    # b0_rules/agent.py does `from tools import TOOL_REGISTRY` (a bare,
    # same-directory import) — b0_rules/ must be on sys.path for that to
    # resolve, but under its own module name ("tools") there's no collision
    # with anything of ours.
    if str(_B0_DIR) not in sys.path:
        sys.path.insert(0, str(_B0_DIR))
    spec = importlib.util.spec_from_file_location("b0_rules_agent", _B0_DIR / "agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b0_agent = _load_b0_agent_module()  # the vendored baseline's agent.py, logic untouched

# B0 tool name -> our canonical tool name (agent/schema.py:ALLOWED_TOOLS)
_TOOL_MAP = {
    "schedule_event": "calendar_event",
    "send_email": "email_draft",
    "create_task": "trello_task",
}


def run_b0_on_transcript(transcript_path: str | Path, transcript_id: str | None = None) -> list[ActionItem]:
    """Runs B0 on transcript_path and returns predictions in common schema."""
    path = Path(transcript_path)
    transcript_text = path.read_text(encoding="utf-8")
    transcript_id = transcript_id or path.stem

    utterances = parse_transcript(transcript_text)

    # Replay B0's own extractor cue-matching (same regex list, same target
    # string B0 checks: the full stripped line) to recover, in order, which
    # utterance each B0 result must have come from.
    cue_utterance_ids = [
        u.id
        for u in utterances
        if any(re.search(cue, u.raw.lower()) for cue in b0_agent.ACTION_CUES)
    ]

    results = b0_agent.run_agent(transcript_text)

    if len(cue_utterance_ids) != len(results):
        raise RuntimeError(
            "b0_adapter evidence-alignment assumption violated: "
            f"{len(cue_utterance_ids)} cue-matched utterances vs "
            f"{len(results)} B0 results for {path}. B0's extractor logic "
            "may have changed upstream in b0_rules/agent.py — do not guess "
            "an alignment, fix this adapter instead."
        )

    items: list[ActionItem] = []
    for idx, (res, u_id) in enumerate(zip(results, cue_utterance_ids), start=1):
        tool = _TOOL_MAP.get(res["routed_tool"], res["routed_tool"])
        recipients = [res["owner"]] if tool == "email_draft" else []
        items.append(
            ActionItem(
                id=f"{transcript_id}-b0-{idx}",
                transcript_id=transcript_id,
                task=res["action"],
                owner=res["owner"],
                tool=tool,
                due=None,
                attendees_or_recipients=recipients,
                evidence_utterance_ids=[u_id],
            )
        )
    return items


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run B0 and print common-schema predictions as JSON.")
    parser.add_argument("--input", required=True, help="Path to a transcript .txt file")
    parser.add_argument("--transcript-id", default=None)
    args = parser.parse_args()

    predictions = run_b0_on_transcript(args.input, args.transcript_id)
    print(json.dumps([p.model_dump() for p in predictions], indent=2))
