"""INST-05: the confirmed hooks-docs fields are recorded in docs/progress.md before the hook was built.

This is a documentary check. Aayush also verifies it by hand and logs that in docs/review-log.md.
"""
import re

import pytest

from hookutil import ROOT

PROGRESS = ROOT / "docs" / "progress.md"


def section():
    text = PROGRESS.read_text(encoding="utf-8")
    m = re.search(r"^### Hooks docs confirmed\n(.*?)(?=^#{2,3} )", text, re.S | re.M)
    assert m, "no '### Hooks docs confirmed' section in docs/progress.md"
    return text, m


@pytest.mark.req("INST-05")
@pytest.mark.parametrize("event,field", [
    ("UserPromptSubmit", "prompt"), ("Stop", "last_assistant_message"),
    ("PreCompact", "trigger"), ("SessionStart", "source"), ("SessionEnd", "reason"),
])
def test_section_records_each_event_and_its_field(event, field):
    """The 'Hooks docs confirmed' section names each hooked event and the stdin field
    log_event.py reads for it, so the field names were checked against the docs and not guessed."""
    _, m = section()
    body = m.group(1)
    assert f"**{event}**" in body
    line = next(l for l in body.splitlines() if f"**{event}**" in l)
    assert f"`{field}`" in line


@pytest.mark.req("INST-05")
def test_section_records_common_fields_and_project_dir_quoting():
    """The section records the common stdin fields (session_id, transcript_path,
    hook_event_name) and the confirmed $CLAUDE_PROJECT_DIR quoting rule."""
    _, m = section()
    for f in ("session_id", "transcript_path", "hook_event_name", "$CLAUDE_PROJECT_DIR"):
        assert f in m.group(1)


@pytest.mark.req("INST-05")
def test_docs_check_logged_before_hook_was_written():
    """The docs check comes earlier in the append-only log than the entry that wrote
    log_event.py: 'before writing the hook' really happened first."""
    text, m = section()
    hook_entry = re.search(r"^## .*log_event\.py", text, re.M)
    assert hook_entry and m.start() < hook_entry.start()
