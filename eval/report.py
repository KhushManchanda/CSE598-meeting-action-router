"""
eval/report.py
-----------------
Turns eval/run_eval.py's raw per-(transcript_id, system) results into
results/results.md (human-readable) and results/results.csv (one row
per transcript_id x system x run), plus a per-category breakdown (gold's
`category` field, for whichever transcript_ids have reviewed gold) and
a fault-injection table exercising agent/verifier.py's recovery
directly (not tied to any specific transcript -- the recovery logic is
the same regardless of which transcript triggered it).
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Optional

from eval.dataset import load_bundle, load_gold


def _mean(values: list) -> Optional[float]:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _stdev(values: list) -> Optional[float]:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _fmt_pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def flatten_rows(results: dict) -> list[dict]:
    """One row per (transcript_id, system, run_index)."""
    rows = []
    for transcript_id, by_system in results.items():
        dataset = load_bundle(transcript_id).dataset
        for system, runs in by_system.items():
            for run_idx, run in enumerate(runs):
                score = run.get("score") or {}
                owner_raw = (score.get("owner_accuracy_raw") or {}).get("accuracy")
                rows.append(
                    {
                        "transcript_id": transcript_id, "dataset": dataset, "system": system, "run_index": run_idx,
                        "tool_calls_used": run.get("tool_calls_used"), "cost_usd": run.get("cost_usd"),
                        "verified_count": run.get("verified_count"), "escalated_count": run.get("escalated_count"),
                        "rejected_count": run.get("rejected_count"), "execution_failures": run.get("execution_failures"),
                        "n_predictions": score.get("n_predictions"), "n_gold": score.get("n_gold"),
                        "precision": score.get("precision"), "recall": score.get("recall"), "f1": score.get("f1"),
                        "owner_accuracy_matched": score.get("owner_accuracy_matched"),
                        "routing_accuracy_matched": score.get("routing_accuracy_matched"),
                        "owner_accuracy_raw": owner_raw, "has_gold": bool(run.get("score")),
                    }
                )
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def dataset_table(rows: list[dict], dataset: str) -> str:
    scored = [r for r in rows if r["dataset"] == dataset and r["has_gold"]]
    if not scored:
        return (
            f"_No reviewed gold yet for dataset `{dataset}` -- predictions were generated and saved "
            f"(see runs/<timestamp>/predictions/), but nothing to score. See `data/gold_draft/` and "
            f"`scripts/review_gold.py`._\n"
        )
    systems = sorted({r["system"] for r in scored})
    lines = [
        "| system | n scored | precision | recall | F1 | owner acc (matched) | routing acc |",
        "|---|---|---|---|---|---|---|",
    ]
    for system in systems:
        srows = [r for r in scored if r["system"] == system]
        lines.append(
            f"| {system} | {len(srows)} | {_fmt_pct(_mean([r['precision'] for r in srows]))} | "
            f"{_fmt_pct(_mean([r['recall'] for r in srows]))} | {_fmt_pct(_mean([r['f1'] for r in srows]))} | "
            f"{_fmt_pct(_mean([r['owner_accuracy_matched'] for r in srows]))} | "
            f"{_fmt_pct(_mean([r['routing_accuracy_matched'] for r in srows]))} |"
        )
    return "\n".join(lines) + "\n"


def category_breakdown(results: dict) -> str:
    """Owner accuracy by gold category, over matched pairs (not gold
    alone), across every system/transcript with reviewed gold."""
    from agent.schema import ActionItem
    from eval.score import match_predictions_to_gold

    by_category: dict[str, dict[str, int]] = {}
    for transcript_id, by_system in results.items():
        gold = load_gold(transcript_id)
        if not gold:
            continue
        for runs in by_system.values():
            for run in runs:
                preds = [ActionItem(**p) for p in run["predictions"]]
                for m in match_predictions_to_gold(preds, gold):
                    if m.gold is None:
                        continue
                    category = m.gold.category or "uncategorized"
                    bucket = by_category.setdefault(category, {"correct": 0, "total": 0})
                    bucket["total"] += 1
                    if (m.pred.owner or "").strip().lower() == (m.gold.owner or "").strip().lower():
                        bucket["correct"] += 1

    if not by_category:
        return "_No reviewed gold yet -- nothing to break down by category._\n"
    lines = ["| category | owner accuracy | n matched items |", "|---|---|---|"]
    for category in sorted(by_category):
        b = by_category[category]
        acc = b["correct"] / b["total"] if b["total"] else None
        lines.append(f"| {category} | {_fmt_pct(acc)} | {b['total']} |")
    return "\n".join(lines) + "\n"


def stability_table(rows: list[dict]) -> str:
    """Spec: 'Repeats a subset 3 times to check stability.' stdev of
    F1 across repeated runs of the same (transcript_id, system)."""
    grouped: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if r["has_gold"]:
            grouped[(r["transcript_id"], r["system"])].append(r["f1"])
    repeated = {k: v for k, v in grouped.items() if len(v) > 1}
    if not repeated:
        return "_No transcript in this run used --repeat > 1; nothing to report on stability._\n"
    lines = ["| transcript_id | system | n runs | mean F1 | stdev F1 |", "|---|---|---|---|---|"]
    for (transcript_id, system), f1s in sorted(repeated.items()):
        lines.append(f"| {transcript_id} | {system} | {len(f1s)} | {_fmt_pct(_mean(f1s))} | {_stdev(f1s):.4f} |")
    return "\n".join(lines) + "\n"


def worst_errors(rows: list[dict], top_n: int = 3) -> str:
    """Per system, the lowest-F1 (transcript_id, run) with reviewed
    gold -- a pointer to where each system is actually failing, not
    just an aggregate."""
    scored = [r for r in rows if r["has_gold"] and r["f1"] is not None]
    if not scored:
        return "_No reviewed gold yet -- nothing to rank._\n"
    lines = []
    for system in sorted({r["system"] for r in scored}):
        srows = sorted((r for r in scored if r["system"] == system), key=lambda r: r["f1"])[:top_n]
        lines.append(f"**{system}**:")
        for r in srows:
            lines.append(
                f"- `{r['transcript_id']}` (run {r['run_index']}): F1={_fmt_pct(r['f1'])}, "
                f"precision={_fmt_pct(r['precision'])}, recall={_fmt_pct(r['recall'])}"
            )
    return "\n".join(lines) + "\n"


def fault_injection_table() -> str:
    """Exercises agent/verifier.py's recovery directly against every
    fault type the mock backend supports, contrasting full recovery
    (A) against no-recovery (A-norec / B1's own no-retry-by-design
    behavior, which is mechanically identical to A-norec's single
    attempt). Not tied to any real transcript -- the recovery logic
    doesn't depend on which transcript triggered the fault.

    Deliberately NOT special-cased for "lost_response": a single,
    no-retry attempt genuinely DOES fail on it, even though the object
    was actually committed server-side -- this is a real, honest
    finding (an un-retried lost_response leaves an orphaned object the
    system never learns about), not a bug in this table.
    """
    from agent.participants import Roster
    from agent.resolver import ResolvedAction
    from agent.router import build_tool_args, call_tool, idempotency_key
    from agent.schema import ActionItem
    from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello
    from agent.verifier import execute_with_recovery

    roster = Roster([{"name": "Marcus", "aliases": [], "email": "marcus@example.com", "trello_member_id": "member_marcus"}])
    item = ActionItem(id="fault-1", transcript_id="fault", task="Dummy task", owner="Marcus", tool="trello_task", due="2026-09-04")
    resolved_action = ResolvedAction(
        owner="Marcus", tool="trello_task", task_text="Dummy task", description="d", due="2026-09-04",
        attendees_or_recipients=[], confidence_notes="", unresolved=False,
    )
    key = idempotency_key("fault", "fault-1")
    fault_types = ["429", "503", "timeout", "lost_response", "invalid_argument", "expired_token"]

    lines = ["| fault | A (full recovery) | A-norec / B1-style (single attempt, no retry) |", "|---|---|---|"]
    for fault in fault_types:
        tools_a = {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}
        tools_a["trello"].set_fault_plan(key, [fault])
        outcome_a = execute_with_recovery(item, resolved_action, roster, tools_a, key, sleep_fn=lambda s: None)
        a_cell = f"{outcome_a.outcome} ({outcome_a.attempts} attempt(s))"

        tools_b = {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}
        tools_b["trello"].set_fault_plan(key, [fault])
        args = build_tool_args(item, resolved_action, roster)
        try:
            call_tool("trello_task", args, tools_b, key)
            b_cell = "verified (no fault needed retry)"
        except Exception as exc:
            committed = len(tools_b["trello"].all_objects())
            b_cell = f"FAILED, no retry ({type(exc).__name__}); object committed server-side: {committed > 0}"

        lines.append(f"| {fault} | {a_cell} | {b_cell} |")
    return "\n".join(lines) + "\n"


def write_results(results: dict, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = flatten_rows(results)
    write_csv(rows, out_dir / "results.csv")

    datasets = sorted({r["dataset"] for r in rows})
    md = ["# Eval Results\n"]
    for dataset in datasets:
        md.append(f"## Dataset: {dataset}\n")
        md.append(dataset_table(rows, dataset))
        md.append("")

    md.append("## Per-category breakdown (owner accuracy, matched items, all systems/transcripts with reviewed gold)\n")
    md.append(category_breakdown(results))
    md.append("")

    md.append("## Stability (repeated runs)\n")
    md.append(stability_table(rows))
    md.append("")

    md.append("## Worst errors per system (lowest F1, reviewed gold only)\n")
    md.append(worst_errors(rows))
    md.append("")

    md.append("## Fault injection (agent/verifier.py's recovery, exercised directly)\n")
    md.append(fault_injection_table())

    (out_dir / "results.md").write_text("\n".join(md), encoding="utf-8")
