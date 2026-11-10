"""PROV-01..06: build site/timeline/data/timeline.json from logs/events.jsonl, git log, docs/progress.md and docs/review-log.md.

Run with `make timeline`. Reads only; never writes logs/ or raw_logs/ (hooks own them).

Actor rules (PROV-02) are a fixed table keyed by source, never inferred from wording:
  prompts, `human:` commits, review-log entries, spec edits    -> HUMAN
  responses, `agent:` commits, progress entries (agent-written) -> CLAUDE
  anything else (other commit prefixes, session events)         -> shared
A spec edit made in a commit that is neither `agent:` nor `human:` (e.g. the early `claude-chat:` commits) is
ambiguous about who wrote it, so it is "shared" too.

Every text field is passed through src.validation.redact.scrub before it is written (PROV-06).
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema

from src.validation.redact import scrub

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site" / "timeline" / "data" / "timeline.json"
SCHEMA = Path(__file__).with_name("timeline.schema.json")
NARRATIVE = "docs/timeline-narrative.md"

ACTORS = ["HUMAN", "CLAUDE", "shared"]
TYPES = ["prompt", "response", "session", "commit", "spec_edit", "progress", "review"]
CATEGORIES = ["human-typed", "automated", "shared"]

# PROV-02 prompt categories. Order matters: first match wins; no match -> "shared" (never guess).
HUMAN_TYPED_MARKER = "Typed by me"
AUTOMATED_PREFIXES = (  # tags Claude Code wraps around machine-sent prompts (AGENT decision: extend if new ones appear)
    "<task-notification",       # a background subagent's report
    "<scheduled-task",          # a scheduled / cron-fired prompt
    "<cross-session-message",   # a message from another session
    "<teammate-message",        # a message from a teammate agent
)

# Files excluded from "lines changed": hook-owned logs and generated outputs (rebuilt by make targets).
GENERATED_PREFIXES = ("logs/", "raw_logs/", "data/", "results/", "site/data/", "site/validation/data/", "site/timeline/data/")

# REJECTED: tags were added to CLAUDE.md's logging rules at this time; earlier rejections were not recorded.
REJECTED_RECORDED_SINCE = "2026-11-10T14:27:58-05:00"
TAG = r"(?<![`\w]){}:(?!`)"
REJECTED_TAG = r"(?m)^\s*[-*]\s+REJECTED:"  # a bullet that starts with the tag; prose mentions don't count
SUMMARY_LEN = 160
TEXT_LEN = 4000


# ---------- helpers ----------
def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def epoch_ms(ts: str) -> int:
    return int(parse_ts(ts).timestamp() * 1000)


def one_line(text: str, n: int = SUMMARY_LEN) -> str:
    text = re.sub(r"</?pasted_content[^>]*>", " ", text)
    line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    line = re.sub(r"\s+", " ", line)
    return line if len(line) <= n else line[: n - 1].rstrip() + "…"


def phase_of(label: str | None) -> tuple[str, str]:
    """'P3:writing-code' -> ('P3', 'writing-code'); anything unparseable -> ('unknown', '')."""
    m = re.match(r"^(P\d)(?::(.*))?$", (label or "").strip())
    return (m.group(1), m.group(2) or "") if m else ("unknown", "")


def classify_prompt(text: str) -> str:
    """PROV-02 prompt category. Exact prefix rules only; anything else is 'shared'."""
    s = text.lstrip()
    if s.startswith(HUMAN_TYPED_MARKER):
        return "human-typed"
    if s.startswith(AUTOMATED_PREFIXES):
        return "automated"
    return "shared"


def commit_actor(subject: str) -> str:
    if subject.startswith("agent:"):
        return "CLAUDE"
    if subject.startswith("human:"):
        return "HUMAN"
    return "shared"


def spec_edit_actor(subject: str) -> str:
    """Spec edits are HUMAN (PROV-02), including ones Claude typed into an `agent:` commit on Aayush's instruction.
    In a commit with neither prefix the author is ambiguous -> shared."""
    return "HUMAN" if subject.startswith(("agent:", "human:")) else "shared"


def item(id_, ts, actor, phase, type_, summary, source, **extra):
    d = {"id": id_, "ts": ts, "t": epoch_ms(ts), "actor": actor, "phase": phase, "type": type_,
         "summary": scrub(summary), "source": source}
    for k, v in extra.items():
        d[k] = scrub(v) if isinstance(v, str) else v
    return d


# ---------- sources ----------
def read_events(path: Path, rel: str = "logs/events.jsonl") -> list[dict]:
    items = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        e = json.loads(line)
        ev, p = e.get("event"), e.get("payload") or {}
        phase, stage = phase_of(e.get("phase"))
        common = dict(stage=stage, session=e.get("session_id", "")[:8])
        src = f"{rel}:{n}"
        if ev == "UserPromptSubmit":
            text = p.get("prompt", "")
            items.append(item(f"ev{n}", e["ts"], "HUMAN", phase, "prompt", one_line(text) or "(empty prompt)", src,
                              category=classify_prompt(text), text=text[:TEXT_LEN], **common))
        elif ev == "Stop":
            text = p.get("response_excerpt", "")
            items.append(item(f"ev{n}", e["ts"], "CLAUDE", phase, "response", one_line(text) or "(no text logged)", src,
                              text=text[:TEXT_LEN], **common))
        else:
            detail = p.get("source") or p.get("reason") or p.get("trigger") or ""
            label = {"SessionStart": "Session started", "SessionEnd": "Session ended",
                     "PreCompact": "Context compacted"}.get(ev, ev or "event")
            items.append(item(f"ev{n}", e["ts"], "shared", phase, "session",
                              f"{label} ({detail})" if detail else label, src, **common))
    return items


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def read_git(repo: Path) -> list[dict]:
    """Commits oldest first: sha, ts, subject, and per-file numstat."""
    out = git(repo, "log", "--reverse", "--format=%x1e%H%x1f%aI%x1f%s", "--numstat")
    commits = []
    for block in out.split("\x1e")[1:]:
        head, *rest = block.split("\n")
        sha, ts, subject = head.split("\x1f")
        files = []
        for line in rest:
            parts = line.split("\t")
            if len(parts) == 3:
                a, r, f = parts
                files.append({"file": f, "added": int(a) if a.isdigit() else 0, "removed": int(r) if r.isdigit() else 0})
        commits.append({"sha": sha, "ts": ts, "subject": subject, "files": files})
    return commits


def commit_phase(subject: str, ts: str, event_phases: list[tuple[int, str]]) -> str:
    """The phase named in the subject ('agent: P4 — …', 'agent: checkpoint P4 …'); otherwise the .phase that the most
    recent earlier hook event recorded; otherwise 'unknown'."""
    m = re.match(r"^\w[\w-]*:\s*(?:checkpoint\s+)?(?:\[)?(P\d)\b", subject)
    if m:
        return m.group(1)
    t = epoch_ms(ts)
    before = [ph for et, ph in event_phases if et <= t]
    return before[-1] if before else "unknown"


def git_items(commits: list[dict], event_phases) -> list[dict]:
    items = []
    for c in commits:
        sha7 = c["sha"][:7]
        phase = commit_phase(c["subject"], c["ts"], event_phases)
        changed = [f for f in c["files"] if not f["file"].startswith(GENERATED_PREFIXES)]
        items.append(item(f"git-{sha7}", c["ts"], commit_actor(c["subject"]), phase, "commit", c["subject"],
                          f"git {sha7}", sha=c["sha"], files=len(c["files"]),
                          added=sum(f["added"] for f in changed), removed=sum(f["removed"] for f in changed)))
        for f in c["files"]:
            if re.match(r"^specs/[^/]+\.md$", f["file"]):
                items.append(item(f"spec-{sha7}-{Path(f['file']).stem}", c["ts"], spec_edit_actor(c["subject"]), phase,
                                  "spec_edit", f"{f['file']}: +{f['added']} / −{f['removed']}",
                                  f"git {sha7}", sha=c["sha"], file=f["file"], added=f["added"], removed=f["removed"]))
    return items


PROGRESS_HEAD = re.compile(r"^## (\d{4}-\d\d-\d\dT[\d:]+[+-]\d\d:\d\d) — \[(P\d)[^\]]*\] (.+)$")


def read_progress(path: Path, rel: str = "docs/progress.md") -> list[dict]:
    items = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = PROGRESS_HEAD.match(line)
        if m:
            items.append(item(f"prog{n}", m.group(1), "CLAUDE", m.group(2), "progress", m.group(3), f"{rel}:{n}"))
    return items


REVIEW_HEAD = re.compile(r"^## (\d{4}-\d\d-\d\d)\b\W*(.+)$")


def read_review_log(path: Path, repo: Path, rel: str = "docs/review-log.md") -> list[dict]:
    """Review-log headings carry only a date. The entry's time is the commit that first added its heading;
    if it was never committed, the end of that day (ts_precision 'day')."""
    items = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = REVIEW_HEAD.match(line)
        if not m:
            continue
        added = git(repo, "log", "--reverse", "--format=%aI", "-S", line, "--", rel).split()
        if added:
            ts, precision = added[0], "commit"
        else:
            ts, precision = f"{m.group(1)}T23:59:59+00:00", "day"
        pm = re.search(r"\bP(\d)\b", m.group(2))
        items.append(item(f"rev{n}", ts, "HUMAN", f"P{pm.group(1)}" if pm else "unknown", "review", m.group(2),
                          f"{rel}:{n}", ts_precision=precision))
    return items


# ---------- PROV-04 pairing ----------
def pair_qa(items: list[dict]) -> None:
    """Each prompt gets `reply`: the id of the first response in the same session after it and before that session's
    next prompt; null when none was logged. Never pairs across sessions."""
    open_prompt: dict[str, dict] = {}
    for it in items:  # items are sorted by time
        if it["type"] == "prompt":
            it["reply"] = None
            open_prompt[it["session"]] = it
        elif it["type"] == "response":
            p = open_prompt.pop(it["session"], None)
            if p is not None:
                p["reply"] = it["id"]
                it["reply_to"] = p["id"]


# ---------- PROV-05 summary ----------
def summarize(items: list[dict], progress_text: str) -> dict:
    def count(type_, actor):
        return sum(1 for i in items if i["type"] == type_ and i["actor"] == actor)

    per = {}
    for a in ACTORS:
        commits = [i for i in items if i["type"] == "commit" and i["actor"] == a]
        per[a] = {"prompts": count("prompt", a), "responses": count("response", a),
                  "spec_edits": count("spec_edit", a), "reviews": count("review", a), "commits": len(commits),
                  "lines_added": sum(c["added"] for c in commits), "lines_removed": sum(c["removed"] for c in commits),
                  "approvals": None, "rejected_plans": None}
    per["HUMAN"]["approvals"] = len(re.findall(TAG.format("HUMAN"), progress_text))
    per["HUMAN"]["rejected_plans"] = len(re.findall(REJECTED_TAG, progress_text))
    cats = {c: sum(1 for i in items if i["type"] == "prompt" and i["category"] == c) for c in CATEGORIES}
    prompts = [i for i in items if i["type"] == "prompt"]
    return {
        "per_actor": per,
        "prompt_categories": cats,
        "agent_decisions": len(re.findall(TAG.format("AGENT"), progress_text)),
        "qa_pairs": sum(1 for p in prompts if p["reply"]),
        "unanswered_prompts": sum(1 for p in prompts if not p["reply"]),
        "rules": {
            "approvals": "Count of HUMAN decision tags in docs/progress.md.",
            "rejected_plans": f"Count of bullets starting with REJECTED: in docs/progress.md. Rejections before {REJECTED_RECORDED_SINCE[:10]} were not recorded.",
            "rejected_recorded_since": REJECTED_RECORDED_SINCE,
            "lines_changed": "Lines added/removed by each actor's commits (agent: → CLAUDE, human: → HUMAN, other → shared), "
                             "excluding generated or hook-owned paths: " + ", ".join(GENERATED_PREFIXES),
            "human_typed_marker": HUMAN_TYPED_MARKER,
            "automated_prefixes": list(AUTOMATED_PREFIXES),
        },
    }


# ---------- build ----------
def build(root: Path = ROOT, out: Path | None = OUT) -> dict:
    events = read_events(root / "logs" / "events.jsonl")
    event_phases = sorted((i["t"], i["phase"]) for i in events)
    commits = read_git(root)
    items = events + git_items(commits, event_phases) + read_progress(root / "docs" / "progress.md") \
        + read_review_log(root / "docs" / "review-log.md", root)
    order = {t: k for k, t in enumerate(TYPES)}
    items.sort(key=lambda i: (i["t"], order[i["type"]], i["id"]))
    pair_qa(items)
    progress_text = (root / "docs" / "progress.md").read_text(encoding="utf-8")
    narrative_path = root / NARRATIVE
    data = {
        "synthetic": False,
        "about": "The real development history of this project, which studies SYNTHETIC data. Prompts and responses "
                 "come from Claude Code hooks and are redacted (home paths, emails, tokens and keys removed).",
        "head": commits[-1]["sha"] if commits else None,
        "phases": sorted({i["phase"] for i in items}),
        "actors": ACTORS, "types": TYPES, "categories": CATEGORIES,
        "items": items,
        "summary": summarize(items, progress_text),
        "narrative": scrub(narrative_path.read_text(encoding="utf-8")) if narrative_path.exists() else None,
    }
    jsonschema.validate(data, json.loads(SCHEMA.read_text(encoding="utf-8")))
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    d = build()
    print(f"timeline: {len(d['items'])} items -> {OUT.relative_to(ROOT)}")
