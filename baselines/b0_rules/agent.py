"""
agent.py
--------
Baseline agent for the "Meeting Action-Item Router" project.

Pipeline (a tool-use / workflow agentic baseline):
  1. PERCEIVE  - read a raw meeting transcript
  2. EXTRACT   - find sentences that describe an action item and pull out
                 (owner, action_text) using pattern matching
  3. DECIDE    - route each action item to the tool that should handle it
                 (schedule_event / send_email / create_task) using keyword
                 rules over the action text
  4. ACT       - call the chosen tool and collect its confirmation
  5. REPORT    - return a structured list describing what the agent did

This is intentionally a rule-based planner rather than an LLM-based one.
See README.md "Known limitations" for why, and the capstone proposal
Section 7 for the planned upgrade path (replacing steps 2-3 with an LLM
tool-calling call to the Claude API).
"""

import re
import sys
import json
from tools import TOOL_REGISTRY

# Modal/action cues that mark a sentence as an action item.
ACTION_CUES = [
    r"\bwill\b", r"\bneeds? to\b", r"\bshould\b", r"\bis going to\b",
    r"\bplans? to\b", r"\bmust\b", r"^action:", r"\bto do\b",
]

# Keyword -> tool routing table. Checked in order; first match wins.
ROUTING_RULES = [
    (["schedule", "calendar", "meeting", "call", "sync", "demo", "book time"], "schedule_event"),
    (["email", "send", "follow up with", "notify", "reply to"], "send_email"),
    ([], "create_task"),  # default / fallback tool
]


def extract_action_items(transcript: str):
    """Step 2: EXTRACT. Returns a list of (owner, action_text) tuples."""
    items = []
    for raw_line in transcript.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()
        if not any(re.search(cue, lower) for cue in ACTION_CUES):
            continue

        # Expected transcript shape: "Name: sentence with an action cue."
        if ":" in line:
            owner, action_text = line.split(":", 1)
            owner = owner.strip()
            action_text = action_text.strip()
        else:
            owner, action_text = "Unassigned", line

        items.append((owner, action_text))
    return items


def route_action_item(action_text: str) -> str:
    """Step 3: DECIDE. Returns the tool name to invoke for this action."""
    lower = action_text.lower()
    for keywords, tool_name in ROUTING_RULES:
        if any(keyword in lower for keyword in keywords):
            return tool_name
    return "create_task"


def run_agent(transcript: str) -> list:
    """Runs the full extract -> decide -> act loop over a transcript."""
    results = []
    for owner, action_text in extract_action_items(transcript):
        tool_name = route_action_item(action_text)          # DECIDE
        tool_fn = TOOL_REGISTRY[tool_name]
        tool_result = tool_fn(owner=owner, description=action_text)  # ACT
        results.append({
            "owner": owner,
            "action": action_text,
            "routed_tool": tool_result["tool"],
            "tool_status": tool_result["status"],
            "confirmation": tool_result["confirmation"],
        })
    return results


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--input":
        print("Usage: python run_baseline.py --input <path_to_transcript.txt>")
        sys.exit(1)

    input_path = sys.argv[2]
    with open(input_path, "r", encoding="utf-8") as f:
        transcript = f.read()

    results = run_agent(transcript)

    print(f"\n=== Meeting Action-Item Router: baseline output for '{input_path}' ===\n")
    if not results:
        print("No action items detected.")
    for i, item in enumerate(results, start=1):
        print(f"[{i}] Owner: {item['owner']}")
        print(f"    Action:        {item['action']}")
        print(f"    Routed tool:   {item['routed_tool']}")
        print(f"    Confirmation:  {item['confirmation']}")
        print()

    print(f"Total action items found: {len(results)}")

    out_path = input_path.rsplit(".", 1)[0] + "_output.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Structured JSON output written to: {out_path}")


if __name__ == "__main__":
    main()
