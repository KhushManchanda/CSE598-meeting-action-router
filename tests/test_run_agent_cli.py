import subprocess
import sys


def test_tools_live_without_confirm_live_exits_without_running():
    result = subprocess.run(
        [sys.executable, "run_agent.py", "--input", "baselines/b0_rules/examples/test1.txt",
         "--roster", "data/rosters/test1_roster.json", "--meeting-date", "2026-09-02", "--tools", "live"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "--confirm-live" in result.stderr
