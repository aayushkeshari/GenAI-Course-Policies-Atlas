"""PROV-01/02/04/05/06: the timeline data built by `make timeline` (src/provenance/build_timeline.py).

Most tests build from a small fixture project (tests/provutil.py) so the expected values are known exactly;
a few check the real, committed site/timeline/data/timeline.json.
"""
import json
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest

from provutil import FAKE_HOME, ROOT, SITE, TIMELINE, make_project
from src.provenance import build_timeline as T


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    root = make_project(tmp_path_factory.mktemp("prov") / "proj")
    out = root / "out" / "timeline.json"
    data = T.build(root=root, out=out)
    return {"root": root, "out": out, "data": data, "by_id": {i["id"]: i for i in data["items"]}}


def items(fx, type_):
    return [i for i in fx["data"]["items"] if i["type"] == type_]


def _strings(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, str):
        yield obj


BANS = [re.compile(re.escape(str(Path.home()))), re.compile(r"/Users/|/home/\w|C:\\Users"),
        re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"), re.compile(r"sk-[A-Za-z0-9]{20,}"),
        re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}")]


# ---------- PROV-01 ----------
@pytest.mark.req("PROV-01")
def test_build_merges_all_four_sources(fx):
    """One build of the fixture project yields items from every source: 9 hook events (4 prompts, 3 responses,
    2 session events), 5 commits plus their spec edits, the progress entry and both review entries, each with
    ts, actor, phase, type, summary and source, and the written file equals the returned data."""
    d = fx["data"]
    assert len(items(fx, "prompt")) == 4 and len(items(fx, "response")) == 3 and len(items(fx, "session")) == 2
    assert len(items(fx, "commit")) == 5 and len(items(fx, "spec_edit")) == 3
    assert len(items(fx, "progress")) == 1 and len(items(fx, "review")) == 2
    for it in d["items"]:
        assert {"ts", "actor", "phase", "type", "summary", "source"} <= it.keys(), it
    assert json.loads(fx["out"].read_text(encoding="utf-8")) == d
    assert {i["source"].split(":")[0] for i in d["items"] if ":" in i["source"]} == \
        {"logs/events.jsonl", "docs/progress.md", "docs/review-log.md"}


@pytest.mark.req("PROV-01")
def test_items_are_sorted_unique_and_valid(fx):
    """Items are in time order, ids are unique, `t` is the epoch-ms of `ts`, and the output validates against
    src/provenance/timeline.schema.json (which a bad item fails)."""
    its = fx["data"]["items"]
    assert [i["t"] for i in its] == sorted(i["t"] for i in its)
    assert len({i["id"] for i in its}) == len(its)
    for i in its:
        assert i["t"] == T.epoch_ms(i["ts"])
    schema = json.loads(T.SCHEMA.read_text())
    jsonschema.validate(fx["data"], schema)
    bad = json.loads(json.dumps(fx["data"]))
    bad["items"][0]["actor"] = "BOTH"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


@pytest.mark.req("PROV-01")
def test_phases_come_from_the_sources(fx):
    """Events take the phase their hook recorded; progress entries their [Px] tag; a commit the phase named in its
    subject, else the phase of the last earlier hook event, else 'unknown' (never guessed)."""
    b = fx["by_id"]
    assert [i["phase"] for i in items(fx, "prompt")] == ["P0", "P0", "P0", "P1"]
    assert items(fx, "progress")[0]["phase"] == "P0"
    commits = {i["summary"]: i["phase"] for i in items(fx, "commit")}
    assert commits["claude-chat: draft specs"] == "unknown"           # before any hook event
    assert commits["agent: P0 step 1 — code"] == "P0"                 # named in the subject
    assert commits["agent: fix without a phase tag"] == "P0"          # last event before 09:06:30 is P0
    assert commits["human: P0 review-log entry"] == "P0"
    assert b  # ids indexed


@pytest.mark.req("PROV-01")
def test_review_entries_take_their_commit_time_or_fall_back_to_the_day(fx):
    """A review-log heading's time is the commit that first added it (precision 'commit'); a heading never
    committed is placed at the end of its date with ts_precision 'day', so it is never given a made-up time."""
    rev = {i["summary"]: i for i in items(fx, "review")}
    assert rev["P0 instrumentation"]["ts"] == "2026-01-01T09:30:00-05:00"
    assert rev["P0 instrumentation"]["ts_precision"] == "commit"
    assert rev["P1 synthetic data"]["ts"] == "2026-01-02T23:59:59+00:00"
    assert rev["P1 synthetic data"]["ts_precision"] == "day"
    assert rev["P1 synthetic data"]["phase"] == "P1"


@pytest.mark.req("PROV-01")
def test_lines_changed_skip_generated_paths(fx):
    """A commit's added/removed counts cover hand-written files only: results/ (generated) is excluded, so the
    P0 commit counts src/x.py (3) and specs/P1-y.md (1), not the 50-line results file."""
    c = {i["summary"]: i for i in items(fx, "commit")}["agent: P0 step 1 — code"]
    assert (c["added"], c["removed"]) == (4, 0)


@pytest.mark.req("PROV-01")
def test_committed_timeline_matches_a_fresh_build():
    """site/timeline/data/timeline.json is current with the repo, apart from history added since it was built: every
    committed item appears unchanged in a fresh build, and the fresh build adds only items newer than the
    committed file's last item. So nothing published is stale or invented."""
    committed = json.loads(TIMELINE.read_text(encoding="utf-8"))
    fresh = {i["id"]: i for i in T.build(out=None)["items"]}
    last = max(i["t"] for i in committed["items"])
    for it in committed["items"]:
        mine = {k: v for k, v in it.items() if k not in ("reply", "reply_to")}
        theirs = {k: v for k, v in fresh.get(it["id"], {}).items() if k not in ("reply", "reply_to")}
        assert mine == theirs, it["id"]
    ids = {i["id"] for i in committed["items"]}
    # the newest commit may be the one that committed this very file, so it can predate `last`
    new = [i for i in fresh.values() if i["id"] not in ids and i["type"] not in ("commit", "spec_edit")]
    assert all(i["t"] >= last for i in new), [i["id"] for i in new if i["t"] < last]


@pytest.mark.req("PROV-01")
def test_every_committed_source_resolves():
    """Each item's source points at something real: `file:line` is a line of that file (an event line, or the
    item's own heading), and `git <sha>` is a commit in this repo."""
    data = json.loads(TIMELINE.read_text(encoding="utf-8"))
    shas = set(subprocess.run(["git", "-C", str(ROOT), "log", "--format=%h", "--abbrev=7"],
                              capture_output=True, text=True, check=True).stdout.split())
    lines = {}
    for it in data["items"]:
        src = it["source"]
        if src.startswith("git "):
            assert src[4:] in shas, src
            continue
        rel, n = src.rsplit(":", 1)
        lines.setdefault(rel, (ROOT / rel).read_text(encoding="utf-8").splitlines())
        line = lines[rel][int(n) - 1]
        if rel.endswith(".md"):
            assert line.startswith("## ") and (it["summary"] in line or it["summary"].endswith("…")), src
        else:
            assert json.loads(line)["ts"] == it["ts"], src


@pytest.mark.req("PROV-01")
def test_make_timeline_runs_the_builder():
    """`make timeline` runs src.provenance.build_timeline (no longer the P5 stub)."""
    out = subprocess.run(["make", "-n", "timeline"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "-m src.provenance.build_timeline" in out and "not implemented" not in out


# ---------- PROV-02 ----------
@pytest.mark.req("PROV-02")
@pytest.mark.parametrize("subject,actor", [
    ("agent: P1 — code", "CLAUDE"), ("human: review", "HUMAN"), ("claude-chat: drafts", "shared"),
    ("Agent: wrong case", "shared"), ("fix typo", "shared"), ("humans: not the prefix", "shared"),
])
def test_commit_actor_follows_the_prefix_only(subject, actor):
    """`agent:` commits are CLAUDE, `human:` commits are HUMAN, and every other subject is 'shared' (no guessing
    from the wording)."""
    assert T.commit_actor(subject) == actor


@pytest.mark.req("PROV-02")
@pytest.mark.parametrize("subject,actor", [
    ("agent: P5 spec — per Aayush", "HUMAN"), ("human: import specs", "HUMAN"), ("claude-chat: revise specs", "shared"),
])
def test_spec_edits_are_human_unless_the_commit_is_ambiguous(subject, actor):
    """Spec edits are HUMAN even when typed into an `agent:` commit; in a commit with neither prefix the author
    is ambiguous, so the edit is 'shared'."""
    assert T.spec_edit_actor(subject) == actor


@pytest.mark.req("PROV-02")
@pytest.mark.parametrize("prompt,category", [
    ("Typed by me: go ahead", "human-typed"),
    ("  \nTyped by me", "human-typed"),
    ("typed by me: lower case", "shared"),
    ("Please continue. Typed by me", "shared"),
    ("[drafted by Aayush] old marker", "shared"),
    ("<task-notification>agent done</task-notification>", "automated"),
    ("<scheduled-task name='x'>run</scheduled-task>", "automated"),
    ("<cross-session-message from='s'>hi</cross-session-message>", "automated"),
    ("\n\n<pasted_content id=\"a\">\n1. yes\n</pasted_content>", "shared"),
    ("git push", "shared"),
    ("/resume", "shared"),
    ("", "shared"),
])
def test_prompt_categories(prompt, category):
    """Prompts starting (after whitespace) with "Typed by me" are human-typed; the tags Claude Code puts on
    subagent reports, scheduled tasks and cross-session messages are automated; everything else is 'shared'."""
    assert T.classify_prompt(prompt) == category


@pytest.mark.req("PROV-02")
def test_actor_table_applied_to_every_item(fx):
    """In a built timeline: prompts, human: commits and reviews are HUMAN; responses, agent: commits and progress
    entries are CLAUDE; session events and the claude-chat commit are shared; the claude-chat spec edit is
    shared and the agent:/human: spec edits are HUMAN."""
    want = {"prompt": "HUMAN", "review": "HUMAN", "response": "CLAUDE", "progress": "CLAUDE", "session": "shared"}
    for it in fx["data"]["items"]:
        if it["type"] in want:
            assert it["actor"] == want[it["type"]], it["id"]
    commits = {i["summary"]: i["actor"] for i in items(fx, "commit")}
    assert commits == {"claude-chat: draft specs": "shared", "human: import specs": "HUMAN",
                       "agent: P0 step 1 — code": "CLAUDE", "agent: fix without a phase tag": "CLAUDE",
                       "human: P0 review-log entry": "HUMAN"}
    specs = sorted((i["summary"].split(":")[0], i["actor"]) for i in items(fx, "spec_edit"))
    assert specs == [("specs/P0-x.md", "HUMAN"), ("specs/P0-x.md", "shared"), ("specs/P1-y.md", "HUMAN")]
    assert [i["category"] for i in items(fx, "prompt")] == ["human-typed", "automated", "shared", "shared"]


# ---------- PROV-04 (data) ----------
@pytest.mark.req("PROV-04")
def test_prompts_pair_with_the_next_response_in_their_own_session(fx):
    """Each prompt's reply is the first response in the same session before that session's next prompt. S2's
    prompt is answered by S2's Stop even though S1's Stop comes first; a prompt with no later response has
    reply null rather than a borrowed one."""
    p = items(fx, "prompt")
    r = {i["id"]: i for i in items(fx, "response")}
    assert r[p[0]["reply"]]["text"] == "Here is the P0 plan."
    assert r[p[1]["reply"]]["text"] == "Noted the subagent report."
    assert r[p[2]["reply"]]["text"].startswith("Done.")
    assert r[p[2]["reply"]]["session"] == p[2]["session"]
    assert p[2]["reply"] and r[p[2]["reply"]]["reply_to"] == p[2]["id"]
    assert len(p) == 4


@pytest.mark.req("PROV-04")
def test_unanswered_prompt_has_null_reply(fx):
    """The fixture's final prompt ('git push') has no response before its session ends, so reply is null and it
    is counted as unanswered."""
    last = [i for i in fx["data"]["items"] if i["type"] == "prompt" and i["summary"] == "git push"]
    assert len(last) == 1 and last[0]["reply"] is None
    assert fx["data"]["summary"]["unanswered_prompts"] == 1 and fx["data"]["summary"]["qa_pairs"] == 3


# ---------- PROV-05 (data) ----------
@pytest.mark.req("PROV-05")
def test_summary_counts_per_actor(fx):
    """Per-actor counts equal hand counts of the fixture: 4 prompts are HUMAN, 3 responses CLAUDE, 2 HUMAN
    decision tags (backticked mentions don't count) as approvals, 1 REJECTED: bullet (a prose mention doesn't count), spec edits and commits by
    prefix rule, and lines changed per actor excluding generated paths."""
    pa = fx["data"]["summary"]["per_actor"]
    assert pa["HUMAN"] == {"prompts": 4, "responses": 0, "spec_edits": 2, "reviews": 2, "commits": 2,
                           "lines_added": 4, "lines_removed": 0, "approvals": 2, "rejected_plans": 1}
    assert pa["CLAUDE"] == {"prompts": 0, "responses": 3, "spec_edits": 0, "reviews": 0, "commits": 2,
                            "lines_added": 4, "lines_removed": 1, "approvals": None, "rejected_plans": None}
    assert pa["shared"]["commits"] == 1 and pa["shared"]["spec_edits"] == 1 and pa["shared"]["lines_added"] == 2
    assert fx["data"]["summary"]["agent_decisions"] == 1
    assert fx["data"]["summary"]["prompt_categories"] == {"human-typed": 1, "automated": 1, "shared": 2}


@pytest.mark.req("PROV-05")
def test_narrative_is_null_until_written(fx, tmp_path):
    """Without docs/timeline-narrative.md the narrative is null (the page then says it is not written yet); with
    the file present its (redacted) text is published verbatim."""
    assert fx["data"]["narrative"] is None
    root = make_project(tmp_path / "p")
    (root / "docs" / "timeline-narrative.md").write_text(f"I set the specs. Paths like {FAKE_HOME}/x are hidden.\n")
    d = T.build(root=root, out=None)
    assert d["narrative"].startswith("I set the specs.") and FAKE_HOME not in d["narrative"]


@pytest.mark.req("PROV-05")
def test_rejected_plans_record_when_counting_started():
    """The summary states that REJECTED: tags only exist from the CLAUDE.md rule onwards, so earlier history reads
    as 'not recorded' rather than zero rejections."""
    rules = json.loads(TIMELINE.read_text(encoding="utf-8"))["summary"]["rules"]
    assert rules["rejected_recorded_since"] == T.REJECTED_RECORDED_SINCE
    assert "not recorded" in rules["rejected_plans"]


# ---------- PROV-06 ----------
@pytest.mark.req("PROV-06")
def test_builder_redacts_paths_emails_and_keys(fx):
    """The fixture's prompt holds a home path and an email and its response holds an sk- key; none of them
    survives into the output, and visible placeholders show that something was removed."""
    text = fx["out"].read_text(encoding="utf-8")
    assert FAKE_HOME not in text and "a@b.org" not in text and "sk-AAAA" not in text
    assert "‹redacted-path›" in text and "‹redacted-email›" in text and "‹redacted-secret›" in text
    for s in _strings(fx["data"]):
        for pat in BANS:
            assert not pat.search(s), (pat.pattern, s)


@pytest.mark.req("PROV-06")
def test_nothing_under_site_contains_private_data():
    """Every file under site/ (decoded JSON strings and keys, or raw text for other files) is free of the home
    directory, /Users/ or /home/ paths, email addresses and credential-like strings."""
    checked = 0
    for p in SITE.rglob("*"):
        if not p.is_file() or p.suffix not in (".json", ".html", ".js", ".css", ".md", ".txt", ".svg"):
            continue
        text = p.read_text(encoding="utf-8")
        if p.suffix == ".json":
            text = "\n".join(_strings(json.loads(text)))
        for pat in BANS:
            m = pat.search(text)
            assert not m, (str(p.relative_to(SITE)), m and m.group())
        checked += 1
    assert checked > 10 and TIMELINE.exists()
