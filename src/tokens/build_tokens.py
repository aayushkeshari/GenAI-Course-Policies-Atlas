"""TOK-02..05: `make tokens` -> results/tokens.json.

Inputs (read only): raw_logs/transcripts/*.jsonl (verbatim transcript copies made by the hook at PreCompact and
SessionEnd; gitignored) and logs/events.jsonl (hook events, redacted).

Transcript facts recorded for TOK-01 (docs/progress.md): every assistant entry has `message.usage` with
`input_tokens`, `output_tokens`, `cache_creation_input_tokens` and `cache_read_input_tokens`. One API response is
written as several entries (one per content block) that share `message.id` and repeat the same usage, so a row is
one unique `message.id`; counting entries would overcount about 2.3×.

Rows never contain prompt or response text, only ids, times, model, phase and counts.
"""
from __future__ import annotations

import json
import re
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPTS = ROOT / "raw_logs" / "transcripts"
EVENTS = ROOT / "logs" / "events.jsonl"
OUT = ROOT / "results" / "tokens.json"
SCHEMA = ROOT / "src" / "report" / "schemas" / "tokens.schema.json"

FIELDS = {  # row key -> transcript usage key (TOK-01)
    "input": "input_tokens",
    "output": "output_tokens",
    "cache_creation": "cache_creation_input_tokens",
    "cache_read": "cache_read_input_tokens",
}
COUNTS = list(FIELDS)
ACTIVITIES = ["planning", "data", "analysis", "writing-code", "validation", "docs"]  # TOK-04 vocabulary
SKIP_MODELS = {"<synthetic>"}  # Claude Code's locally generated placeholder messages: not API calls
EXPERIMENT = re.compile(r"\bTOK-05 run ([ABC])\b")
CONDITIONS = {"A": "long session, no clear", "B": "right after /clear + /resume", "C": "right after /compact"}


def epoch_ms(ts: str) -> int:
    return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)


def split_phase(label: str | None) -> tuple[str, str]:
    m = re.match(r"^(P\d)(?::(.+))?$", (label or "").strip())
    return (m.group(1), m.group(2) or "unknown") if m else ("unknown", "unknown")


# ---------- TOK-02: parse ----------
def parse_transcript(path: Path) -> list[dict]:
    """One row per unique assistant message.id that carries usage. Entries repeating an id must repeat the same
    usage (checked, so a format change can't silently double count)."""
    rows: dict[str, dict] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("type") != "assistant":
            continue
        m = e.get("message") or {}
        usage = m.get("usage")
        if not usage or m.get("model") in SKIP_MODELS:
            continue
        counts = {k: int(usage.get(src) or 0) for k, src in FIELDS.items()}
        mid = m.get("id") or f"{path.stem}:{n}"
        if mid in rows:
            if {k: rows[mid][k] for k in COUNTS} != counts:
                raise ValueError(f"{path.name}:{n}: message {mid} repeats with different usage")
            continue
        rows[mid] = {"message_id": mid, "ts": e["timestamp"], "t": epoch_ms(e["timestamp"]),
                     "session_id": e.get("sessionId") or e.get("session_id") or path.stem,
                     "model": m.get("model") or "unknown", "sidechain": bool(e.get("isSidechain")), **counts}
    return list(rows.values())


def parse_all(transcripts: Path) -> list[dict]:
    """All transcripts, deduplicated across files by message id (a resumed session can repeat earlier messages)."""
    seen, rows = set(), []
    for path in sorted(transcripts.glob("*.jsonl")):
        for r in parse_transcript(path):
            if r["message_id"] not in seen:
                seen.add(r["message_id"])
                rows.append(r)
    rows.sort(key=lambda r: (r["t"], r["message_id"]))
    return rows


def read_events(path: Path) -> list[dict]:
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            e = json.loads(line)
            e["line"], e["t"] = n, epoch_ms(e["ts"])
            out.append(e)
    return out


# ---------- TOK-02: phase/activity join ----------
def join_phase(rows: list[dict], events: list[dict]) -> None:
    """Each row takes phase/activity from the nearest preceding UserPromptSubmit in its own session
    (join = "prompt"). Rows before a session's first logged prompt (work done before the hooks were installed)
    take the phase of that session's first hook event and are flagged join = "session-start". A row in a session
    with no hook events at all falls back to the nearest preceding prompt in any session (join = "any-session")."""
    prompts = sorted((e for e in events if e["event"] == "UserPromptSubmit"), key=lambda e: e["t"])
    by_session: dict[str, list[dict]] = defaultdict(list)
    for p in prompts:
        by_session[p["session_id"]].append(p)
    first_event = {}
    for e in sorted(events, key=lambda e: e["t"]):
        first_event.setdefault(e["session_id"], e)
    all_t = [p["t"] for p in prompts]
    for r in rows:
        ps = by_session.get(r["session_id"], [])
        i = bisect_right([p["t"] for p in ps], r["t"])
        if i:
            src, how = ps[i - 1], "prompt"
        elif r["session_id"] in first_event:
            src, how = first_event[r["session_id"]], "session-start"
        else:
            j = bisect_right(all_t, r["t"])
            src, how = (prompts[j - 1], "any-session") if j else (None, "none")
        r["phase"], r["activity"] = split_phase(src["phase"]) if src else ("unknown", "unknown")
        r["join"] = how
        r["prompt_line"] = src["line"] if src and src["event"] == "UserPromptSubmit" else None
        m = EXPERIMENT.search(src["payload"].get("prompt", "")) if how == "prompt" else None
        r["experiment"] = m.group(1) if m else None
        r["context"] = r["input"] + r["cache_creation"] + r["cache_read"]


# ---------- TOK-03: boundaries ----------
def boundaries(events: list[dict]) -> list[dict]:
    out = []
    for e in events:
        p = e.get("payload") or {}
        if e["event"] == "SessionStart" and p.get("source") == "clear":
            kind = "clear"
        elif e["event"] == "PreCompact":
            kind = "compact"
        else:
            continue
        phase, activity = split_phase(e.get("phase"))
        out.append({"ts": e["ts"], "t": e["t"], "kind": kind, "session_id": e["session_id"], "phase": phase,
                    "trigger": p.get("trigger") or p.get("source"), "event_line": e["line"]})
    return sorted(out, key=lambda b: b["t"])


def boundary_drops(rows: list[dict], bounds: list[dict]) -> list[dict]:
    """Context of the last row before each boundary vs the first row after it (the sawtooth's drop). A clear starts
    a new session, so 'after' is the next row in any session; a compact continues its own session."""
    out = []
    for b in bounds:
        before = [r for r in rows if r["t"] < b["t"]]
        after = [r for r in rows if r["t"] > b["t"] and (b["kind"] == "clear" or r["session_id"] == b["session_id"])]
        if b["kind"] == "compact":
            before = [r for r in before if r["session_id"] == b["session_id"]]
        out.append({**{k: b[k] for k in ("ts", "kind")},
                    "context_before": before[-1]["context"] if before else None,
                    "context_after": after[0]["context"] if after else None})
    return out


# ---------- TOK-04: metrics ----------
def tally(rows: list[dict]) -> dict:
    d = {k: sum(r[k] for r in rows) for k in COUNTS}
    d["total"] = sum(d[k] for k in COUNTS)
    d["messages"] = len(rows)
    ctx = d["input"] + d["cache_creation"] + d["cache_read"]
    d["cache_read_share"] = round(d["cache_read"] / ctx, 4) if ctx else None
    return d


def group(rows, key, order=None):
    keys = order or sorted({r[key] for r in rows})
    return {k: tally([r for r in rows if r[key] == k]) for k in keys if any(r[key] == k for r in rows)}


def per_prompt(rows: list[dict], events: list[dict]) -> list[dict]:
    """Tokens spent answering each logged prompt: the rows joined to it (until the session's next prompt)."""
    rows_by = defaultdict(list)
    for r in rows:
        if r["prompt_line"] is not None:
            rows_by[r["prompt_line"]].append(r)
    out = []
    for e in events:
        if e["event"] != "UserPromptSubmit":
            continue
        phase, activity = split_phase(e.get("phase"))
        t = tally(rows_by.get(e["line"], []))
        out.append({"event_line": e["line"], "ts": e["ts"], "phase": phase, "activity": activity,
                    **{k: t[k] for k in COUNTS + ["total", "messages"]}})
    return out


def prompt_stats(pp: list[dict]) -> dict:
    def stats(xs):
        tot = [x["total"] for x in xs]
        return {"prompts": len(xs), "mean": round(sum(tot) / len(tot)) if tot else None,
                "median": median(tot) if tot else None, "max": max(tot) if tot else None}
    by_phase = defaultdict(list)
    for x in pp:
        by_phase[x["phase"]].append(x)
    return {"all": stats(pp), "by_phase": {k: stats(v) for k, v in sorted(by_phase.items())}}


def experiment(rows: list[dict]) -> dict:
    """TOK-05: rows answering prompts that contain the marker 'TOK-05 run A|B|C'. n = 1 per condition."""
    out = {}
    for c, label in CONDITIONS.items():
        rs = [r for r in rows if r["experiment"] == c]
        t = tally(rs)
        out[c] = {"label": label, "runs": len({r["prompt_line"] for r in rs}), **t,
                  "first_context": rs[0]["context"] if rs else None,
                  "peak_context": max((r["context"] for r in rs), default=None)}
    return {"conditions": out, "marker": EXPERIMENT.pattern,
            "caveat": "One run per condition (n = 1). Differences are anecdotal, not evidence: task wording, "
                      "Claude's choices and cache timing alone can move these numbers."}


def build(transcripts: Path = TRANSCRIPTS, events_path: Path = EVENTS, out: Path | None = OUT) -> dict:
    events = read_events(events_path)
    rows = parse_all(transcripts)
    join_phase(rows, events)
    bounds = boundaries(events)
    pp = per_prompt(rows, events)
    data = {
        "synthetic": False,
        "about": "Real token usage of the Claude Code sessions that built this project (which studies synthetic data).",
        "fields": FIELDS,
        "rows": rows,
        "boundaries": bounds,
        "metrics": {
            "totals": tally(rows),
            "by_phase": group(rows, "phase"),
            "by_activity": group(rows, "activity", ACTIVITIES + sorted({r["activity"] for r in rows} - set(ACTIVITIES))),
            "by_model": group(rows, "model"),
            "per_prompt": pp,
            "per_prompt_stats": prompt_stats(pp),
            "boundary_drops": boundary_drops(rows, bounds),
            "join_counts": {k: sum(1 for r in rows if r["join"] == k) for k in ("prompt", "session-start", "any-session", "none")},
            "activities_logged": sorted({r["activity"] for r in rows}),
        },
        "experiment": experiment(rows),
        "sources": {"transcripts": len(list(transcripts.glob("*.jsonl"))), "events": len(events),
                    "not_covered": "Subagent transcripts are stored outside raw_logs/ and are not copied by the hook, "
                                   "so subagent tokens are not counted."},
    }
    jsonschema.validate(data, json.loads(SCHEMA.read_text(encoding="utf-8")))
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    d = build()
    t = d["metrics"]["totals"]
    print(f"tokens: {t['messages']} assistant messages, {t['total']:,} tokens -> {OUT.relative_to(ROOT)}")
