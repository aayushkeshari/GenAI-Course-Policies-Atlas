"""Pytest plugin: write results/tests/run-<timestamp>.json for every run.

Requirement INST-07; the file format is defined by VAL-01. For each test it records nodeid,
req_ids, phase, kind, status, duration_s, failure_message, docstring and source.

- phase comes from the first requirement ID's area prefix (INST -> P0, DATA -> P1, ...), so an
  old test keeps its phase no matter what .phase says when the run happens. With no req marker,
  phase is "untagged".
- kind comes from @pytest.mark.kind("..."), default "unit".
- status is one of passed | failed | skipped | error | xfailed | xpassed.
- Every run file is kept (VAL-02). The home directory is replaced with "~" in all text.

This file holds only the plugin. Test helpers live in tests/hookutil.py, so test_runfile.py can
load this exact source into an isolated pytester project.
"""
import inspect
import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

SCHEMA = "test-run/1"
PHASE_BY_AREA = {"INST": "P0", "DATA": "P1", "ANL": "P2", "DASH": "P3",
                 "VAL": "P4", "PROV": "P5", "TOK": "P6", "PUB": "P7"}
KINDS = ("unit", "property", "integration", "recovery", "ui", "fault")
HOME = str(Path.home())


def _clean(text):
    return (text or "").replace(HOME, "~")


def _git(root, *args):
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def describe(item):
    """Static facts about a collected test item."""
    req_ids = []
    for mark in reversed(list(item.iter_markers("req"))):  # outermost (class/module) first
        for rid in mark.args:
            if rid not in req_ids:
                req_ids.append(rid)
    kind_mark = item.get_closest_marker("kind")
    fn = getattr(item, "function", None)
    try:
        source = inspect.getsource(fn) if fn else ""
    except (OSError, TypeError):
        source = ""
    path, line, _ = item.location
    return {
        "nodeid": item.nodeid,
        "req_ids": req_ids,
        "phase": PHASE_BY_AREA.get(req_ids[0].split("-")[0], "untagged") if req_ids else "untagged",
        "kind": kind_mark.args[0] if kind_mark and kind_mark.args else "unit",
        "file": path,
        "line": (line + 1) if line is not None else None,
        "docstring": (inspect.getdoc(fn) or "") if fn else "",
        "source": _clean(source),
    }


class RunRecorder:
    def __init__(self, config):
        self.root = Path(config.rootpath)
        self.args = [_clean(str(a)) for a in config.invocation_params.args]
        self.started = datetime.now().astimezone()
        self.meta = {}
        self.results = {}
        self.collection_errors = []
        self.git_commit = _git(self.root, "rev-parse", "HEAD")
        status = _git(self.root, "status", "--porcelain")
        self.git_dirty = None if status is None else bool(status)

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items):
        for item in items:
            self.meta[item.nodeid] = describe(item)

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append({"nodeid": report.nodeid,
                                           "message": _clean(report.longreprtext)})

    def pytest_runtest_logreport(self, report):
        r = self.results.setdefault(report.nodeid, {"status": None, "duration_s": 0.0, "messages": []})
        r["duration_s"] += report.duration
        xfail = hasattr(report, "wasxfail")
        if report.when == "setup":
            if report.failed:
                r["status"] = "error"
            elif report.skipped:
                r["status"] = "xfailed" if xfail else "skipped"
        elif report.when == "call":
            if xfail:
                r["status"] = "xfailed" if report.skipped else "xpassed"
            else:
                r["status"] = report.outcome
        elif report.failed and r["status"] in (None, "passed"):  # teardown failure
            r["status"] = "error"
        if report.failed or report.skipped:
            r["messages"].append(_clean(report.longreprtext))

    def build(self, exitstatus):
        finished = datetime.now().astimezone()
        tests = []
        for nodeid, r in self.results.items():
            info = self.meta.get(nodeid) or {"nodeid": nodeid, "req_ids": [], "phase": "untagged",
                                             "kind": "unit", "file": None, "line": None,
                                             "docstring": "", "source": ""}
            tests.append({**info, "status": r["status"] or "error",
                          "duration_s": round(r["duration_s"], 6),
                          "failure_message": "\n".join(m for m in r["messages"] if m)})
        summary = {}
        for t in tests:
            summary[t["status"]] = summary.get(t["status"], 0) + 1
        try:
            current_phase = (self.root / ".phase").read_text(encoding="utf-8").strip() or "untagged"
        except OSError:
            current_phase = "untagged"
        return {
            "schema": SCHEMA,
            "started": self.started.isoformat(timespec="milliseconds"),
            "finished": finished.isoformat(timespec="milliseconds"),
            "duration_s": round((finished - self.started).total_seconds(), 3),
            "exit_status": int(exitstatus),
            "python": platform.python_version(),
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "current_phase": current_phase,
            "args": self.args,
            "summary": summary,
            "collection_errors": self.collection_errors,
            "tests": tests,
        }

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        out_dir = self.root / "results" / "tests"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.started.strftime("%Y%m%dT%H%M%S.%f%z")
        path = out_dir / f"run-{stamp}.json"
        path.write_text(json.dumps(self.build(exitstatus), indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def pytest_configure(config):
    config.addinivalue_line("markers", "req(*ids): requirement ID(s) this test covers")
    config.addinivalue_line("markers", "kind(name): " + " | ".join(KINDS) + " (default: unit)")
    if not hasattr(config, "workerinput"):  # don't write a file per xdist worker
        config.pluginmanager.register(RunRecorder(config), "run_recorder")
