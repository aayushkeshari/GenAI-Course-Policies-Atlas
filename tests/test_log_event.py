"""INST-02/03/04/08: log_event.py behavior, by running it as a subprocess on sample hook JSON."""
import json
import os
from datetime import datetime

import pytest

from hookutil import errors, events, run_hook


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".phase").write_text("P0:test\n")
    return tmp_path


def sample(event, **fields):
    base = {"session_id": "sess-1", "transcript_path": "", "cwd": "/tmp",
            "permission_mode": "default", "hook_event_name": event}
    return {**base, **fields}


def write_transcript(path, entries):
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


def ok(proc):
    """INST-03 invariants that hold for every invocation."""
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""


# ---------- INST-02 / INST-08: one sample per event type ----------

@pytest.mark.req("INST-02", "INST-08")
def test_record_has_exact_schema_and_local_iso_ts(project):
    """A record has exactly {ts, event, session_id, phase, payload}, and ts is ISO 8601 with a
    timezone offset (local tz, not naive)."""
    ok(run_hook(project, sample("SessionStart", source="startup")))
    [rec] = events(project)
    assert set(rec) == {"ts", "event", "session_id", "phase", "payload"}
    ts = datetime.fromisoformat(rec["ts"])
    assert ts.tzinfo is not None
    assert ts.utcoffset() == datetime.now().astimezone().utcoffset()
    assert rec["event"] == "SessionStart" and rec["session_id"] == "sess-1"
    assert rec["phase"] == "P0:test"


@pytest.mark.req("INST-02", "INST-08")
def test_user_prompt_submit_logs_full_prompt_untruncated(project):
    """UserPromptSubmit stores the full prompt text (5,000+ chars, multi-line, unicode) unchanged."""
    prompt = "Line one ✓\n" + "x" * 5000 + "\n\"quoted\""
    ok(run_hook(project, sample("UserPromptSubmit", prompt=prompt)))
    assert events(project)[0]["payload"] == {"prompt": prompt}


@pytest.mark.req("INST-02", "INST-08")
def test_stop_uses_last_assistant_message_first_1000_chars(project):
    """Stop stores the first 1,000 characters of last_assistant_message as response_excerpt."""
    msg = "".join(chr(ord("a") + i % 26) for i in range(2500))
    ok(run_hook(project, sample("Stop", last_assistant_message=msg, stop_hook_active=False)))
    assert events(project)[0]["payload"] == {"response_excerpt": msg[:1000]}


@pytest.mark.req("INST-02", "INST-08")
def test_stop_falls_back_to_last_assistant_text_in_transcript(project, tmp_path):
    """With no last_assistant_message, Stop takes the text of the LAST assistant entry in
    transcript_path. It ignores tool_use blocks, user entries, and blank or corrupt lines."""
    t = write_transcript(tmp_path / "t.jsonl", [
        {"type": "user", "message": {"role": "user", "content": "q1"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "old answer"}]}},
        {"type": "user", "message": {"role": "user", "content": "q2"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "new "},
                                                      {"type": "tool_use", "name": "Bash"},
                                                      {"type": "text", "text": "answer"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}},
    ])
    with open(t, "a") as f:
        f.write("{not json\n\n")
    ok(run_hook(project, sample("Stop", transcript_path=str(t))))
    assert events(project)[0]["payload"] == {"response_excerpt": "new \nanswer"}


@pytest.mark.req("INST-02", "INST-08")
@pytest.mark.parametrize("trigger", ["manual", "auto"])
def test_precompact_logs_trigger(project, trigger):
    """PreCompact stores payload.trigger (manual/auto)."""
    ok(run_hook(project, sample("PreCompact", trigger=trigger, custom_instructions=None)))
    assert events(project)[0]["payload"] == {"trigger": trigger}


@pytest.mark.req("INST-02", "INST-08")
@pytest.mark.parametrize("source", ["startup", "resume", "clear", "compact", "fork"])
def test_session_start_logs_source(project, source):
    """SessionStart stores payload.source for every documented value, fork included."""
    ok(run_hook(project, sample("SessionStart", source=source)))
    assert events(project)[0]["payload"] == {"source": source}


@pytest.mark.req("INST-02", "INST-08")
@pytest.mark.parametrize("reason", ["clear", "resume", "logout", "prompt_input_exit", "other"])
def test_session_end_logs_reason(project, reason):
    """SessionEnd stores payload.reason for every documented value."""
    ok(run_hook(project, sample("SessionEnd", reason=reason)))
    assert events(project)[0]["payload"] == {"reason": reason}


@pytest.mark.req("INST-02", "INST-08")
@pytest.mark.kind("integration")
def test_manual_check_sequence_appends_in_order(project):
    """Simulates Aayush's manual check (start, 3 prompts with replies, /compact, /clear) and
    checks events.jsonl has one line per event, in order, all tagged with the phase."""
    seq = [sample("SessionStart", source="startup")]
    for i in range(3):
        seq += [sample("UserPromptSubmit", prompt=f"p{i}"),
                sample("Stop", last_assistant_message=f"r{i}")]
    seq += [sample("PreCompact", trigger="manual"), sample("SessionStart", source="compact"),
            sample("SessionEnd", reason="clear"),
            sample("SessionStart", source="clear", session_id="sess-2")]
    for s in seq:
        ok(run_hook(project, s))
    recs = events(project)
    assert [r["event"] for r in recs] == [s["hook_event_name"] for s in seq]
    assert {r["phase"] for r in recs} == {"P0:test"}
    assert [r["ts"] for r in recs] == sorted(r["ts"] for r in recs)


@pytest.mark.req("INST-02")
@pytest.mark.parametrize("content", [None, "", "  \n\t"])
def test_phase_is_untagged_when_phase_file_missing_or_blank(tmp_path, content):
    """phase is "untagged" when .phase is missing, empty, or whitespace. Otherwise it is the
    file's contents, stripped."""
    if content is not None:
        (tmp_path / ".phase").write_text(content)
    ok(run_hook(tmp_path, sample("SessionStart", source="startup")))
    assert events(tmp_path)[0]["phase"] == "untagged"


@pytest.mark.req("INST-02")
def test_phase_change_takes_effect_on_next_event(project):
    """.phase is read on every event, so editing it retags later events without a restart."""
    ok(run_hook(project, sample("UserPromptSubmit", prompt="a")))
    (project / ".phase").write_text("P1:build")
    ok(run_hook(project, sample("UserPromptSubmit", prompt="b")))
    assert [e["phase"] for e in events(project)] == ["P0:test", "P1:build"]


# ---------- INST-03: never blocks ----------

@pytest.mark.req("INST-03")
@pytest.mark.kind("recovery")
@pytest.mark.parametrize("stdin", ["", "{not json", "[1, 2]", "null"])
def test_bad_input_exits_0_silently_and_logs_error(project, stdin):
    """Empty, malformed, or non-object input still exits 0 with empty stdout. The failure is
    written to logs/hook_errors.log and nothing is added to events.jsonl."""
    ok(run_hook(project, stdin))
    assert events(project) == []
    assert "Traceback" in errors(project)


@pytest.mark.req("INST-03")
@pytest.mark.kind("recovery")
def test_unreadable_transcript_on_stop_still_logs_event(project, tmp_path):
    """A Stop with no last_assistant_message and a transcript_path that doesn't exist still
    logs the event (empty excerpt), exits 0, and records the error."""
    ok(run_hook(project, sample("Stop", transcript_path=str(tmp_path / "missing.jsonl"))))
    assert events(project)[0]["payload"] == {"response_excerpt": ""}
    assert "could not read transcript" in errors(project)


@pytest.mark.req("INST-03")
@pytest.mark.kind("recovery")
def test_unwritable_logs_dir_still_exits_0(project):
    """If logs/ can't be created (a regular file sits in its place), so neither log can be
    written, the hook still exits 0 with no stdout."""
    (project / "logs").write_text("i am a file")
    ok(run_hook(project, sample("UserPromptSubmit", prompt="hi")))


@pytest.mark.req("INST-03")
def test_unknown_event_is_logged_with_empty_payload(project):
    """An event the hook doesn't know about is still logged (empty payload), not dropped or crashed."""
    ok(run_hook(project, sample("Notification", message="m")))
    assert events(project)[0]["event"] == "Notification"
    assert events(project)[0]["payload"] == {}


@pytest.mark.req("INST-03")
def test_hook_does_not_import_third_party_packages():
    """log_event.py imports only standard-library modules, so it runs under any system
    python3, outside the venv."""
    import ast
    import sys
    from hookutil import HOOK
    tree = ast.parse(HOOK.read_text())
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert names <= set(sys.stdlib_module_names), names - set(sys.stdlib_module_names)


# ---------- INST-04: transcript copies ----------

@pytest.mark.req("INST-04")
@pytest.mark.parametrize("event,extra", [("PreCompact", {"trigger": "manual"}),
                                         ("SessionEnd", {"reason": "clear"})])
def test_transcript_copied_verbatim_to_raw_logs(project, tmp_path, event, extra):
    """On PreCompact and SessionEnd, the transcript is copied byte-for-byte to
    raw_logs/transcripts/<session_id>.jsonl. It is not redacted, because raw_logs/ is gitignored."""
    t = write_transcript(tmp_path / "t.jsonl", [{"type": "user", "message": {"content": "me@x.com"}}])
    ok(run_hook(project, sample(event, transcript_path=str(t), **extra)))
    copy = project / "raw_logs" / "transcripts" / "sess-1.jsonl"
    assert copy.read_bytes() == t.read_bytes()


@pytest.mark.req("INST-04")
def test_later_copy_replaces_earlier_with_superset(project, tmp_path):
    """A PreCompact copy followed by a SessionEnd copy of the grown transcript leaves the latest
    (superset) contents in one file per session."""
    t = write_transcript(tmp_path / "t.jsonl", [{"n": 1}])
    ok(run_hook(project, sample("PreCompact", transcript_path=str(t), trigger="auto")))
    write_transcript(t, [{"n": 1}, {"n": 2}])
    ok(run_hook(project, sample("SessionEnd", transcript_path=str(t), reason="other")))
    files = list((project / "raw_logs" / "transcripts").iterdir())
    assert [f.name for f in files] == ["sess-1.jsonl"]
    assert files[0].read_bytes() == t.read_bytes()


@pytest.mark.req("INST-04")
@pytest.mark.parametrize("event", ["UserPromptSubmit", "Stop", "SessionStart"])
def test_other_events_do_not_copy(project, tmp_path, event):
    """Only PreCompact and SessionEnd copy transcripts. Other events leave raw_logs/ alone."""
    t = write_transcript(tmp_path / "t.jsonl", [{"n": 1}])
    ok(run_hook(project, sample(event, transcript_path=str(t), prompt="p",
                                last_assistant_message="r", source="startup")))
    assert not (project / "raw_logs").exists()


@pytest.mark.req("INST-04")
def test_session_id_is_sanitized_into_filename(project, tmp_path):
    """A session_id containing path separators can't write outside raw_logs/transcripts/."""
    t = write_transcript(tmp_path / "t.jsonl", [{"n": 1}])
    ok(run_hook(project, sample("SessionEnd", transcript_path=str(t), reason="other",
                                session_id="../../evil")))
    assert [f.name for f in (project / "raw_logs" / "transcripts").iterdir()] == ["______evil.jsonl"]
    assert not (project.parent / "evil.jsonl").exists()


@pytest.mark.req("INST-04", "INST-03")
@pytest.mark.kind("recovery")
def test_missing_transcript_on_copy_logs_error_but_keeps_event(project, tmp_path):
    """If the transcript to copy doesn't exist, the event is still logged, the hook exits 0,
    and the copy failure goes to hook_errors.log."""
    ok(run_hook(project, sample("SessionEnd", transcript_path=str(tmp_path / "nope.jsonl"),
                                reason="logout")))
    assert events(project)[0]["payload"] == {"reason": "logout"}
    assert "could not copy transcript" in errors(project)


@pytest.mark.req("INST-04")
def test_subagent_transcripts_are_copied_with_the_session(project, tmp_path):
    """INST-04 (amended): the session's subagent transcripts (<transcript>/subagents/*.jsonl and *.meta.json) are
    copied verbatim to raw_logs/transcripts/subagents/<session_id>/ next to the session copy; other files are not."""
    t = write_transcript(tmp_path / "t.jsonl", [{"n": 1}])
    sub = tmp_path / "t" / "subagents"
    sub.mkdir(parents=True)
    write_transcript(sub / "agent-x.jsonl", [{"type": "assistant", "isSidechain": True}])
    (sub / "agent-x.meta.json").write_text('{"agentType": "web-fetch"}')
    (sub / "notes.txt").write_text("not a transcript")
    ok(run_hook(project, sample("SessionEnd", transcript_path=str(t), reason="clear")))
    dest = project / "raw_logs" / "transcripts" / "subagents" / "sess-1"
    assert sorted(f.name for f in dest.iterdir()) == ["agent-x.jsonl", "agent-x.meta.json"]
    assert (dest / "agent-x.jsonl").read_bytes() == (sub / "agent-x.jsonl").read_bytes()


@pytest.mark.req("INST-04")
def test_backfill_copies_subagent_transcripts_still_on_disk(project, tmp_path):
    """`log_event.py --backfill-subagents` finds this project's folder under the Claude config dir (project path with
    non-alphanumerics as '-'), copies every session's subagent transcripts, prints nothing to stdout, and exits 0."""
    import os
    import subprocess
    import sys
    from hookutil import HOOK
    import re
    config = tmp_path / "cfg"
    sub = config / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(project)) / "sess-9" / "subagents"
    sub.mkdir(parents=True)
    write_transcript(sub / "agent-y.jsonl", [{"n": 1}])
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project), "CLAUDE_CONFIG_DIR": str(config)}
    proc = subprocess.run([sys.executable, str(HOOK), "--backfill-subagents"], capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0 and proc.stdout == "" and "copied 1 subagent files" in proc.stderr
    assert (project / "raw_logs" / "transcripts" / "subagents" / "sess-9" / "agent-y.jsonl").exists()
    assert not (project / "logs").exists()  # backfill writes no events
