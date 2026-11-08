"""INST-01: hook registration in .claude/settings.json."""
import json
import os
import shutil
import subprocess

import pytest

from hookutil import HOOK, ROOT, events

EVENTS = ["UserPromptSubmit", "Stop", "PreCompact", "SessionStart", "SessionEnd"]
SETTINGS = ROOT / ".claude" / "settings.json"


def _commands(event):
    groups = json.loads(SETTINGS.read_text())["hooks"].get(event, [])
    return [h for g in groups for h in g.get("hooks", [])]


@pytest.mark.req("INST-01")
@pytest.mark.parametrize("event", EVENTS)
def test_each_event_registers_log_event_via_project_dir(event):
    """Each of the 5 events has exactly one command hook, and it calls
    .claude/hooks/log_event.py through a double-quoted $CLAUDE_PROJECT_DIR path."""
    hooks = _commands(event)
    assert len(hooks) == 1, hooks
    assert hooks[0]["type"] == "command"
    assert '"$CLAUDE_PROJECT_DIR/.claude/hooks/log_event.py"' in hooks[0]["command"]


@pytest.mark.req("INST-01")
def test_no_unexpected_events_registered():
    """settings.json registers exactly the 5 spec'd events, so nothing else fires the hook."""
    assert sorted(json.loads(SETTINGS.read_text())["hooks"]) == sorted(EVENTS)


@pytest.mark.req("INST-01")
def test_session_end_timeout_exceeds_default_budget():
    """SessionEnd sets a timeout above the 1.5 s shared budget, so the transcript copy (INST-04)
    isn't cut off."""
    assert _commands("SessionEnd")[0].get("timeout", 0) >= 5


@pytest.mark.req("INST-01")
@pytest.mark.kind("integration")
@pytest.mark.parametrize("event", EVENTS)
def test_registered_command_runs_from_path_with_spaces(tmp_path, event):
    """The exact command string from settings.json, run through a shell from a project dir
    whose path contains spaces (like the real one), reaches the hook and logs the event."""
    project = tmp_path / "proj with spaces"
    (project / ".claude" / "hooks").mkdir(parents=True)
    shutil.copy(HOOK, project / ".claude" / "hooks" / "log_event.py")
    cmd = _commands(event)[0]["command"]
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    stdin = json.dumps({"hook_event_name": event, "session_id": "s", "transcript_path": "",
                        "last_assistant_message": "x"})
    proc = subprocess.run(["/bin/sh", "-c", cmd], input=stdin, text=True,
                          capture_output=True, env=env, timeout=30)
    assert proc.returncode == 0 and proc.stdout == ""
    assert [e["event"] for e in events(project)] == [event]
