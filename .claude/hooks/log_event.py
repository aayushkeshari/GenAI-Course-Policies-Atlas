#!/usr/bin/env python3
"""Claude Code hook: append one redacted JSON line per event to logs/events.jsonl.

Registered in .claude/settings.json for UserPromptSubmit, Stop, PreCompact, SessionStart
and SessionEnd (INST-01). It uses only the standard library, because Claude Code runs it
with the system python3, outside the project venv.

Guarantees (INST-03): it always exits 0, never writes to stdout (on UserPromptSubmit and
SessionStart stdout is injected into Claude's context), and logs its own errors to
logs/hook_errors.log.
"""
import json
import os
import re
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

EXCERPT_LEN = 1000
COPY_EVENTS = {"PreCompact", "SessionEnd"}

# INST-09: applied to every string before it is written to logs/. Order matters: tokens
# first (a token could contain '@'), then emails, then home paths.
_TOKEN = "[REDACTED_TOKEN]"
REDACTIONS = [
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE), _TOKEN),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}"), _TOKEN),
    (re.compile(r"\bghp_[A-Za-z0-9]{16,}"), _TOKEN),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), _TOKEN),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"(?<![\w.-])/(?:Users|home)/[^/\s\"'`]+"), "~"),
]


def redact(value):
    """Return value with every string in it (recursively) scrubbed of secrets and home paths."""
    if isinstance(value, str):
        for pattern, replacement in REDACTIONS:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def project_dir():
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def read_phase(root):
    try:
        phase = (root / ".phase").read_text(encoding="utf-8").strip()
    except OSError:
        return "untagged"
    return phase or "untagged"


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def log_error(root, message):
    """Best effort: append a redacted error entry. Never raises."""
    try:
        logs = root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with open(logs / "hook_errors.log", "a", encoding="utf-8") as f:
            f.write(f"--- {now_iso()}\n{redact(message).rstrip()}\n")
    except Exception:
        pass


def last_assistant_text(transcript_path):
    """Text of the last assistant entry in a transcript JSONL that has any text content."""
    lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant":
            continue
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, str):
            parts = [content]
        elif isinstance(content, list):
            parts = [c.get("text", "") for c in content
                     if isinstance(c, dict) and c.get("type") == "text"]
        else:
            parts = []
        text = "\n".join(p for p in parts if p)
        if text:
            return text
    return ""


def build_payload(event, data, root):
    if event == "UserPromptSubmit":
        return {"prompt": data.get("prompt", "")}
    if event == "Stop":
        text = data.get("last_assistant_message")
        if not isinstance(text, str):
            text = ""
            path = data.get("transcript_path")
            if path:
                try:
                    text = last_assistant_text(path)
                except Exception:
                    log_error(root, f"Stop: could not read transcript {path}\n{traceback.format_exc()}")
        # Redact before truncating so a secret cut at the boundary can't slip through.
        return {"response_excerpt": redact(text)[:EXCERPT_LEN]}
    if event == "PreCompact":
        return {"trigger": data.get("trigger")}
    if event == "SessionStart":
        return {"source": data.get("source")}
    if event == "SessionEnd":
        return {"reason": data.get("reason")}
    return {}


def copy_transcript(root, data):
    """INST-04: keep a verbatim copy (raw_logs/ is gitignored, so it is not redacted)."""
    src = data.get("transcript_path")
    if not src:
        log_error(root, f"{data.get('hook_event_name')}: no transcript_path in input")
        return
    session = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id") or "unknown"))
    dest_dir = root / "raw_logs" / "transcripts"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Transcripts are append-only, so the newest copy contains every earlier one.
        shutil.copyfile(src, dest_dir / f"{session}.jsonl")
    except Exception:
        log_error(root, f"could not copy transcript {src}\n{traceback.format_exc()}")
    copy_subagents(root, Path(src).with_suffix("") / "subagents", session)


def copy_subagents(root, sub_dir, session):
    """INST-04 (amended): also copy the session's subagent transcripts (<transcript>/subagents/agent-*.jsonl and
    their .meta.json) to raw_logs/transcripts/subagents/<session>/. Nothing is created when there are none."""
    try:
        files = sorted(f for f in Path(sub_dir).iterdir()
                       if f.is_file() and (f.suffix == ".jsonl" or f.name.endswith(".meta.json"))) \
            if Path(sub_dir).is_dir() else []
        if not files:
            return 0
        dest = root / "raw_logs" / "transcripts" / "subagents" / session
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copyfile(f, dest / re.sub(r"[^A-Za-z0-9_.-]", "_", f.name))
        return len(files)
    except Exception:
        log_error(root, f"could not copy subagent transcripts from {sub_dir}\n{traceback.format_exc()}")
        return 0


def backfill_subagents(root):
    """One-off: copy every subagent transcript of this project still on disk (Claude Code keeps them under
    <config dir>/projects/<project path with non-alphanumerics as '-'>/<session>/subagents/)."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    proj = config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root))
    total = 0
    if proj.is_dir():
        for sess in sorted(d for d in proj.iterdir() if d.is_dir()):
            total += copy_subagents(root, sess / "subagents", re.sub(r"[^A-Za-z0-9_-]", "_", sess.name))
    return total


def main():
    root = project_dir()
    raw = ""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("hook input is not a JSON object")
        event = data.get("hook_event_name") or "unknown"
        record = {
            "ts": now_iso(),
            "event": event,
            "session_id": data.get("session_id"),
            "phase": read_phase(root),
            "payload": build_payload(event, data, root),
        }
        line = json.dumps(redact(record), ensure_ascii=False) + "\n"
        logs = root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with open(logs / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(line)
        if event in COPY_EVENTS:
            copy_transcript(root, data)
    except Exception:
        log_error(root, f"{traceback.format_exc()}input (first 300 chars): {raw[:300]!r}")


if __name__ == "__main__":
    # Belt and braces for INST-03: nothing this process does can reach stdout.
    sys.stdout = open(os.devnull, "w")
    try:
        if sys.argv[1:] == ["--backfill-subagents"]:  # run by hand, never by Claude Code's hook config
            sys.stderr.write(f"copied {backfill_subagents(project_dir())} subagent files\n")
        else:
            main()
    finally:
        os._exit(0)
