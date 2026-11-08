"""INST-07 / VAL-01 / VAL-02: the conftest plugin writes a machine-readable run file in the VAL-01 format.

Each test copies tests/conftest.py into an isolated pytester project, runs pytest there in a
subprocess, and inspects the run file it produces.
"""
import hashlib
import json
from pathlib import Path

import pytest

from src.validation.runs import canonical_body, load_run

CONFTEST = (Path(__file__).parent / "conftest.py").read_text()
FIELDS = {"nodeid", "req_ids", "phase", "kind", "status", "duration_s", "failure_message",
          "body_sha256"}

SAMPLE = '''
import pytest
from pathlib import Path

@pytest.mark.req("DATA-03")
@pytest.mark.kind("property")
def test_pass():
    """Proves the passing path."""
    assert 1

@pytest.mark.req("INST-01", "VAL-02")
def test_fail():
    """Proves the failing path."""
    assert 1 == 2, "boom-marker"

@pytest.mark.skip(reason="skip-reason-marker")
@pytest.mark.req("TOK-01")
def test_skip():
    pass

def test_untagged():
    pass

@pytest.fixture
def broken():
    raise RuntimeError("setup-broke-marker")

def test_error(broken):
    pass

@pytest.mark.xfail(reason="known")
def test_xfail():
    assert 0

def test_home_leak():
    assert str(Path.home()) == "nope"
'''


def run(pytester, *args):
    pytester.makeconftest(CONFTEST)
    result = pytester.runpytest_subprocess(*args)
    files = sorted((pytester.path / "results" / "tests").glob("run-*.json"))
    return result, files


@pytest.fixture
def runfile(pytester):
    pytester.makepyfile(test_sample=SAMPLE)
    _, files = run(pytester)
    assert len(files) == 1
    data = load_run(files[0])  # resolves docstring/source from the body sidecar
    return data, {t["nodeid"].split("::")[-1]: t for t in data["tests"]}


@pytest.mark.req("INST-07", "VAL-01")
@pytest.mark.kind("integration")
def test_every_test_has_all_val01_fields(runfile):
    """Every test entry has every VAL-01 field (nodeid, req_ids, phase, kind, status,
    duration_s, failure_message, body_sha256), and every executed test appears."""
    data, tests = runfile
    assert data["schema"] == "test-run/2"
    assert len(tests) == 7
    for t in tests.values():
        assert FIELDS <= set(t), FIELDS - set(t)
        assert isinstance(t["duration_s"], float) and t["duration_s"] >= 0


@pytest.mark.req("INST-07")
@pytest.mark.kind("integration")
def test_statuses_cover_every_outcome(runfile):
    """Pass, fail, skip, fixture-setup error and xfail are each recorded with the right status,
    and the summary counts match."""
    data, tests = runfile
    assert {n: t["status"] for n, t in tests.items()} == {
        "test_pass": "passed", "test_fail": "failed", "test_skip": "skipped",
        "test_untagged": "passed", "test_error": "error", "test_xfail": "xfailed",
        "test_home_leak": "failed"}
    assert data["summary"] == {"passed": 2, "failed": 2, "skipped": 1, "error": 1, "xfailed": 1}
    assert data["exit_status"] == 1


@pytest.mark.req("INST-07")
@pytest.mark.kind("integration")
def test_phase_from_first_req_prefix_and_kind_default(runfile):
    """phase comes from the first req ID's area (DATA -> P1, INST -> P0, TOK -> P6),
    not from .phase. With no req, phase is "untagged". kind defaults to unit."""
    data, tests = runfile
    assert (tests["test_pass"]["req_ids"], tests["test_pass"]["phase"]) == (["DATA-03"], "P1")
    assert (tests["test_fail"]["req_ids"], tests["test_fail"]["phase"]) == (["INST-01", "VAL-02"], "P0")
    assert tests["test_skip"]["phase"] == "P6"
    assert (tests["test_untagged"]["req_ids"], tests["test_untagged"]["phase"]) == ([], "untagged")
    assert tests["test_pass"]["kind"] == "property"
    assert tests["test_fail"]["kind"] == "unit"
    assert data["current_phase"] == "untagged"  # no .phase in the pytester project


@pytest.mark.req("INST-07", "VAL-01")
@pytest.mark.kind("integration")
def test_messages_docstrings_and_source_captured(runfile):
    """failure_message holds the assertion text, skip reason, or setup error. docstring and
    source come from the test function (read back through the body sidecar). Passing tests
    have an empty message."""
    _, tests = runfile
    assert "boom-marker" in tests["test_fail"]["failure_message"]
    assert "skip-reason-marker" in tests["test_skip"]["failure_message"]
    assert "setup-broke-marker" in tests["test_error"]["failure_message"]
    assert tests["test_pass"]["failure_message"] == ""
    assert tests["test_pass"]["docstring"] == "Proves the passing path."
    assert tests["test_fail"]["source"].startswith('@pytest.mark.req("INST-01", "VAL-02")')
    assert "def test_fail():" in tests["test_fail"]["source"]


@pytest.mark.req("INST-07")
@pytest.mark.kind("integration")
def test_home_directory_scrubbed_from_run_file(pytester):
    """The home directory path never appears in the run file (it may be published in P4/P7).
    It's replaced with ~."""
    pytester.makepyfile(test_sample=SAMPLE)
    _, files = run(pytester)
    text = files[0].read_text()
    assert str(Path.home()) not in text
    assert "~" in json.loads(text)["tests"][-1]["failure_message"]
    for body in (files[0].parent / "bodies").glob("*.json"):
        assert str(Path.home()) not in body.read_text()


@pytest.mark.req("INST-07")
@pytest.mark.kind("recovery")
def test_collection_error_still_writes_run_file(pytester):
    """A test module that fails to import still produces a run file, with the error under
    collection_errors."""
    pytester.makepyfile(test_broken="import nonexistent_module_xyz\n")
    _, files = run(pytester)
    data = json.loads(files[0].read_text())
    assert data["collection_errors"]
    assert "nonexistent_module_xyz" in data["collection_errors"][0]["message"]


@pytest.mark.req("INST-07", "VAL-02")
@pytest.mark.kind("integration")
def test_each_run_writes_a_new_file(pytester):
    """Two runs produce two distinct run files. Earlier runs are never overwritten."""
    pytester.makepyfile(test_one="def test_a():\n    pass\n")
    run(pytester)
    _, files = run(pytester)
    assert len(files) == 2


@pytest.mark.req("VAL-01", "VAL-02")
@pytest.mark.kind("integration")
def test_bodies_are_content_addressed_and_written_once(pytester):
    """Each body file's SHA-256 equals its name, and every body_sha256 in the run has a file.
    A second run of unchanged tests adds a run file but no body files and leaves existing
    body files byte-identical. Editing one test adds exactly one body file and keeps the old one."""
    pytester.makepyfile(test_sample=SAMPLE)
    _, files = run(pytester)
    bodies = files[0].parent / "bodies"
    before = {p.name: p.read_bytes() for p in bodies.glob("*.json")}
    assert len(before) == 7
    for name, raw in before.items():
        assert hashlib.sha256(raw).hexdigest() + ".json" == name
    shas = {t["body_sha256"] for t in json.loads(files[0].read_text())["tests"]}
    assert {s + ".json" for s in shas} == set(before)
    _, files = run(pytester)
    assert len(files) == 2
    assert {p.name: p.read_bytes() for p in bodies.glob("*.json")} == before
    pytester.makepyfile(test_sample=SAMPLE.replace("Proves the passing path.", "Proves it, edited."))
    run(pytester)
    after = {p.name for p in bodies.glob("*.json")}
    assert len(after) == 8 and set(before) <= after


@pytest.mark.req("VAL-01")
def test_plugin_and_reader_agree_on_body_bytes():
    """tests/conftest.py and src/validation/runs.py produce the same canonical body bytes, so the
    reader's hash check accepts what the plugin writes (including non-ASCII text)."""
    import conftest
    for doc, src in [("", ""), ("Doc — ü", "def f():\n    pass\n"), ('q "x"', "a\tb")]:
        assert conftest.canonical_body(doc, src) == canonical_body(doc, src)


@pytest.mark.req("VAL-01", "VAL-02")
def test_reader_accepts_old_inline_format_and_rejects_tampered_bodies(tmp_path):
    """A test-run/1 file (docstring/source inline) loads with a computed body_sha256. A body file
    whose bytes don't hash to its name is rejected, so the explorer can't show the wrong source."""
    old = {"schema": "test-run/1", "tests": [{"nodeid": "t::a", "docstring": "D", "source": "S"}]}
    (tmp_path / "run-1.json").write_text(json.dumps(old))
    t = load_run(tmp_path / "run-1.json")["tests"][0]
    assert t["body_sha256"] == hashlib.sha256(canonical_body("D", "S")).hexdigest()
    sha = t["body_sha256"]
    (tmp_path / "bodies").mkdir()
    (tmp_path / "bodies" / f"{sha}.json").write_bytes(canonical_body("D", "tampered"))
    new = {"schema": "test-run/2", "tests": [{"nodeid": "t::a", "body_sha256": sha}]}
    (tmp_path / "run-2.json").write_text(json.dumps(new))
    with pytest.raises(ValueError, match="does not hash"):
        load_run(tmp_path / "run-2.json")


@pytest.mark.req("VAL-02")
def test_every_committed_run_file_loads():
    """Every run file in results/tests/ (old and new format) loads, and every new-format run's
    bodies resolve and verify. Nothing has been pruned or corrupted."""
    from src.validation.runs import run_files
    files = run_files()
    assert len(files) >= 54
    for f in files:
        run = load_run(f)
        assert run["tests"], f.name
