"""INST-07: the conftest plugin writes a machine-readable run file in the VAL-01 format.

Each test copies tests/conftest.py into an isolated pytester project, runs pytest there in a
subprocess, and inspects the run file it produces.
"""
import json
from pathlib import Path

import pytest

CONFTEST = (Path(__file__).parent / "conftest.py").read_text()
FIELDS = {"nodeid", "req_ids", "phase", "kind", "status", "duration_s", "failure_message",
          "docstring", "source"}

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
    data = json.loads(files[0].read_text())
    return data, {t["nodeid"].split("::")[-1]: t for t in data["tests"]}


@pytest.mark.req("INST-07")
@pytest.mark.kind("integration")
def test_every_test_has_all_val01_fields(runfile):
    """Every test entry has every VAL-01 field (nodeid, req_ids, phase, kind, status,
    duration_s, failure_message, docstring, source), and every executed test appears."""
    data, tests = runfile
    assert data["schema"] == "test-run/1"
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


@pytest.mark.req("INST-07")
@pytest.mark.kind("integration")
def test_messages_docstrings_and_source_captured(runfile):
    """failure_message holds the assertion text, skip reason, or setup error. docstring and
    source come from the test function. Passing tests have an empty message."""
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


@pytest.mark.req("INST-07")
@pytest.mark.kind("integration")
def test_each_run_writes_a_new_file(pytester):
    """Two runs produce two distinct run files. Earlier runs are never overwritten."""
    pytester.makepyfile(test_one="def test_a():\n    pass\n")
    run(pytester)
    _, files = run(pytester)
    assert len(files) == 2
