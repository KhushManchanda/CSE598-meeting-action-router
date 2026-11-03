import json
import threading
import time

import pytest

from ui import demo
from ui.runtime import MODES, RunController, RunRequest, load_history, read_local_config, validate_roster


def request():
    return RunRequest("Test walkthrough", demo.TRANSCRIPT, demo.MEETING_DATE, demo.ROSTER, MODES[0])


def wait_for(controller, predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = controller.snapshot()
        if predicate(state):
            return state
        threading.Event().wait(0.01)
    raise AssertionError(controller.snapshot())


def test_ui_worker_requires_each_approval_and_start_is_idempotent(tmp_path):
    controller = RunController(request(), runs_dir=tmp_path)
    assert controller.start()
    assert not controller.start()
    first = wait_for(controller, lambda state: state["pending"] is not None)["pending"]
    assert first["tool"] == "trello_task"
    assert not any(a["state"] == "verified" for a in controller.snapshot()["actions"])
    assert controller.submit(first["id"], True, {"task": "Reviewed deployment checklist"})
    assert not controller.submit(first["id"], True)  # stale approval cannot execute twice
    second = wait_for(controller, lambda state: state["pending"] is not None)["pending"]
    assert second["tool"] == "calendar_event"
    assert controller.submit(second["id"], False)
    third = wait_for(controller, lambda state: state["pending"] is not None)["pending"]
    assert "Check the release notes" in third["description"]
    assert controller.submit(third["id"], True, {"description": third["description"] + "\nSee you there."})
    state = wait_for(controller, lambda state: state["status"] == "complete")
    assert len(state["report"]["verified"]) == 2
    assert len(state["report"]["rejected"]) == 1
    assert state["report"]["tool_calls_used"] == 2
    assert state["report"]["verified"][0]["created_object"]["title"] == "Reviewed deployment checklist"
    assert state["report"]["verified"][1]["created_object"]["body"].endswith("See you there.")
    controller._thread.join(timeout=3)
    history = load_history(tmp_path)
    assert len(history) == 1 and history[0]["status"] == "complete"
    assert (controller.path / "report.json").exists()
    assert "OPENAI_API_KEY" not in (controller.path / "input.json").read_text()


def test_stopping_at_review_never_executes_an_unapproved_action(tmp_path):
    controller = RunController(request(), runs_dir=tmp_path)
    controller.start()
    wait_for(controller, lambda state: state["pending"] is not None)
    controller.cancel()
    state = wait_for(controller, lambda state: state["status"] == "stopped")
    controller._thread.join(timeout=3)
    assert not any(row["execution_attempts"] for row in state["actions"])
    assert state["pending"] is None


def test_review_timeout_stops_without_execution(tmp_path):
    controller = RunController(request(), runs_dir=tmp_path, review_timeout=0.03)
    controller.start()
    state = wait_for(controller, lambda state: state["status"] == "stopped")
    controller._thread.join(timeout=3)
    assert not any(row["execution_attempts"] for row in state["actions"])


def test_configuration_is_not_read_without_explicit_consent(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Configuration file must not be opened")
    monkeypatch.setattr("dotenv.dotenv_values", forbidden)
    with pytest.raises(PermissionError):
        read_local_config(False)


def test_offline_walkthrough_rejects_changed_input_instead_of_faking_extraction(tmp_path):
    req = request()
    with pytest.raises(ValueError, match="fixed transcript"):
        RunController(RunRequest(req.title, "Arjun: I will do a different task.", req.meeting_date,
                                 req.roster, MODES[0]), runs_dir=tmp_path)


def test_roster_rejects_ambiguous_names_and_invalid_emails():
    with pytest.raises(ValueError, match="unique"):
        validate_roster([{"name": "Arjun", "aliases": ["A"]}, {"name": "A"}])
    with pytest.raises(ValueError, match="valid email"):
        validate_roster([{"name": "Arjun", "email": "not an email"}])


def test_history_ignores_partial_or_corrupt_state(tmp_path):
    folder = tmp_path / "ui-broken"
    folder.mkdir()
    (folder / "state.json").write_text("not JSON")
    assert load_history(tmp_path) == []


def test_runtime_scrubs_supplied_keys_from_snapshots_and_evidence(tmp_path):
    # Explicitly fictional placeholder; never reads a local environment file.
    fake_key = "placeholder-key-for-test"
    controller = RunController(request(), config={"OPENAI_API_KEY": fake_key}, runs_dir=tmp_path)
    controller._event({"event": "test", "message": fake_key})
    assert fake_key not in json.dumps(controller.snapshot())


def test_live_clients_use_explicit_configuration_without_global_client(monkeypatch, tmp_path):
    from types import SimpleNamespace
    openai_client = SimpleNamespace()
    composio_client = SimpleNamespace()
    calls = {}

    def openai(**kwargs):
        calls["openai"] = kwargs
        return openai_client

    def composio(**kwargs):
        calls["composio"] = kwargs
        return composio_client

    monkeypatch.setattr("openai.OpenAI", openai)
    monkeypatch.setattr("composio.Composio", composio)
    config = {"OPENAI_API_KEY": "fictional-openai", "LLM_MODEL": "configured-test-model",
              "COMPOSIO_API_KEY": "fictional-composio", "COMPOSIO_USER_ID": "test-user",
              "TRELLO_LIST_ID": "test-list"}
    req = request()
    controller = RunController(RunRequest(req.title, req.transcript, req.meeting_date, req.roster, MODES[2]),
                               config, runs_dir=tmp_path)
    client, tools = controller._build_clients()
    assert client.model == "configured-test-model"
    assert client._get_client() is openai_client
    assert calls["openai"]["api_key"] == "fictional-openai"
    assert calls["composio"]["api_key"] == "fictional-composio"
    assert tools["trello"].list_id == "test-list"
    assert all(tool._client is composio_client for tool in tools.values())
