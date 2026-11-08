"""INST-09: redaction before anything is written to logs/."""
import pytest

from hookutil import errors, events, load_hook_module, run_hook

redact = load_hook_module().redact
TOKEN = "[REDACTED_TOKEN]"


@pytest.mark.req("INST-09")
@pytest.mark.parametrize("raw,expected", [
    ("mail me@example.com now", "mail [EMAIL] now"),
    ("a.b+tag@sub.uni.edu", "[EMAIL]"),
    ("key sk-ant-api03-AbC123_def-456ghiJKL789 end", f"key {TOKEN} end"),
    ("sk-proj-abcdefghijklmnop1234", TOKEN),
    ("ghp_abcdefghijklmnopqrstuvwxyz0123456789", TOKEN),
    ("github_pat_11ABCDEFG0123456789_abcdefghijklmnop", TOKEN),
    ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig", f"Authorization: {TOKEN}"),
    ("/Users/someone/Desktop/CS 4005/Project 2", "~/Desktop/CS 4005/Project 2"),
    ("/home/bob/.ssh/id_rsa", "~/.ssh/id_rsa"),
    ("cd '/Users/alice' && ls", "cd '~' && ls"),
    ("file:///Users/alice/x.html", "file://~/x.html"),
])
def test_redacts_each_secret_class(raw, expected):
    """Each pattern class in INST-09 (emails, sk-/ghp_/github_pat_/Bearer tokens, /Users and
    /home paths) is replaced with its placeholder. The text around it is unchanged."""
    assert redact(raw) == expected


@pytest.mark.req("INST-09")
@pytest.mark.parametrize("text", [
    "task-list and sk-learn are fine",          # sk- prefix but too short to be a key
    "a task-management-system-overview",       # long, but 'sk-' is mid-word
    "the bearer of bad news",                   # 'bearer' in prose
    "see https://example.com/Users/guide",      # /Users inside a URL path, not a home dir
    "src/home/page.py",                         # relative path containing 'home'
    "ratio 3@4",                                # '@' with no domain
])
def test_leaves_lookalikes_alone(text):
    """Strings that only look like secrets or home paths are not changed, so the logs stay
    readable for P5."""
    assert redact(text) == text


@pytest.mark.req("INST-09")
def test_redacts_nested_structures_and_is_idempotent():
    """redact() walks dicts and lists, leaves non-strings alone, and running it twice gives the
    same result as running it once."""
    data = {"a": ["x@y.io", {"b": "/home/z/f"}], "n": 3, "none": None}
    once = redact(data)
    assert once == {"a": ["[EMAIL]", {"b": "~/f"}], "n": 3, "none": None}
    assert redact(once) == once


SECRETS = ("me@example.com", "sk-ant-api03-SECRETSECRETSECRET99", "ghp_SECRETSECRETSECRETSECRET",
           "Bearer SECRETSECRETSECRETSECRET", "/Users/someone")


@pytest.mark.req("INST-09")
@pytest.mark.kind("integration")
def test_no_secret_reaches_events_jsonl(tmp_path):
    """End to end: a prompt and a Stop message that carry every secret class produce an
    events.jsonl file containing none of them."""
    blob = " | ".join(SECRETS)
    run_hook(tmp_path, {"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": blob})
    run_hook(tmp_path, {"hook_event_name": "Stop", "session_id": "s", "last_assistant_message": blob})
    raw = (tmp_path / "logs" / "events.jsonl").read_text()
    assert len(events(tmp_path)) == 2
    for s in SECRETS:
        assert s not in raw


@pytest.mark.req("INST-09")
def test_stop_excerpt_redacts_before_truncating(tmp_path):
    """A token straddling the 1,000-char cut is redacted, not left as a partial key that's too
    short to match."""
    # The space matters: the sk- pattern requires a word boundary, so "task-management-…" is not
    # redacted (see test_leaves_lookalikes_alone). The redacted token then spans chars 990-1005.
    msg = "x" * 989 + " sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUV"
    run_hook(tmp_path, {"hook_event_name": "Stop", "session_id": "s", "last_assistant_message": msg})
    excerpt = events(tmp_path)[0]["payload"]["response_excerpt"]
    assert "sk-ant" not in excerpt and excerpt.endswith("[REDACTED_")


@pytest.mark.req("INST-09", "INST-03")
@pytest.mark.kind("recovery")
def test_hook_errors_log_is_redacted(tmp_path):
    """Malformed input containing secrets is quoted in hook_errors.log only in redacted form,
    including the home path in the traceback."""
    run_hook(tmp_path, "{broken " + " ".join(SECRETS))
    log = errors(tmp_path)
    assert "Traceback" in log
    for s in SECRETS:
        assert s not in log
