"""
Tests for eval/run_eval.py, driven by a fake LLM client (no real/paid
API calls). Runs against the real `test1` transcript/gold since that's
the one transcript_id with reviewed gold right now -- exercising the
actual eval/score.py scoring path, not a mock of it.
"""

import json

from agent.llm import LLMCallResult
from eval.dataset import load_bundle
from eval.run_eval import SystemRunResult, run_eval, run_system


def _tc(id_, tool_name, **kwargs):
    return {"id": id_, "name": tool_name, "arguments": json.dumps(kwargs)}


def _finalize_result(**kwargs):
    defaults = dict(owner=None, tool="trello_task", task_text="x", description="d", due=None, attendees_or_recipients=[], confidence_notes="")
    defaults.update(kwargs)
    return LLMCallResult(content=None, tool_calls=[_tc("r1", "finalize_resolution", **defaults)], model="gpt-4o-mini")


def _grounding_result(grounded=True, reason="ok"):
    return LLMCallResult(content=None, tool_calls=[_tc("g1", "report_grounding", grounded=grounded, reason=reason)], model="gpt-4o-mini")


class _OneCandidateScriptedClient:
    """Always proposes exactly one candidate (Marcus will draft release
    notes), resolves it cleanly, and grounds it -- enough to drive both
    B1's and Agent A's full real pipelines deterministically."""

    CANDIDATE = [
        {
            "task": "Draft release notes", "raw_owner_mention": "Marcus", "raw_due_mention": "Friday",
            "evidence_quote": "Marcus will draft the release notes and create a task to track review.",
            "evidence_utterance_ids": ["u10"],
        }
    ]

    def complete(self, messages, tools=None, tool_choice=None, response_format=None):
        name = (tool_choice or {}).get("function", {}).get("name")
        if name == "propose_action_items":
            return LLMCallResult(content=None, tool_calls=[_tc("c1", "propose_action_items", candidates=self.CANDIDATE)], model="gpt-4o-mini")
        if name == "report_grounding":
            return _grounding_result(True)

        # Neither the resolver nor B1 forces a tool_choice, so the only
        # way to tell them apart is which TOOL SET they offered.
        tool_names = {t["function"]["name"] for t in (tools or [])}
        if "finalize_resolution" in tool_names:
            return _finalize_result(owner="Marcus", tool="trello_task", task_text="Draft release notes", due="2026-09-04")
        if "create_task" in tool_names:
            return LLMCallResult(
                content=None,
                tool_calls=[
                    _tc(
                        "b1-1", "create_task", title="Draft release notes", assignee_member_id="member_marcus",
                        due="2026-09-04", list_id="list_todo", description="d",
                        owner="Marcus", evidence_utterance_ids=["u10"],
                    )
                ],
                model="gpt-4o-mini",
            )
        raise AssertionError(f"unexpected tool set offered to fake LLM client: {tool_names}")


def test_run_system_b0_needs_no_llm_client():
    bundle = load_bundle("test1")
    result = run_system("b0", bundle)
    assert result.system == "b0"
    assert len(result.predictions) == 7  # B0's known behavior on test1.txt
    assert result.tool_calls_used is None  # B0 never touches the mock backend


def test_run_system_b1_with_fake_client():
    bundle = load_bundle("test1")
    result = run_system("b1", bundle, llm_client=_OneCandidateScriptedClient())
    assert result.system == "b1"
    assert len(result.predictions) == 1
    assert result.predictions[0]["owner"] == "Marcus"
    assert result.verified_count == 1


def test_run_system_agent_a_with_fake_client():
    bundle = load_bundle("test1")
    result = run_system("a", bundle, llm_client=_OneCandidateScriptedClient())
    assert result.system == "a"
    assert len(result.predictions) == 1
    assert result.verified_count == 1
    assert result.escalated_count == 0


def test_run_system_unknown_system_raises():
    import pytest

    bundle = load_bundle("test1")
    with pytest.raises(ValueError):
        run_system("not_a_real_system", bundle)


def test_run_eval_end_to_end_scores_against_real_gold(tmp_path):
    results = run_eval(
        transcript_ids=["test1"], systems=["a"], out_dir=tmp_path / "run1",
        llm_client=_OneCandidateScriptedClient(),
    )
    assert "test1" in results
    runs = results["test1"]["a"]
    assert len(runs) == 1
    score = runs[0]["score"]
    assert score is not None  # test1 has reviewed gold
    assert score["n_gold"] == 6

    # config + predictions actually written to disk
    assert (tmp_path / "run1" / "config.json").exists()
    pred_path = tmp_path / "run1" / "predictions" / "a" / "test1.json"
    assert pred_path.exists()


def test_run_eval_repeat_subset_runs_multiple_times(tmp_path):
    results = run_eval(
        transcript_ids=["test1"], systems=["a"], out_dir=tmp_path / "run2",
        repeat=3, repeat_subset=["test1"], llm_client=_OneCandidateScriptedClient(),
    )
    assert len(results["test1"]["a"]) == 3
    # each repeat's prediction file is saved separately
    pred_dir = tmp_path / "run2" / "predictions" / "a"
    assert (pred_dir / "test1_0.json").exists()
    assert (pred_dir / "test1_1.json").exists()
    assert (pred_dir / "test1_2.json").exists()


def test_run_eval_transcript_without_gold_still_generates_predictions(tmp_path):
    results = run_eval(
        transcript_ids=["synth_eng_sync_01"], systems=["a"], out_dir=tmp_path / "run3",
        llm_client=_OneCandidateScriptedClient(),
    )
    run = results["synth_eng_sync_01"]["a"][0]
    assert run["score"] is None  # no reviewed gold yet for this transcript
    assert isinstance(run["predictions"], list)  # predictions were still generated
