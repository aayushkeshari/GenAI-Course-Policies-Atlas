"""VAL-04: fault injection runs on a temp copy, records which tests catch each fault, and lists uncaught faults."""
import hashlib
import json
from pathlib import Path

import pytest

from hookutil import ROOT
from src.validation import faults as F
from src.validation.redact import scrub

CONFTEST = (ROOT / "tests" / "conftest.py").read_text()
MOD = "def add(a, b):\n    return a + b\n\n\ndef unused(x):\n    return x * 2\n"
TEST = ('import pytest\nfrom mod import add\n\n\n@pytest.mark.req("VAL-04")\ndef test_add():\n'
        '    """add adds."""\n    assert add(2, 3) == 5\n\n\ndef test_truth():\n    assert True\n')
TINY_FAULTS = [
    {"id": "T1", "title": "caught", "category": "x", "description": "add subtracts", "file": "mod.py",
     "old": "return a + b", "new": "return a - b"},
    {"id": "T2", "title": "uncaught", "category": "x", "description": "untested code changes", "file": "mod.py",
     "old": "return x * 2", "new": "return x * 3"},
]


def tiny_repo(root: Path, test=TEST) -> Path:
    (root / "tests").mkdir(parents=True)
    (root / "pytest.ini").write_text("[pytest]\ntestpaths = tests\npythonpath = .\n")
    (root / "tests" / "conftest.py").write_text(CONFTEST)
    (root / "tests" / "test_mod.py").write_text(test)
    (root / "mod.py").write_text(MOD)
    return root


def tree_hash(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


@pytest.mark.req("VAL-04")
@pytest.mark.kind("fault")
def test_runner_records_caught_and_uncaught_faults_without_touching_the_repo(tmp_path):
    """On a tiny repo with two faults, the runner reports one caught (by exactly the test that checks it) and
    one uncaught, with detection rate 0.5 and the uncaught fault listed. The source repo is byte-identical
    afterwards (faults are applied only to a temp copy) and only the report file is written. T1 is a same-size
    edit applied within a second of the baseline, so this also proves no stale bytecode is reused."""
    repo = tiny_repo(tmp_path / "repo")
    before = tree_hash(repo)
    out = tmp_path / "faults.json"
    report = F.run(repo=repo, out=out, faults=TINY_FAULTS, log=lambda *_: None)
    assert tree_hash(repo) == before
    assert json.loads(out.read_text()) == report
    by_id = {f["id"]: f for f in report["faults"]}
    assert by_id["T1"]["caught"] and by_id["T1"]["caught_by"] == ["tests/test_mod.py::test_add"]
    assert not by_id["T2"]["caught"] and by_id["T2"]["caught_by"] == []
    assert (report["n_faults"], report["n_caught"], report["detection_rate"], report["uncaught"]) == (2, 1, 0.5, ["T2"])
    assert report["baseline"]["n_tests"] == 2


@pytest.mark.req("VAL-04")
@pytest.mark.kind("fault")
def test_a_fault_must_match_exactly_once(tmp_path):
    """A fault whose old text is missing or appears twice is rejected before any run, so a stale fault can
    never be reported as 'uncaught' when it was never applied."""
    repo = tiny_repo(tmp_path / "repo")
    missing = {**TINY_FAULTS[0], "old": "return a * b"}
    twice = {**TINY_FAULTS[0], "old": "return "}
    for fault, n in ((missing, 0), (twice, 2)):
        with pytest.raises(ValueError, match=f"found {n}"):
            F.apply(repo, fault)
    assert (repo / "mod.py").read_text() == MOD
    with pytest.raises(ValueError):
        F.run(repo=repo, out=tmp_path / "o.json", faults=[missing], log=lambda *_: None)
    assert not (tmp_path / "o.json").exists()


@pytest.mark.req("VAL-04")
@pytest.mark.kind("fault")
def test_baseline_must_be_clean(tmp_path):
    """If the unmodified copy already has a failing test, the runner stops without writing a report, because
    'caught' would be meaningless."""
    repo = tiny_repo(tmp_path / "repo", test=TEST + "\n\ndef test_broken():\n    assert False\n")
    with pytest.raises(RuntimeError, match="baseline run is not clean"):
        F.run(repo=repo, out=tmp_path / "o.json", faults=TINY_FAULTS, log=lambda *_: None)
    assert not (tmp_path / "o.json").exists()


@pytest.fixture(scope="module")
def report():
    return json.loads((ROOT / "results" / "faults.json").read_text())


@pytest.mark.req("VAL-04")
def test_committed_fault_report_is_current_and_consistent(report):
    """results/faults.json covers at least 8 faults, is for exactly the faults defined in src/validation/faults.py,
    and each fault's old text still occurs exactly once in the repo (so the report is not for stale code).
    Counts, rate and the uncaught list agree with the per-fault results; only F09 includes the UI tests."""
    assert report["n_faults"] == len(report["faults"]) == len(F.FAULTS) >= 8
    keys = ("id", "title", "category", "description", "file", "old", "new")
    assert [{k: f[k] for k in keys} for f in report["faults"]] == [{k: f[k] for k in keys} for f in F.FAULTS]
    for f in F.FAULTS:
        assert (ROOT / f["file"]).read_text().count(f["old"]) == 1, f["id"]
    caught = [f for f in report["faults"] if f["caught"]]
    assert report["n_caught"] == len(caught)
    assert report["detection_rate"] == round(len(caught) / report["n_faults"], 4)
    assert report["uncaught"] == [f["id"] for f in report["faults"] if not f["caught"]]
    for f in report["faults"]:
        assert f["caught"] == bool(f["caught_by"]) and f["n_caught_by"] == len(f["caught_by"])
    assert [f["id"] for f in report["faults"] if f["ui_tests_included"]] == ["F09"]
    for f in report["faults"]:
        assert sorted(f["caught_by_golden"] + f["caught_by_behavioral"]) == f["caught_by"]
        assert f["golden_only"] == (f["caught"] and not f["caught_by_behavioral"])
    n_beh = sum(bool(f["caught_by_behavioral"]) for f in report["faults"])
    assert report["n_caught_behavioral"] == n_beh
    assert report["behavioral_detection_rate"] == round(n_beh / report["n_faults"], 4)
    assert report["golden_only"] == [f["id"] for f in report["faults"] if f["golden_only"]]


@pytest.mark.req("VAL-04")
def test_fault_report_published_with_redacted_node_ids(report):
    """site/validation/data/faults.json is results/faults.json with caught_by node IDs passed through the same
    redaction as tests.json, and every catching test exists in the explorer's snapshot run."""
    site = json.loads((ROOT / "site" / "validation" / "data" / "faults.json").read_text())
    expected = json.loads(json.dumps(report))
    for f in expected["faults"]:
        f["caught_by"] = [scrub(n) for n in f["caught_by"]]
    assert site == expected
    known = {t["nodeid"] for t in json.loads((ROOT / "site/validation/data/tests.json").read_text())["tests"]}
    for f in site["faults"]:
        assert set(f["caught_by"]) <= known, f["id"]


@pytest.mark.req("VAL-04")
def test_make_faults_target():
    """`make faults` runs the fault-injection module."""
    import subprocess
    out = subprocess.run(["make", "-n", "faults"], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout
    assert "-m src.validation.faults" in out


@pytest.mark.req("VAL-04")
@pytest.mark.parametrize("nodeid,golden", [
    ("tests/test_anl_inference.py::test_committed_regression_is_current", True),
    ("tests/test_anl_clean.py::test_committed_clean_data_and_log_are_current", True),
    ("tests/test_x.py::test_thing_is_current[seed7]", True),
    ("tests/test_anl_eval.py::test_cohen_kappa_known_values", False),
    ("tests/test_x.py::test_is_currently_wrong", False),
])
def test_golden_file_tests_are_classified_by_name(nodeid, golden):
    """Tests whose name ends in _is_current / _are_current (optionally parametrized) count as golden-file
    tests; everything else counts as behavioural."""
    assert bool(F.GOLDEN.search(nodeid)) is golden
