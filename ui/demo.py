"""Clearly labeled, fixed offline walkthrough; never a real-model evaluation."""
import json

from agent.llm import LLMCallResult

TRANSCRIPT = """Weekly project sync
Dana: Omar will prepare the deployment checklist by November 6, 2026.
Lily: Lily will schedule a dashboard review on November 9, 2026, with Dana.
Omar: Omar will email Dana the launch review agenda. The agenda is to check the release notes, review test results, and confirm next steps.
"""
ROSTER = [
    {"name": name, "aliases": [], "email": f"{name.lower()}@example.com", "trello_member_id": f"member_{name.lower()}"}
    for name in ("Dana", "Omar", "Lily")
]
MEETING_DATE = "2026-11-03"
TASKS = [
    dict(task="Prepare the deployment checklist", owner="Omar", tool="trello_task", due="2026-11-06",
         recipients=[], quote="Omar will prepare the deployment checklist by November 6, 2026.", evidence="u1",
         body="Prepare the deployment checklist for the release."),
    dict(task="Dashboard review", owner="Lily", tool="calendar_event", due="2026-11-09",
         recipients=["dana@example.com"], quote="Lily will schedule a dashboard review on November 9, 2026, with Dana.", evidence="u2",
         body="Review the dashboard with Dana."),
    dict(task="Launch review agenda", owner="Omar", tool="email_draft", due=None,
         recipients=["dana@example.com"], quote="Omar will email Dana the launch review agenda.", evidence="u3",
         body="Hi Dana,\n\nHere is the launch review agenda:\n- Check the release notes\n- Review test results\n- Confirm next steps\n\nThanks,\nOmar"),
]


def result(name, arguments):
    return LLMCallResult(content=None, tool_calls=[{"id": "offline", "name": name,
                         "arguments": json.dumps(arguments)}], model="offline-walkthrough", cost_usd=0.0)


class WalkthroughClient:
    """Scripted responses for TRANSCRIPT only; uses the real downstream pipeline."""
    def complete(self, messages, tools=None, tool_choice=None, **kwargs):
        forced = (tool_choice or {}).get("function", {}).get("name")
        if forced == "propose_action_items":
            return result(forced, {"candidates": [dict(task=t["task"], raw_owner_mention=t["owner"],
                raw_due_mention=t["due"], evidence_quote=t["quote"], evidence_utterance_ids=[t["evidence"]]) for t in TASKS]})
        if forced == "report_grounding":
            return result(forced, {"grounded": True, "reason": "Scripted walkthrough; content quality is not evaluated by a model."})
        content = messages[1]["content"]
        task = next(t for t in TASKS if f"  task: {t['task']}\n" in content)
        return result("finalize_resolution", dict(owner=task["owner"], tool=task["tool"],
            task_text=task["task"], description=task["body"], due=task["due"],
            attendees_or_recipients=task["recipients"], confidence_notes="Offline walkthrough: scripted resolution.", unresolved=False))
