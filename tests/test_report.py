import csv
import json
import tempfile
from pathlib import Path

from eval.report import (
    category_breakdown, dataset_table, fault_injection_table, flatten_rows, stability_table,
    worst_errors, write_csv, write_results,
)
from eval.run_eval import run_eval

CANDIDATE_RELEASE_NOTES = [
    {
        "task": "Draft release notes", "raw_owner_mention": "Marcus", "raw_due_mention": "Friday",
        "evidence_quote": "Marcus will draft the release notes and create a task to track review.",
        "evidence_utterance_ids": ["u10"],
    }
]


def _results_with_real_test1_scoring():
    """Builds a real results dict (via eval/run_eval.run_eval, but with
    a fake LLM client -- no real API calls) so report.py's table
    functions are tested against genuine eval/score.py output, not a
    hand-built stand-in."""
    from tests.test_run_eval import _OneCandidateScriptedClient

    return run_eval(
        transcript_ids=["test1"], systems=["a"], out_dir=Path(tempfile.mkdtemp()),
        llm_client=_OneCandidateScriptedClient(),
    )


def test_flatten_rows_produces_one_row_per_run():
    results = _results_with_real_test1_scoring()
    rows = flatten_rows(results)
    assert len(rows) == 1
    assert rows[0]["transcript_id"] == "test1"
    assert rows[0]["dataset"] == "test1"
    assert rows[0]["has_gold"] is True
    assert rows[0]["n_gold"] == 6


def test_write_csv_round_trips(tmp_path):
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    path = tmp_path / "out.csv"
    write_csv(rows, path)
    with open(path) as f:
        read_back = list(csv.DictReader(f))
    assert read_back == [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]


def test_write_csv_handles_empty_rows(tmp_path):
    path = tmp_path / "out.csv"
    write_csv([], path)
    assert path.exists()


def test_dataset_table_reports_no_gold_message_for_unscored_dataset():
    rows = [{"dataset": "synthetic", "has_gold": False, "system": "a"}]
    table = dataset_table(rows, "synthetic")
    assert "No reviewed gold yet" in table


def test_dataset_table_computes_means_across_scored_rows():
    rows = [
        {"dataset": "test1", "has_gold": True, "system": "a", "precision": 1.0, "recall": 0.8, "f1": 0.89, "owner_accuracy_matched": 1.0, "routing_accuracy_matched": 0.8},
        {"dataset": "test1", "has_gold": True, "system": "a", "precision": 0.8, "recall": 0.6, "f1": 0.69, "owner_accuracy_matched": 0.9, "routing_accuracy_matched": 0.6},
    ]
    table = dataset_table(rows, "test1")
    assert "| a | 2 |" in table
    assert "90.0%" in table  # owner accuracy mean


def test_category_breakdown_uses_matched_pairs_not_gold_alone():
    results = _results_with_real_test1_scoring()
    table = category_breakdown(results)
    assert "category" in table
    assert "n matched items" in table


def test_stability_table_reports_stdev_for_repeated_runs(tmp_path):
    from tests.test_run_eval import _OneCandidateScriptedClient

    results = run_eval(
        transcript_ids=["test1"], systems=["a"], out_dir=tmp_path / "run",
        repeat=3, repeat_subset=["test1"], llm_client=_OneCandidateScriptedClient(),
    )
    table = stability_table(flatten_rows(results))
    assert "test1" in table
    assert "| 3 |" in table  # n runs


def test_stability_table_reports_nothing_when_no_repeats():
    rows = [{"transcript_id": "t1", "system": "a", "has_gold": True, "f1": 0.9}]
    table = stability_table(rows)
    assert "nothing to report" in table


def test_worst_errors_lists_lowest_f1_per_system():
    rows = [
        {"transcript_id": "t1", "system": "a", "run_index": 0, "has_gold": True, "f1": 0.9, "precision": 1.0, "recall": 0.8},
        {"transcript_id": "t2", "system": "a", "run_index": 0, "has_gold": True, "f1": 0.3, "precision": 0.5, "recall": 0.2},
    ]
    table = worst_errors(rows, top_n=1)
    assert "t2" in table
    assert "t1" not in table  # worse one only, top_n=1


def test_fault_injection_table_shows_a_recovers_and_norec_fails_on_lost_response():
    table = fault_injection_table()
    lines = {line.split("|")[1].strip(): line for line in table.splitlines() if line.startswith("|") and "fault" not in line and "---" not in line}
    lost_response_row = lines["lost_response"]
    assert "verified" in lost_response_row.split("|")[2]  # A recovers
    assert "FAILED" in lost_response_row.split("|")[3]  # single-attempt does not
    assert "committed server-side: True" in lost_response_row.split("|")[3]


def test_fault_injection_table_covers_all_fault_types():
    table = fault_injection_table()
    for fault in ["429", "503", "timeout", "lost_response", "invalid_argument", "expired_token"]:
        assert fault in table


def test_write_results_produces_md_and_csv(tmp_path):
    results = _results_with_real_test1_scoring()
    write_results(results, tmp_path / "results")
    assert (tmp_path / "results" / "results.md").exists()
    assert (tmp_path / "results" / "results.csv").exists()
    md = (tmp_path / "results" / "results.md").read_text()
    assert "Dataset: test1" in md
    assert "Fault injection" in md
