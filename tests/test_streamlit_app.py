import threading
import time
import runpy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ui import demo
from ui.runtime import MODES, RunController, RunRequest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def app():
    at = AppTest.from_file(str(APP), default_timeout=15)
    # Prevent AppTest from consulting any real Streamlit secrets store.
    at.secrets["test_placeholder"] = "offline-only"
    return at


def test_ui_starts_offline_without_loading_configuration(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("The default UI must not read configuration")
    monkeypatch.setattr("dotenv.dotenv_values", forbidden)
    at = app().run()
    assert not at.exception
    assert at.title[0].value == "Review your meeting actions"
    assert at.selectbox(key="runtime_mode").value == MODES[0]
    assert any("Offline walkthrough" in message.value for message in at.info)


@pytest.mark.parametrize("page", ["Run history", "Evaluation", "Connections"])
def test_read_only_pages_render_without_credentials(page):
    at = app()
    at.session_state["workspace_nav"] = page
    at.run()
    assert not at.exception


def test_review_ui_can_reject_each_offline_action_and_render_results(tmp_path):
    controller = RunController(RunRequest("UI test", demo.TRANSCRIPT, demo.MEETING_DATE, demo.ROSTER, MODES[0]),
                               runs_dir=tmp_path)
    controller.start()
    at = app()
    at.session_state["run_controller"] = controller
    at.session_state["workspace_nav"] = "Current run"
    try:
        for _ in range(3):
            deadline = time.monotonic() + 5
            while controller.snapshot()["pending"] is None and time.monotonic() < deadline:
                threading.Event().wait(0.01)
            at.run()
            assert not at.exception
            reject = next(button for button in at.button if button.label == "Reject action")
            reject.click().run()
        controller._thread.join(timeout=5)
        at.run()
        assert not at.exception
        assert controller.snapshot()["status"] == "complete"
        assert len(controller.snapshot()["report"]["rejected"]) == 3
        assert controller.snapshot()["report"]["tool_calls_used"] == 0
    finally:
        controller.cancel()
        controller._thread.join(timeout=3)


def test_setup_starts_one_worker_and_review_preserves_an_edit(monkeypatch, tmp_path):
    controllers = []

    def create(request, config):
        controller = RunController(request, config, runs_dir=tmp_path)
        controllers.append(controller)
        return controller

    monkeypatch.setattr("ui.runtime.RunController", create)
    at = app().run()
    next(button for button in at.button if button.label == "Extract actions →").click().run()
    controller = controllers[0]
    try:
        for index in range(3):
            deadline = time.monotonic() + 5
            while controller.snapshot()["pending"] is None and time.monotonic() < deadline:
                threading.Event().wait(0.01)
            at.run()
            assert not at.exception
            if index == 0:
                next(field for field in at.text_input if field.label == "Subject / task title").set_value("Reviewed deployment checklist")
                label = "Approve action"
            else:
                label = "Reject action"
            next(button for button in at.button if button.label == label).click().run()
        controller._thread.join(timeout=5)
        at.run()
        assert not at.exception
        assert len(controllers) == 1
        report = controller.snapshot()["report"]
        assert report["verified"][0]["created_object"]["title"] == "Reviewed deployment checklist"
        assert len(report["rejected"]) == 2
    finally:
        controller.cancel()
        controller._thread.join(timeout=3)


def test_api_mode_requires_consent_before_reading_configuration(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Configuration must not be read without consent")

    monkeypatch.setattr("dotenv.dotenv_values", forbidden)
    at = app().run()
    at.selectbox(key="runtime_mode").set_value(MODES[1]).run()
    next(button for button in at.button if button.label == "Extract actions →").click().run()
    assert not at.exception
    assert any("Allow this app" in message.value for message in at.error)
    assert "run_controller" not in at.session_state


def test_launcher_applies_localhost_and_no_secret_store_before_starting(monkeypatch):
    from streamlit.web import bootstrap
    calls = []
    monkeypatch.setattr(bootstrap, "load_config_options", lambda options: calls.append(("configure", options)))
    monkeypatch.setattr(bootstrap, "run", lambda path, hello, args, options: calls.append(("start", options)))
    runpy.run_path(str(APP.parent / "run_ui.py"), run_name="__main__")
    assert [call[0] for call in calls] == ["configure", "start"]
    options = calls[0][1]
    assert options["server.address"] == "127.0.0.1"
    assert options["secrets.files"] == []
    assert options["browser.gatherUsageStats"] is False
