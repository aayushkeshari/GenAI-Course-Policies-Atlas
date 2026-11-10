"""Shared helpers for the P5 provenance tests: a tiny fixture project (git repo + hook log + progress and review logs)."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
TIMELINE = SITE / "data" / "timeline.json"

S1, S2 = "aaaaaaaa-1111", "bbbbbbbb-2222"
FAKE_HOME = "/Users/someone"  # fixture string: must be redacted, never published

EVENTS = [
    # ts, event, session, phase, payload
    ("2026-01-01T09:00:00.000-05:00", "SessionStart", S1, "P0:planning", {"source": "startup"}),
    ("2026-01-01T09:01:00.000-05:00", "UserPromptSubmit", S1, "P0:planning", {"prompt": "Typed by me: plan P0 please"}),
    ("2026-01-01T09:02:00.000-05:00", "Stop", S1, "P0:planning", {"response_excerpt": "Here is the P0 plan."}),
    ("2026-01-01T09:03:00.000-05:00", "UserPromptSubmit", S1, "P0:planning",
     {"prompt": "<task-notification>subagent finished</task-notification>"}),
    # S2 interleaves with S1: its prompt is answered by S2's Stop, never by S1's
    ("2026-01-01T09:04:00.000-05:00", "UserPromptSubmit", S2, "P0:writing-code",
     {"prompt": f"\n\n<pasted_content id=\"x\">\nlook at {FAKE_HOME}/secret.txt and mail a@b.org\n</pasted_content>"}),
    ("2026-01-01T09:05:00.000-05:00", "Stop", S1, "P0:planning", {"response_excerpt": "Noted the subagent report."}),
    ("2026-01-01T09:06:00.000-05:00", "Stop", S2, "P0:writing-code",
     {"response_excerpt": "Done. key sk-" + "A" * 24 + " was in the paste"}),
    ("2026-01-01T09:07:00.000-05:00", "UserPromptSubmit", S2, "P1:planning", {"prompt": "git push"}),
    ("2026-01-01T09:08:00.000-05:00", "SessionEnd", S2, "P1:planning", {"reason": "clear"}),
]

PROGRESS = """# Progress log

## 2026-01-01T09:02:30-05:00 — [P0] Step 1: plan
- HUMAN: approve the plan.
- HUMAN: second approval. AGENT: one agent decision.
- Prose that mentions `HUMAN:` in backticks is not a tag.
- REJECTED: the first layout.
Prose about rejected plans (REJECTED: tags) is not a tag either.
"""

REVIEW_COMMITTED = "## 2026-01-01 — P0 instrumentation"
REVIEW_UNCOMMITTED = "## 2026-01-02 — P1 synthetic data"

COMMITS = [
    # ts, subject, files {path: content}
    ("2026-01-01T08:00:00-05:00", "claude-chat: draft specs", {"specs/P0-x.md": "a\nb\n"}),
    ("2026-01-01T08:30:00-05:00", "human: import specs", {"specs/P0-x.md": "a\nb\nc\n", "README.md": "r\n"}),
    ("2026-01-01T09:02:45-05:00", "agent: P0 step 1 — code", {"src/x.py": "1\n2\n3\n", "results/big.json": "x\n" * 50,
                                                            "specs/P1-y.md": "y\n"}),
    ("2026-01-01T09:06:30-05:00", "agent: fix without a phase tag", {"src/x.py": "1\n2\n"}),
    ("2026-01-01T09:30:00-05:00", "human: P0 review-log entry", {"docs/review-log.md": REVIEW_COMMITTED + "\n- ok\n"}),
]


def _git(repo, *args, env=None):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def make_project(root: Path) -> Path:
    """Build the fixture project under `root` and return it."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Fixture")
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    for ts, subject, files in COMMITS:
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
        _git(root, "add", "-A")
        env = {**os.environ, "GIT_AUTHOR_DATE": ts, "GIT_COMMITTER_DATE": ts}
        _git(root, "commit", "-q", "-m", subject, env=env)
    (root / "logs").mkdir(exist_ok=True)
    (root / "logs" / "events.jsonl").write_text("".join(
        json.dumps({"ts": ts, "event": ev, "session_id": s, "phase": ph, "payload": p}) + "\n"
        for ts, ev, s, ph, p in EVENTS))
    (root / "docs" / "progress.md").write_text(PROGRESS)
    (root / "docs" / "review-log.md").write_text(f"# Review log\n\n{REVIEW_COMMITTED}\n- ok\n\n{REVIEW_UNCOMMITTED}\n- later\n")
    return root
