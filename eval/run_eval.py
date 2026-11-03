#!/usr/bin/env python3
"""
eval/run_eval.py
-------------------
Runs B0, B1, Agent A, and Agent A's ablations (A-noval, A-norec) over a
chosen split (dev/test/all), against the mock tool backend with
auto-approve. Saves every system's raw predictions under
runs/<timestamp>/ (with model/temperature/prompt-hash/budget config),
scores against data/gold/ for whichever transcript_ids have been
reviewed (most of step 5's are still drafts -- see eval/dataset.py,
which returns None rather than crashing for those), and writes
results/results.md + results/results.csv.

Usage:
    python -m eval.run_eval --split dev --systems b0,b1,a
    python -m eval.run_eval --split dev --systems a --repeat 3 --repeat-subset test1

B0 never touches the mock tool backend (its own tools.py stubs have no
idempotency/read-back concept at all -- see baselines/b0_adapter.py);
its behavior metrics (tool_calls_used, cost, etc.) are reported as
None/"n/a", not 0 -- 0 would wrongly claim something was measured.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

# Same reasoning as run_agent.py: agent/config.py and
# agent/tool_schemas.py read os.environ at import time, so .env must
# be loaded before those modules are imported, not lazily inside main().
load_dotenv()

from agent.config import LLM_MODEL, LLM_TEMPERATURE  # noqa: E402
from agent.ledger import VERIFIED, Ledger  # noqa: E402
from agent.orchestrator import DEFAULT_BUDGET, run_meeting  # noqa: E402
from agent.participants import Roster  # noqa: E402
from agent.prompts import prompt_hash  # noqa: E402
from agent.resolver import PROMPT_NAME as RESOLVER_PROMPT_NAME  # noqa: E402
from agent.validator import GROUNDING_PROMPT_NAME  # noqa: E402
from agent.schema import ActionItem  # noqa: E402
from agent.tools.mock_backend import MockCalendar, MockGmailDrafts, MockTrello  # noqa: E402
from baselines.b0_adapter import run_b0_on_transcript  # noqa: E402
from baselines.b1_single_call import run_b1  # noqa: E402
from eval.dataset import TranscriptBundle, load_bundle, load_gold, load_split  # noqa: E402
from eval.score import score as score_predictions  # noqa: E402

ALL_SYSTEMS = ["b0", "b1", "a", "a_noval", "a_norec"]
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class SystemRunResult:
    system: str
    transcript_id: str
    predictions: list[dict] = field(default_factory=list)
    tool_calls_used: Optional[int] = None
    cost_usd: Optional[float] = None
    verified_count: Optional[int] = None
    escalated_count: Optional[int] = None
    rejected_count: Optional[int] = None
    execution_failures: Optional[int] = None


def _fresh_tools() -> dict:
    return {"calendar": MockCalendar(), "trello": MockTrello(), "gmail": MockGmailDrafts()}


def _run_b0(bundle: TranscriptBundle) -> SystemRunResult:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(bundle.transcript_text)
        tmp_path = f.name
    predictions = run_b0_on_transcript(tmp_path, transcript_id=bundle.transcript_id)
    return SystemRunResult(system="b0", transcript_id=bundle.transcript_id, predictions=[p.model_dump() for p in predictions])


def _run_b1(bundle: TranscriptBundle, llm_client: Any = None) -> SystemRunResult:
    tools = _fresh_tools()
    result = run_b1(bundle.transcript_text, bundle.meeting_date, bundle.roster, tools, transcript_id=bundle.transcript_id, llm_client=llm_client)
    successes = sum(1 for r in result.execution_log if r.success)
    failures = sum(1 for r in result.execution_log if not r.success)
    return SystemRunResult(
        system="b1", transcript_id=bundle.transcript_id, predictions=[p.model_dump() for p in result.predictions],
        tool_calls_used=len(result.execution_log), cost_usd=result.llm_call.cost_usd,
        verified_count=successes, execution_failures=failures,
    )


def _run_agent_a(
    bundle: TranscriptBundle, system_name: str, enable_validator: bool, enable_recovery: bool, llm_client: Any = None
) -> SystemRunResult:
    tools = _fresh_tools()
    roster = Roster(bundle.roster)
    ledger = Ledger(":memory:")
    report = run_meeting(
        bundle.transcript_text, bundle.meeting_date, roster, tools, bundle.transcript_id,
        ledger=ledger, llm_client=llm_client, auto_approve=True,
        enable_validator=enable_validator, enable_recovery=enable_recovery, print_fn=lambda s: None,
    )
    records = ledger.list_for_meeting(bundle.transcript_id)
    ledger.close()

    predictions = []
    for r in records:
        if r.state != VERIFIED:
            continue
        predictions.append(
            ActionItem(
                id=r.id, transcript_id=bundle.transcript_id, task=r.task or "(untitled)",
                owner=r.owner, tool=r.tool, due=r.due,
                attendees_or_recipients=r.attendees_or_recipients, evidence_utterance_ids=r.evidence_utterance_ids,
            ).model_dump()
        )

    return SystemRunResult(
        system=system_name, transcript_id=bundle.transcript_id, predictions=predictions,
        tool_calls_used=report.tool_calls_used, cost_usd=report.total_cost_usd,
        verified_count=len(report.verified), escalated_count=len(report.escalated), rejected_count=len(report.rejected),
    )


def run_system(system: str, bundle: TranscriptBundle, llm_client: Any = None) -> SystemRunResult:
    """llm_client: override for testing (a fake/scripted client) or to
    point at a non-default model; None uses each system's own default
    LLMClient (real OpenAI calls). B0 ignores it -- it's rule-based."""
    if system == "b0":
        return _run_b0(bundle)
    if system == "b1":
        return _run_b1(bundle, llm_client=llm_client)
    if system == "a":
        return _run_agent_a(bundle, "a", enable_validator=True, enable_recovery=True, llm_client=llm_client)
    if system == "a_noval":
        return _run_agent_a(bundle, "a_noval", enable_validator=False, enable_recovery=True, llm_client=llm_client)
    if system == "a_norec":
        return _run_agent_a(bundle, "a_norec", enable_validator=True, enable_recovery=False, llm_client=llm_client)
    raise ValueError(f"Unknown system {system!r}, expected one of {ALL_SYSTEMS}")


def run_eval(
    transcript_ids: list[str],
    systems: list[str],
    out_dir: Path,
    repeat: int = 1,
    repeat_subset: Optional[list[str]] = None,
    llm_client: Any = None,
) -> dict:
    """Returns the full results structure: {transcript_id: {system: [run_dict, ...]}}.
    Every (system, transcript_id) pair runs once, except transcript_ids
    in repeat_subset (default: none), which run `repeat` times each --
    spec: "Repeats a subset 3 times to check stability." """
    repeat_subset = set(repeat_subset or [])
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "timestamp": out_dir.name,
        "model": LLM_MODEL,
        "temperature": LLM_TEMPERATURE,
        "budget_per_meeting": DEFAULT_BUDGET,
        "split_transcript_ids": transcript_ids,
        "systems": systems,
        "repeat": repeat,
        "repeat_subset": sorted(repeat_subset),
        "prompt_hashes": {
            "extractor_v1": prompt_hash("extractor_v1"),
            RESOLVER_PROMPT_NAME: prompt_hash(RESOLVER_PROMPT_NAME),
            GROUNDING_PROMPT_NAME: prompt_hash(GROUNDING_PROMPT_NAME),
            "b1_single_call_v1": prompt_hash("b1_single_call_v1"),
        },
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    results: dict[str, dict[str, list[dict]]] = {}
    for transcript_id in transcript_ids:
        bundle = load_bundle(transcript_id)
        gold = load_gold(transcript_id)
        n_runs = repeat if transcript_id in repeat_subset else 1
        results[transcript_id] = {}

        for system in systems:
            runs = []
            for run_idx in range(n_runs):
                run_result = run_system(system, bundle, llm_client=llm_client)
                scored = score_predictions([ActionItem(**p) for p in run_result.predictions], gold) if gold else None
                run_dict = {**asdict(run_result), "score": scored}
                runs.append(run_dict)

                pred_dir = out_dir / "predictions" / system
                pred_dir.mkdir(parents=True, exist_ok=True)
                suffix = f"_{run_idx}" if n_runs > 1 else ""
                (pred_dir / f"{transcript_id}{suffix}.json").write_text(json.dumps(run_dict, indent=2, default=str), encoding="utf-8")

            results[transcript_id][system] = runs

    (out_dir / "results_raw.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run B0/B1/Agent A (+ ablations) over a dataset split.")
    parser.add_argument("--split", default="dev", help="'dev', 'test', 'all', or a comma-separated list of transcript_ids")
    parser.add_argument("--systems", default="b0,b1,a", help=f"comma-separated subset of {ALL_SYSTEMS}")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--repeat-subset", default="", help="comma-separated transcript_ids to repeat --repeat times")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    if args.split == "all":
        transcript_ids = load_split("dev") + load_split("test")
    elif args.split in ("dev", "test"):
        transcript_ids = load_split(args.split)
    else:
        transcript_ids = [t.strip() for t in args.split.split(",") if t.strip()]

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    repeat_subset = [t.strip() for t in args.repeat_subset.split(",") if t.strip()]

    timestamp = args.out_dir or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "runs" / timestamp

    results = run_eval(transcript_ids, systems, out_dir, repeat=args.repeat, repeat_subset=repeat_subset)

    from eval.report import write_results  # local import: report.py imports nothing heavy, avoids a cycle at module load

    write_results(results, REPO_ROOT / "results")
    print(f"Wrote raw predictions/config to {out_dir}")
    print(f"Wrote results/results.md and results/results.csv")


if __name__ == "__main__":
    main()
