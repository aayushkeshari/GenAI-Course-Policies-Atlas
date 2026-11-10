"""TOK-01..05, TOK-08: the token parser and metrics built by `make tokens` (src/tokens/build_tokens.py).

Fixture tests use tests/tokutil.py, whose numbers are small enough to check by hand. Real-data tests read the
committed results/tokens.json, because raw_logs/ (the verbatim transcripts) is gitignored.
"""
import json
import subprocess

import pytest

from src.tokens import build_tokens as K
from tokutil import RESULT, ROOT, S1, S2, S3, make_fixture

COUNTS = ["input", "output", "cache_creation", "cache_read"]


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    tdir, ev = make_fixture(tmp_path_factory.mktemp("tok"))
    d = K.build(transcripts=tdir, events_path=ev, out=None)
    return {"data": d, "rows": {r["message_id"]: r for r in d["rows"]}, "tdir": tdir, "ev": ev}


@pytest.fixture(scope="module")
def real():
    return json.loads(RESULT.read_text(encoding="utf-8"))


# ---------- TOK-01 ----------
@pytest.mark.req("TOK-01")
def test_field_names_were_recorded_from_a_real_transcript():
    """docs/progress.md has a TOK-01 entry naming the four usage fields found in a real transcript, and the parser
    reads exactly those names."""
    text = (ROOT / "docs" / "progress.md").read_text(encoding="utf-8")
    entry = text[text.index("TOK-01: usage fields"):]
    for name in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "message.id"):
        assert name in entry[:3000], name
    assert K.FIELDS == {"input": "input_tokens", "output": "output_tokens",
                        "cache_creation": "cache_creation_input_tokens", "cache_read": "cache_read_input_tokens"}


# ---------- TOK-02 ----------
@pytest.mark.req("TOK-02", "TOK-08")
def test_parser_gives_one_row_per_assistant_message(fx):
    """On the fixture transcripts the parser yields one row per unique message id (m1..m7): a message repeated
    across content blocks or across files counts once, user entries are ignored, and Claude Code's local
    '<synthetic>' placeholder is skipped. Each row has ts, session, model and the four counts."""
    rows = fx["data"]["rows"]
    assert [r["message_id"] for r in rows] == ["m1", "m2", "m3", "m4", "m5", "m6", "m7"]
    m2 = fx["rows"]["m2"]
    assert (m2["input"], m2["output"], m2["cache_creation"], m2["cache_read"]) == (2, 20, 200, 2000)
    assert m2["session_id"] == S1 and m2["model"] == "claude-opus-5-5" and m2["ts"] == "2026-01-01T14:02:00Z"
    assert all(r["context"] == r["input"] + r["cache_creation"] + r["cache_read"] for r in rows)


@pytest.mark.req("TOK-02", "TOK-08")
def test_repeated_message_with_different_usage_is_an_error(tmp_path):
    """If a message id ever repeats with different counts, parsing stops with an error instead of picking one
    (so a transcript format change can't silently double or drop tokens)."""
    from tokutil import asst
    f = tmp_path / "x.jsonl"
    f.write_text(json.dumps(asst("2026-01-01T00:00:00Z", "s", "m", 1, 1, 1, 1)) + "\n" +
                 json.dumps(asst("2026-01-01T00:00:00Z", "s", "m", 1, 2, 1, 1)) + "\n")
    with pytest.raises(ValueError, match="different usage"):
        K.parse_transcript(f)


@pytest.mark.req("TOK-02", "TOK-08")
def test_phase_join_uses_the_nearest_earlier_prompt_in_the_same_session(fx):
    """m2 (14:02:00Z = 09:02 local) follows 'plan please' (P0:planning) and m3 follows 'build it'
    (P1:writing-code); m4 after the compact still belongs to 'build it'; m5/m6 follow session two's prompt
    (P2:planning) even though session one's prompts are later in no case. Times in UTC and -05:00 compare correctly."""
    r = fx["rows"]
    assert (r["m2"]["phase"], r["m2"]["activity"], r["m2"]["join"]) == ("P0", "planning", "prompt")
    assert (r["m3"]["phase"], r["m3"]["activity"]) == ("P1", "writing-code")
    assert (r["m4"]["phase"], r["m4"]["prompt_line"]) == ("P1", 3)
    assert (r["m5"]["phase"], r["m5"]["activity"], r["m5"]["prompt_line"]) == ("P2", "planning", 7)


@pytest.mark.req("TOK-02", "TOK-08")
def test_phase_join_fallbacks_are_flagged_never_blank(fx):
    """A row before its session's first prompt (m1) takes the session's first hook event's phase, flagged
    'session-start'; a row from a session the hooks never saw (m7) takes the nearest earlier prompt in any
    session, flagged 'any-session'. No fixture row is left without a phase."""
    r = fx["rows"]
    assert (r["m1"]["phase"], r["m1"]["join"], r["m1"]["prompt_line"]) == ("P0", "session-start", None)
    assert (r["m7"]["phase"], r["m7"]["join"], r["m7"]["session_id"]) == ("P2", "any-session", S3)
    assert all(x["phase"] != "unknown" and x["join"] != "none" for x in fx["data"]["rows"])


# ---------- TOK-03 ----------
@pytest.mark.req("TOK-03")
def test_clear_and_compact_boundaries_are_marked(fx):
    """SessionStart with source=clear and PreCompact become boundaries (a startup SessionStart does not), each with
    its time and session, and the drop table pairs the context just before and just after each one."""
    b = fx["data"]["boundaries"]
    assert [(x["kind"], x["session_id"]) for x in b] == [("compact", S1), ("clear", S2)]
    drops = fx["data"]["metrics"]["boundary_drops"]
    assert drops[0] == {"ts": "2026-01-01T09:05:00.000-05:00", "kind": "compact",
                        "context_before": 3 + 300 + 3000, "context_after": 4 + 400 + 400}
    assert drops[1]["context_before"] == 4 + 400 + 400 and drops[1]["context_after"] == 5 + 500 + 50


# ---------- TOK-04 ----------
@pytest.mark.req("TOK-04")
def test_totals_by_phase_and_activity(fx):
    """By-phase and by-activity tallies equal hand sums: P0 = m1+m2, P1 = m3+m4, P2 = m5+m6+m7; planning =
    m1+m2+m5+m6+m7, writing-code = m3+m4. Activities are listed in the spec's order."""
    m = fx["data"]["metrics"]
    assert m["by_phase"]["P0"]["output"] == 10 + 20 and m["by_phase"]["P1"]["output"] == 30 + 40
    assert m["by_phase"]["P2"]["output"] == 50 + 60 + 70
    assert m["by_activity"]["planning"]["messages"] == 5 and m["by_activity"]["writing-code"]["messages"] == 2
    assert list(m["by_activity"]) == ["planning", "writing-code"]


@pytest.mark.req("TOK-04")
def test_tokens_per_prompt_and_cache_share(fx):
    """Per-prompt tallies cover the rows joined to each prompt ('build it' gets m3+m4); the cache-read share is
    cache_read / (input + cache_creation + cache_read)."""
    pp = {x["event_line"]: x for x in fx["data"]["metrics"]["per_prompt"]}
    assert pp[3]["messages"] == 2 and pp[3]["total"] == (3 + 30 + 300 + 3000) + (4 + 40 + 400 + 400)
    t = fx["data"]["metrics"]["totals"]
    assert t["cache_read_share"] == round(t["cache_read"] / (t["input"] + t["cache_creation"] + t["cache_read"]), 4)


# ---------- TOK-05 ----------
@pytest.mark.req("TOK-05")
def test_experiment_rows_are_found_by_marker(fx):
    """Rows answering a prompt containing 'TOK-05 run B' (even after a 'Typed by me' prefix) are condition B; the
    other conditions are empty, and the result carries the n = 1 caveat."""
    e = fx["data"]["experiment"]
    assert e["conditions"]["B"]["messages"] == 2 and e["conditions"]["B"]["runs"] == 1
    assert e["conditions"]["B"]["first_context"] == 5 + 500 + 50
    assert e["conditions"]["A"]["messages"] == 0 and e["conditions"]["C"]["first_context"] is None
    assert "n = 1" in e["caveat"] and "anecdotal" in e["caveat"]


@pytest.mark.req("TOK-05")
def test_spec_says_one_run_per_condition_and_a_small_sample():
    """specs/P6-tokens.md's TOK-05 asks for one run per condition and a plain statement that the sample is small."""
    spec = (ROOT / "specs" / "P6-tokens.md").read_text(encoding="utf-8")
    tok5 = spec[spec.index("**TOK-05**"):spec.index("**TOK-06**")]
    assert "1 run per condition" in tok5 and "small" in tok5 and "twice" not in tok5


# ---------- TOK-08 on the real, committed results ----------
@pytest.mark.req("TOK-08")
def test_real_totals_equal_the_sum_of_rows(real):
    """In results/tokens.json the overall totals, and the sums over every phase, activity and model, equal the sum
    of the rows; per-prompt message counts add up to the rows joined to a prompt."""
    rows, m = real["rows"], real["metrics"]
    for k in COUNTS + ["total", "messages"]:
        want = len(rows) if k == "messages" else sum(r[k] for r in rows) if k != "total" else sum(r[c] for r in rows for c in COUNTS)
        assert m["totals"][k] == want, k
        for g in ("by_phase", "by_activity", "by_model"):
            assert sum(v[k] for v in m[g].values()) == want, (g, k)
    assert sum(x["messages"] for x in m["per_prompt"]) == sum(1 for r in rows if r["prompt_line"] is not None)
    assert len(rows) > 100 and len({r["message_id"] for r in rows}) == len(rows)


@pytest.mark.req("TOK-08")
def test_real_phase_join_has_no_gaps(real):
    """Every real row has a phase and activity, none is unjoined, every prompt-joined row points at a
    UserPromptSubmit line of logs/events.jsonl in the same session, and the only fallback used is the flagged
    'session-start' one (work before the hooks were installed)."""
    lines = (ROOT / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    for r in real["rows"]:
        assert r["phase"] != "unknown" and r["activity"] != "unknown" and r["join"] != "none", r["message_id"]
        if r["join"] == "prompt":
            e = json.loads(lines[r["prompt_line"] - 1])
            assert e["event"] == "UserPromptSubmit" and e["session_id"] == r["session_id"]
    jc = real["metrics"]["join_counts"]
    assert jc["none"] == 0 and jc["prompt"] > jc["session-start"]


@pytest.mark.req("TOK-08")
def test_real_results_hold_no_text_or_paths(real):
    """results/tokens.json carries ids, times and counts only: no prompt or response text, home paths or emails."""
    text = RESULT.read_text(encoding="utf-8")
    assert "/Users/" not in text and "@" not in text.replace('"@', "")
    assert all(set(r) == {"message_id", "ts", "t", "session_id", "model", "sidechain", *COUNTS, "context", "phase",
                          "activity", "join", "prompt_line", "experiment"} for r in real["rows"])


@pytest.mark.req("TOK-02")
def test_make_tokens_runs_the_builder():
    """`make tokens` runs src.tokens.build_tokens (no longer the P6 stub)."""
    out = subprocess.run(["make", "-n", "tokens"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "-m src.tokens.build_tokens" in out and "not implemented" not in out
