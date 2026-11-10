"""P4: build site/validation/data/ for the validation explorer (run by `make report`, after build_site_data).

The snapshot is one `make test` run: the newest run file that has an archived coverage summary in
results/tests/coverage/ (VAL-03), unless a run is named. Every input is an immutable or committed file,
so rebuilding from the run named in manifest.json reproduces the output byte for byte.

Published test text (node IDs, sources, docstrings, failure messages) passes through src.validation.redact,
because some test fixtures are fake home paths, tokens or emails that must never appear under site/.

Outputs (all JSON is sorted, compact and synthetic-labelled):
  manifest.json       snapshot run, inputs and their SHA-256
  tests.json          the snapshot run's tests with docstring, source and failure message (VAL-01, VAL-05)
  history.json        every run up to the snapshot, plus one status letter per run for each test (VAL-02)
  traceability.json   spec requirement -> tests -> status (VAL-03)
  coverage.json       per-module line coverage of src/ for the snapshot run (VAL-03)
  faults.json         results/faults.json from `make faults`, with caught_by node IDs redacted like tests.json (VAL-04)
  claims.json         dashboard findings -> supporting tests (VAL-06)
  review-log.md       copy of docs/review-log.md (VAL-07)
  recovery/*.json     the truth-derived results, copied byte for byte. They are shown ONLY on the explorer's
                      "Recovery vs. ground truth (validation only)" view and never reach site/data/ or the dashboard.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import jsonschema

from src.validation.redact import scrub
from src.validation.runs import load_run, run_files
from src.validation.specs import requirements

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "results" / "tests"
RESULTS = ROOT / "results"
SPECS = ROOT / "specs"
REVIEW_LOG = ROOT / "docs" / "review-log.md"
CLAIMS = Path(__file__).resolve().parent / "claims.json"
OUT = ROOT / "site" / "validation" / "data"
SCHEMAS = Path(__file__).resolve().parent / "schemas"

RECOVERY_FILES = ["recovery.json", "rhetoric_recovery.json", "coder_dev_eval.json"]
NOTE = ("SYNTHETIC DATA: real university names are attached to invented policies and statements. "
        "This file describes the project's tests, not findings.")
STATUS_CODE = {"passed": "p", "failed": "f", "error": "e", "skipped": "s", "xfailed": "x", "xpassed": "X"}
BAD = {"failed", "error", "xpassed"}
REDACTION_NOTE = ("Test text is published with fake fixture values replaced: home paths, emails and "
                  "credential-like strings appear as ‹redacted-…› placeholders.")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                    encoding="utf-8")


def snapshot_run(runs_dir: Path = RUNS) -> str:
    """Name of the newest run file that has an archived coverage summary (i.e. a `make test` run)."""
    covered = {p.name for p in (Path(runs_dir) / "coverage").glob("run-*.json")}
    runs = [p.name for p in run_files(runs_dir) if p.name in covered]
    if not runs:
        raise SystemExit("no `make test` run with coverage in results/tests/: run `make test` first")
    return runs[-1]


def _scrub_test(t: dict) -> dict:
    keep = ("nodeid", "req_ids", "phase", "kind", "file", "line", "status", "duration_s",
            "failure_message", "docstring", "source", "body_sha256")
    return {k: scrub(t[k]) if isinstance(t.get(k), str) and k not in ("body_sha256", "status", "kind", "phase")
            else t.get(k) for k in keep}


def rollup(statuses: list[str]) -> str:
    """Requirement status from its tests' statuses."""
    if any(s in BAD for s in statuses):
        return "failing"
    if not statuses:
        return "untested"
    if all(s in ("passed", "xfailed") for s in statuses):
        return "passing"
    return "partial"  # some linked tests were skipped


def _phase_number(phase: str) -> int | None:
    head = (phase or "").split(":")[0]
    return int(head[1:]) if head[:1] == "P" and head[1:].isdigit() else None


def history(files: list[Path], nodeids: list[str]) -> dict:
    runs, letters = [], {n: [] for n in nodeids}
    for f in files:
        run = json.loads(f.read_text(encoding="utf-8"))  # bodies not needed for history
        by_id = {scrub(t["nodeid"]): t["status"] for t in run["tests"]}
        runs.append({"file": f.name, "started": run["started"], "git_commit": run.get("git_commit"),
                     "git_dirty": run.get("git_dirty"), "phase": run.get("current_phase"),
                     "summary": run["summary"], "n_tests": len(run["tests"]),
                     "make_test": "--cov=src" in run.get("args", [])})
        for n in nodeids:
            letters[n].append(STATUS_CODE.get(by_id.get(n), "."))
    return {"runs": runs, "codes": {**STATUS_CODE, "absent": "."},
            "tests": {n: "".join(v) for n, v in letters.items()}}


def traceability(reqs: list[dict], tests: list[dict], current_phase: str) -> dict:
    current = _phase_number(current_phase)
    rows = []
    for r in reqs:
        linked = [t for t in tests if r["id"] in t["req_ids"]]
        n = _phase_number(r["phase"])
        rows.append({**r, "tests": [t["nodeid"] for t in linked],
                     "status": rollup([t["status"] for t in linked]),
                     "phase_started": current is not None and n is not None and n <= current})
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"current_phase": current_phase, "counts": counts, "requirements": rows}


def claims(claims_path: Path, tests: list[dict]) -> dict:
    spec = json.loads(Path(claims_path).read_text(encoding="utf-8"))
    status = {t["nodeid"]: t["status"] for t in tests}
    out = []
    for c in spec["claims"]:
        sts = [status.get(n, "missing") for n in c["tests"]]
        out.append({**c, "test_status": dict(zip(c["tests"], sts)),
                    "status": "failing" if any(s in BAD or s == "missing" for s in sts) else rollup(sts)})
    return {"note": spec["note"], "claims": out}


def build(run: str | None = None, runs_dir: Path = RUNS, results: Path = RESULTS, specs_dir: Path = SPECS,
          review_log: Path = REVIEW_LOG, claims_path: Path = CLAIMS, out: Path = OUT) -> list[str]:
    runs_dir, results, out = Path(runs_dir), Path(results), Path(out)
    run = run or snapshot_run(runs_dir)
    files = [f for f in run_files(runs_dir) if f.name <= run]
    if not files or files[-1].name != run:
        raise SystemExit(f"run file {run} not found in {runs_dir}")
    latest = load_run(files[-1])
    cov_path = runs_dir / "coverage" / run
    cov = json.loads(cov_path.read_text(encoding="utf-8"))

    out.mkdir(parents=True, exist_ok=True)
    (out / "recovery").mkdir(exist_ok=True)
    written = []

    def put(name, obj):
        _dump(out / name, obj)
        written.append(name)

    tests = sorted((_scrub_test(t) for t in latest["tests"]), key=lambda t: t["nodeid"])
    if len({t["nodeid"] for t in tests}) != len(tests):
        raise SystemExit("redaction made two node IDs identical")
    put("tests.json", {"synthetic": True, "note": NOTE, "run": run, "started": latest["started"],
                       "git_commit": latest.get("git_commit"), "git_dirty": latest.get("git_dirty"),
                       "summary": latest["summary"], "redaction": REDACTION_NOTE,
                       "collection_errors": [{k: scrub(v) for k, v in e.items()}
                                             for e in latest.get("collection_errors", [])],
                       "n": len(tests), "tests": tests})
    put("history.json", {"synthetic": True, "note": NOTE,
                         **history(files, [t["nodeid"] for t in tests])})
    reqs = [{**r, "text": scrub(r["text"])} for r in requirements(specs_dir)]
    put("traceability.json", {"synthetic": True, "note": NOTE,
                              **traceability(reqs, tests, latest.get("current_phase", "untagged"))})
    put("coverage.json", {"synthetic": True, "note": NOTE, "run": run, "source": "pytest-cov, line coverage of src/",
                          **{k: v for k, v in cov.items() if k != "run"}})
    inputs = {}
    faults = results / "faults.json"
    if faults.exists():
        report = json.loads(faults.read_text(encoding="utf-8"))
        jsonschema.validate(report, json.loads((SCHEMAS / "faults.schema.json").read_text(encoding="utf-8")))
        for f in report["faults"]:
            f["caught_by"] = [scrub(n) for n in f["caught_by"]]
        put("faults.json", report)
        inputs["results/faults.json"] = _sha(faults)
    if Path(claims_path).exists():
        put("claims.json", {"synthetic": True, **claims(claims_path, tests)})
        inputs["src/report/claims.json"] = _sha(claims_path)
    shutil.copyfile(review_log, out / "review-log.md")
    written.append("review-log.md")
    for name in RECOVERY_FILES:
        shutil.copyfile(results / name, out / "recovery" / name)
        written.append(f"recovery/{name}")
        inputs[f"results/{name}"] = _sha(results / name)

    inputs["docs/review-log.md"] = _sha(review_log)
    inputs.update({f"specs/{p.name}": _sha(p) for p in sorted(Path(specs_dir).glob("*.md"))})
    inputs[f"results/tests/coverage/{run}"] = _sha(cov_path)
    put("manifest.json", {"synthetic": True, "note": NOTE, "run": run, "n_runs": len(files),
                          "first_run": files[0].name, "inputs": inputs, "files": sorted(written)})
    return sorted(written)


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    for name in build(run=argv[0] if argv else None):
        print(f"site/validation/data/{name}")


if __name__ == "__main__":
    main()
