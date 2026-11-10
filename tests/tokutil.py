"""Shared helpers for the P6 token tests: a fixture transcript set and hook log with hand-checkable numbers."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "tokens.json"
S1, S2, S3 = "sess-one", "sess-two", "sess-three"


def asst(ts, session, mid, inp, out, cc, cr, model="claude-opus-5-5", block="text"):
    return {"type": "assistant", "timestamp": ts, "sessionId": session, "isSidechain": False,
            "message": {"id": mid, "model": model, "role": "assistant", "content": [{"type": block}],
                        "usage": {"input_tokens": inp, "output_tokens": out, "cache_creation_input_tokens": cc,
                                  "cache_read_input_tokens": cr, "service_tier": "standard"}}}


# Times are UTC in transcripts (Z) and -05:00 in the hook log, as in the real files.
T1 = [  # session one: work before its first logged prompt, then two prompts, then a compact
    {"type": "user", "timestamp": "2026-01-01T13:59:00Z", "sessionId": S1, "message": {"role": "user", "content": "hi"}},
    asst("2026-01-01T14:00:00Z", S1, "m1", 1, 10, 100, 1000),                       # before any prompt -> session-start
    asst("2026-01-01T14:02:00Z", S1, "m2", 2, 20, 200, 2000, block="thinking"),
    asst("2026-01-01T14:02:00Z", S1, "m2", 2, 20, 200, 2000, block="tool_use"),     # same id repeated: counted once
    asst("2026-01-01T14:03:00Z", S1, "m3", 3, 30, 300, 3000),
    {"type": "assistant", "timestamp": "2026-01-01T14:03:30Z", "sessionId": S1,     # local placeholder: skipped
     "message": {"id": "synth", "model": "<synthetic>", "usage": {"input_tokens": 0, "output_tokens": 0,
                                                                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}}},
    asst("2026-01-01T14:06:00Z", S1, "m4", 4, 40, 400, 400),                        # after the compact
]
T2 = [  # session two, after a /clear; one experiment prompt
    asst("2026-01-01T14:11:00Z", S2, "m5", 5, 50, 500, 50),
    asst("2026-01-01T14:12:00Z", S2, "m6", 6, 60, 600, 6000),
]
T3 = [  # a session the hooks never saw (no events at all) and a repeat of m6 from a resumed copy
    asst("2026-01-01T14:20:00Z", S3, "m7", 7, 70, 700, 7000),
    asst("2026-01-01T14:12:00Z", S2, "m6", 6, 60, 600, 6000),
]

EVENTS = [
    ("2026-01-01T08:59:30.000-05:00", "SessionStart", S1, "P0:planning", {"source": "startup"}),
    ("2026-01-01T09:01:00.000-05:00", "UserPromptSubmit", S1, "P0:planning", {"prompt": "plan please"}),
    ("2026-01-01T09:02:30.000-05:00", "UserPromptSubmit", S1, "P1:writing-code", {"prompt": "build it"}),
    ("2026-01-01T09:05:00.000-05:00", "PreCompact", S1, "P1:writing-code", {"trigger": "manual"}),
    ("2026-01-01T09:09:00.000-05:00", "SessionEnd", S1, "P1:writing-code", {"reason": "clear"}),
    ("2026-01-01T09:09:00.050-05:00", "SessionStart", S2, "P1:writing-code", {"source": "clear"}),
    ("2026-01-01T09:10:00.000-05:00", "UserPromptSubmit", S2, "P2:planning",
     {"prompt": "Typed by me. TOK-05 run B: add one chart"}),
]


def make_fixture(root: Path) -> tuple[Path, Path]:
    tdir = root / "transcripts"
    tdir.mkdir(parents=True)
    for name, entries in [("a-one", T1), ("b-two", T2), ("c-three", T3)]:
        (tdir / f"{name}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    ev = root / "events.jsonl"
    ev.write_text("".join(json.dumps({"ts": ts, "event": e, "session_id": s, "phase": ph, "payload": p}) + "\n"
                          for ts, e, s, ph, p in EVENTS))
    return tdir, ev
