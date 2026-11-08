"""Shared helpers for tests that run .claude/hooks/log_event.py as a subprocess."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "log_event.py"


def load_hook_module():
    """Import log_event.py as a module (for unit-testing redact() directly)."""
    spec = importlib.util.spec_from_file_location("log_event", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_hook(project, stdin, hook=HOOK):
    """Run the hook with CLAUDE_PROJECT_DIR=project. stdin may be a dict (sent as JSON) or a raw str."""
    if not isinstance(stdin, str):
        stdin = json.dumps(stdin)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    return subprocess.run([sys.executable, str(hook)], input=stdin, capture_output=True,
                          text=True, env=env, timeout=30)


def events(project):
    path = Path(project) / "logs" / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def errors(project):
    path = Path(project) / "logs" / "hook_errors.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""
