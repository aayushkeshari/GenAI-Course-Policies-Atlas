"""P4 validation data: site/validation/data/ is a faithful, reproducible snapshot of one `make test` run."""
import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from hookutil import ROOT
from src.report import build_validation_data as V
from src.validation import runs as R
from src.validation.redact import scrub
from src.validation.specs import requirements

OUT = ROOT / "site" / "validation" / "data"
SITE = ROOT / "site"


def j(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifest():
    return j("manifest.json")


@pytest.mark.req("VAL-02", "VAL-03")
@pytest.mark.kind("integration")
def test_validation_data_is_current(tmp_path, manifest):
    """Rebuilding from the run named in manifest.json reproduces every file in site/validation/data/ byte for byte.
    So the committed explorer data is exactly what `make report` derives from committed inputs (run files,
    bodies, coverage summary, specs, review log, claims, faults and recovery results)."""
    written = V.build(run=manifest["run"], out=tmp_path)
    committed = sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*") if p.is_file())
    assert committed == written
    for name in written:
        assert (OUT / name).read_bytes() == (tmp_path / name).read_bytes(), name


@pytest.mark.req("VAL-01", "VAL-05")
def test_tests_json_is_the_snapshot_run_with_bodies(manifest):
    """tests.json holds every test of the snapshot run with all VAL-01 fields, and each docstring and source
    is the verified text of its body file, passed through the site redaction (scrub) and nothing else."""
    run = R.load_run(R.RUNS / manifest["run"])
    tests = j("tests.json")
    assert tests["run"] == manifest["run"] and tests["n"] == len(run["tests"]) > 400
    by_id = {scrub(t["nodeid"]): t for t in run["tests"]}
    assert len(by_id) == len(run["tests"])
    for t in tests["tests"]:
        src = by_id[t["nodeid"]]
        for k in ("req_ids", "phase", "kind", "status", "duration_s", "body_sha256"):
            assert t[k] == src[k], (t["nodeid"], k)
        for k in ("failure_message", "docstring", "source"):
            assert t[k] == scrub(src[k]), (t["nodeid"], k)
        assert t["source"].lstrip().startswith(("@", "def ")), t["nodeid"]


@pytest.mark.req("VAL-02")
def test_history_has_every_run_and_matches_each_run_file(manifest):
    """history.json lists every run file up to the snapshot, oldest first (none dropped), and each test's
    status letter for a run equals that run file's recorded status ('.' when the test didn't exist)."""
    h = j("history.json")
    files = [f for f in R.run_files() if f.name <= manifest["run"]]
    assert [r["file"] for r in h["runs"]] == [f.name for f in files]
    assert manifest["n_runs"] == len(files) >= 55
    for i in (0, len(files) // 2, len(files) - 1):
        recorded = {scrub(t["nodeid"]): t["status"] for t in json.loads(files[i].read_text())["tests"]}
        for nodeid, letters in h["tests"].items():
            assert len(letters) == len(files)
            assert letters[i] == V.STATUS_CODE.get(recorded.get(nodeid), "."), (files[i].name, nodeid)


@pytest.mark.req("VAL-03")
def test_traceability_covers_every_requirement_with_correct_status():
    """traceability.json has one row per spec requirement, with its full text. Each row's tests are exactly the
    snapshot tests tagged with that ID, and its status is the rollup of their statuses (untested when none)."""
    t = j("traceability.json")
    tests = j("tests.json")["tests"]
    reqs = requirements()
    assert [r["id"] for r in t["requirements"]] == [r["id"] for r in reqs]
    for row, spec in zip(t["requirements"], reqs):
        assert row["text"] == scrub(spec["text"]) and row["spec"] == spec["spec"]
        linked = [x for x in tests if row["id"] in x["req_ids"]]
        assert row["tests"] == [x["nodeid"] for x in linked]
        assert row["status"] == V.rollup([x["status"] for x in linked])
    assert sum(t["counts"].values()) == 75


@pytest.mark.req("VAL-03")
@pytest.mark.parametrize("statuses,expected", [
    ([], "untested"), (["passed"], "passing"), (["passed", "xfailed"], "passing"),
    (["passed", "skipped"], "partial"), (["passed", "failed"], "failing"), (["error"], "failing"),
    (["xpassed"], "failing"), (["skipped", "failed"], "failing")])
def test_rollup_rule(statuses, expected):
    """A requirement fails if any linked test failed, errored or unexpectedly passed; it is untested with no
    tests, passing when all passed (or xfailed as expected), and partial when some were skipped."""
    assert V.rollup(statuses) == expected


@pytest.mark.req("VAL-03")
def test_coverage_is_per_module_for_the_snapshot_run(manifest):
    """coverage.json is the archived pytest-cov summary of the snapshot run: one row per src/ module, with
    statement, missing and percent figures that add up to the totals."""
    cov = j("coverage.json")
    assert cov["run"] == manifest["run"]
    modules = {m["module"] for m in cov["modules"]}
    assert {str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")} <= modules
    assert sum(m["statements"] for m in cov["modules"]) == cov["totals"]["statements"]
    assert sum(m["missing"] for m in cov["modules"]) == cov["totals"]["missing"]
    for m in cov["modules"]:
        assert 0 <= m["percent"] <= 100


@pytest.mark.req("VAL-03")
def test_attach_coverage_refuses_a_report_from_another_run(tmp_path):
    """The per-run coverage archive is written only if the report's timestamp falls inside the newest run's
    start..end(+2 min) window, so a stale report is never attributed to the wrong run."""
    run = {"schema": "test-run/2", "started": "2026-11-08T10:00:00.000-05:00",
           "finished": "2026-11-08T10:00:20.000-05:00", "tests": []}
    (tmp_path / "run-20261108T100000.000000-0500.json").write_text(json.dumps(run))
    cov = {"meta": {"timestamp": "2026-11-08T10:00:19.5", "version": "x"},
           "files": {"src/a.py": {"summary": {"num_statements": 4, "missing_lines": 1, "percent_covered": 75.0}}},
           "totals": {"num_statements": 4, "missing_lines": 1, "percent_covered": 75.0}}
    (tmp_path / "cov.json").write_text(json.dumps(cov))
    out = R.attach_coverage(tmp_path / "cov.json", tmp_path)
    assert json.loads(out.read_text())["modules"][0]["percent"] == 75.0
    cov["meta"]["timestamp"] = "2026-11-08T09:00:00"
    (tmp_path / "cov.json").write_text(json.dumps(cov))
    with pytest.raises(ValueError, match="not written during"):
        R.attach_coverage(tmp_path / "cov.json", tmp_path)


@pytest.mark.req("VAL-05")
def test_snapshot_is_a_make_test_run_and_unknown_runs_fail(tmp_path):
    """Without a named run, the snapshot is the newest run that has an archived coverage summary (a full
    `make test` run, not an ad-hoc partial pytest run). Naming a run that doesn't exist stops the build."""
    snap = V.snapshot_run()
    assert (R.RUNS / "coverage" / snap).exists()
    newer = [f for f in R.run_files() if f.name > snap and (R.RUNS / "coverage" / f.name).exists()]
    assert not newer
    with pytest.raises(SystemExit):
        V.build(run="run-19990101T000000.000000-0500.json", out=tmp_path)


@pytest.mark.req("VAL-07")
def test_review_log_is_copied_verbatim():
    """The explorer's review log is docs/review-log.md byte for byte (Aayush's manual reviews, unedited)."""
    assert (OUT / "review-log.md").read_bytes() == (ROOT / "docs" / "review-log.md").read_bytes()


@pytest.mark.req("DASH-01", "VAL-05")
def test_truth_derived_results_only_in_the_validation_recovery_view():
    """The three truth-derived results are byte-for-byte copies under site/validation/data/recovery/ and nowhere
    else in site/. ground_truth.json is nowhere in site/. Nothing under site/dashboard/ references the
    validation data, and the builder never reads data/raw/ or imports src.evaluation."""
    for name in V.RECOVERY_FILES:
        assert (OUT / "recovery" / name).read_bytes() == (ROOT / "results" / name).read_bytes()
        found = [p for p in SITE.rglob(name)]
        assert found == [OUT / "recovery" / name], found
    assert not list(SITE.rglob("ground_truth*"))
    for p in (SITE / "dashboard").rglob("*"):
        if p.is_file():
            assert "validation/data" not in p.read_text(encoding="utf-8"), p.name
    src = Path(V.__file__).read_text(encoding="utf-8")
    assert "data/raw" not in src and '"raw"' not in src
    imports = [n for n in ast.walk(ast.parse(src)) if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = [a.name for n in imports for a in n.names] + [n.module or "" for n in imports if isinstance(n, ast.ImportFrom)]
    assert not any(x.startswith("src.evaluation") for x in names)


@pytest.mark.req("VAL-05")
def test_no_private_data_in_the_validation_site():
    """No string under site/validation/ (decoded JSON keys/values, or raw text for other files) contains the
    home directory, a /Users/ or /home/ path, an email address, or a credential-like string. Test sources,
    failure messages and the review log are published, so this is checked on the output."""
    bans = [re.compile(re.escape(str(Path.home()))), re.compile(r"/Users/|/home/\w|C:\\Users"),
            re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"), re.compile(r"sk-[A-Za-z0-9]{20,}"),
            re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}")]
    for p in (SITE / "validation").rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            if p.suffix == ".json":
                text = "\n".join(_strings(json.loads(text)))
            for pat in bans:
                m = pat.search(text)
                assert not m, (p.name, m and m.group())


@pytest.mark.req("VAL-05")
@pytest.mark.parametrize("raw,clean", [
    ("cd '/Users/alice' && ls", "cd '‹redacted-path›' && ls"),
    ("see a@b.org now", "see ‹redacted-email› now"),
    ('api_key = "abcdefghij"', "api_key = ‹redacted-secret›"),
    ("sk-" + "A" * 24, "‹redacted-secret›"),
    ("\n@pytest.mark.req('X')", "\n@pytest.mark.req('X')"),
])
def test_scrub_replaces_fixture_secrets_with_visible_placeholders(raw, clean):
    """Fake home paths, emails and credential-like strings in published test text become visible
    ‹redacted-…› placeholders; ordinary decorators are untouched."""
    assert scrub(raw) == clean
    assert scrub(str(Path.home()) + "/x") == "~/x"


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


@pytest.mark.req("VAL-05")
def test_every_data_file_is_labelled_synthetic(manifest):
    """Every JSON file the explorer loads carries synthetic: true, and the manifest's input hashes match
    the files on disk."""
    for p in OUT.rglob("*.json"):
        assert json.loads(p.read_text())["synthetic"] is True, p.name
    for rel, sha in manifest["inputs"].items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha, rel
