"""VAL-04 fault injection (`make faults`).

On a temporary copy of the repo, apply one deliberate bug at a time, run the test suite, and record which
tests caught it (tests that passed on the unmodified copy and fail or error with the fault). Writes
results/faults.json with the detection rate. Uncaught faults are listed, not hidden.

- Each fault is an exact text edit that must match exactly once, so a fault can never silently not apply.
- A baseline run on the unmodified copy must pass first; otherwise nothing is reported.
- The network-bound Playwright UI tests (tests/test_dash_ui.py, tests/test_val_ui.py) are left out of fault runs to
  keep `make faults` to a few minutes. They are included only for faults marked `ui` (the site-data fault).
- Fault runs write no bytecode cache, so every edit is compiled from source (a same-size edit within one
  second would otherwise reuse a stale .pyc).
- The fault runner's own tests (tests/test_val_faults.py) are always excluded: they run this runner and check
  its committed report, so inside a fault run they would recurse or check a report that is being rewritten.
- The real repo is never modified: no file in it is written except results/faults.json.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "faults.json"
UI_TESTS = ["tests/test_dash_ui.py", "tests/test_val_ui.py"]
SELF_TESTS = ["tests/test_val_faults.py"]  # they run this runner and check its committed report: never inside a fault run
SKIP_COPY = {".venv", ".git", "logs", "raw_logs", ".pytest_cache", "__pycache__", ".idea", "node_modules"}
# A golden-file ("is current") test re-derives a committed output and compares it byte for byte. It catches any
# change to the output, but says nothing about which property broke. Faults caught only by such tests are reported
# separately, so the headline rate isn't mistaken for behavioural coverage.
GOLDEN = re.compile(r"::test_\w*_(?:is|are)_current(?:\[|$)")
NOTE = ("SYNTHETIC DATA project. Each fault is a deliberate bug injected into a temporary copy of the repo; "
        "the committed code is unchanged.")

FAULTS = [
    {"id": "F01", "title": "Flip a regression sign", "category": "analysis",
     "description": "The term_index predictor enters the ordinal regression negated, so the time trend flips sign.",
     "file": "src/analysis/inference.py",
     "old": '"term_index": c["term_index"] * 1.0', "new": '"term_index": c["term_index"] * -1.0'},
    {"id": "F02", "title": "Skip dedupe", "category": "cleaning",
     "description": "Cleaning no longer drops exact duplicate rows.",
     "file": "src/analysis/clean.py",
     "old": 'df = df.drop_duplicates(keep="first").reset_index(drop=True)', "new": "df = df.reset_index(drop=True)"},
    {"id": "F03", "title": "Ignore the seed", "category": "data",
     "description": "The generator seeds its RNG with the constant default (2026) instead of the requested seed. "
                    "The default-seed dataset is unchanged, so only seed-sensitivity tests can notice.",
     "file": "src/data/generate.py",
     "old": "rng = random.Random(seed)", "new": "rng = random.Random(2026)"},
    {"id": "F04", "title": "Break a keyword rule", "category": "coding",
     "description": "The S-2-ban rule matches only the exact word 'banned', missing 'ban', 'bans', 'banning'.",
     "file": "src/analysis/code_text.py",
     "old": 'r"\\bban\\w*"', "new": 'r"\\bbanned\\b"'},
    {"id": "F05", "title": "Off-by-one term index", "category": "cleaning",
     "description": "term_index starts at 1 instead of 0 (F23 = 1 .. F26 = 7).",
     "file": "src/analysis/clean.py",
     "old": 'df["term"].map(TERMS.index)', "new": 'df["term"].map(lambda t: TERMS.index(t) + 1)'},
    {"id": "F06", "title": "Kappa without chance correction", "category": "evaluation",
     "description": "Cohen's kappa returns raw observed agreement instead of (po - pe) / (1 - pe).",
     "file": "src/evaluation/hand_sample.py",
     "old": "return 1.0 if pe == 1 else (po - pe) / (1 - pe)", "new": "return po"},
    {"id": "F07", "title": "Wrong denominator", "category": "analysis",
     "description": "The intro learning-vs-generation gap divides by all rows instead of intro rows.",
     "file": "src/analysis/descriptives.py",
     "old": "est = (a.sum() - b.sum()) / intro.sum()", "new": "est = (a.sum() - b.sum()) / len(intro)"},
    {"id": "F08", "title": "Flip the rhetoric gap", "category": "analysis",
     "description": "The rhetoric gap is computed as z(policy) - z(stance) instead of z(stance) - z(policy).",
     "file": "src/analysis/rhetoric.py",
     "old": 't["gap"] = t["z_stance"] - t["z_policy"]', "new": 't["gap"] = t["z_policy"] - t["z_stance"]'},
    {"id": "F09", "title": "Site data drops a field", "category": "site", "ui": True,
     "description": "The dashboard export omits census_region from institutions.json. "
                    "The Playwright UI tests are included for this fault.",
     "file": "src/report/build_site_data.py",
     "old": '["inst_id", "name", "state", "census_region", "control", "carnegie", "cs_enrollment"]',
     "new": '["inst_id", "name", "state", "control", "carnegie", "cs_enrollment"]'},
    {"id": "F10", "title": "Home-path redaction is a no-op", "category": "instrumentation",
     "description": "The run-file plugin stops replacing the home directory with ~ before publishing test text.",
     "file": "tests/conftest.py",
     "old": 'return (text or "").replace(HOME, "~")', "new": 'return text or ""'},
]


def _ignore(directory, names):
    skip = {n for n in names if n in SKIP_COPY or n == ".coverage"}
    if Path(directory).name == "coverage" and Path(directory).parent.name == "tests":
        skip |= {n for n in names if n == "latest.json"}
    return skip


def copy_repo(repo: Path, dest: Path) -> Path:
    shutil.copytree(repo, dest, ignore=_ignore, symlinks=True)
    return dest


def apply(repo: Path, fault: dict) -> bytes:
    """Apply a fault in place and return the file's original bytes. The `old` text must occur exactly once."""
    path = Path(repo) / fault["file"]
    original = path.read_bytes()
    text = original.decode("utf-8")
    n = text.count(fault["old"])
    if n != 1:
        raise ValueError(f"{fault['id']}: expected exactly one match of its old text in {fault['file']}, found {n}")
    path.write_text(text.replace(fault["old"], fault["new"]), encoding="utf-8")
    return original


def run_suite(repo: Path, include_ui: bool, python: str = sys.executable, timeout: int = 900) -> dict:
    """Run pytest in `repo` and return {nodeid: status} from the run file the plugin writes."""
    runs = Path(repo) / "results" / "tests"
    before = set(runs.glob("run-*.json")) if runs.exists() else set()
    args = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + [f"--ignore={t}" for t in SELF_TESTS]
    if not include_ui:
        args += [f"--ignore={t}" for t in UI_TESTS]
    # No bytecode cache: a same-size edit within the same second would otherwise reuse the stale .pyc
    # (CPython validates by mtime and size), and the fault would silently not run.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=timeout, env=env)
    new = sorted(set(runs.glob("run-*.json")) - before)
    if not new:
        raise RuntimeError(f"pytest wrote no run file (exit {proc.returncode}):\n{proc.stdout[-2000:]}{proc.stderr[-2000:]}")
    run = json.loads(new[-1].read_text(encoding="utf-8"))
    new[-1].unlink()  # fault runs are scratch; they must not appear in the copy's history
    statuses = {t["nodeid"]: t["status"] for t in run["tests"]}
    for err in run.get("collection_errors", []):
        statuses[err["nodeid"] or "<collection>"] = "error"
    return statuses


def run(repo: Path = ROOT, out: Path = OUT, faults: list[dict] = FAULTS, python: str = sys.executable,
        log=print) -> dict:
    repo, out = Path(repo), Path(out)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="faults-") as tmp:
        copy = copy_repo(repo, Path(tmp) / "repo")
        for f in faults:  # fail fast if any fault no longer applies, before spending minutes on runs
            (copy / f["file"]).write_bytes(apply(copy, f))
        log("baseline (no UI tests)…")
        base = run_suite(copy, include_ui=False, python=python)
        base_ui = None
        if any(f.get("ui") for f in faults):
            log("baseline (with UI tests)…")
            base_ui = run_suite(copy, include_ui=True, python=python)
        for b in (base, base_ui or {}):
            bad = sorted(n for n, s in b.items() if s in ("failed", "error"))
            if bad:
                raise RuntimeError(f"baseline run is not clean; fix these before injecting faults: {bad[:10]}")
        results = []
        for f in faults:
            t0 = time.monotonic()
            original = apply(copy, f)
            try:
                statuses = run_suite(copy, include_ui=bool(f.get("ui")), python=python)
            finally:
                (copy / f["file"]).write_bytes(original)
            baseline = base_ui if f.get("ui") else base
            caught_by = sorted(n for n, s in statuses.items()
                               if s in ("failed", "error") and baseline.get(n) not in ("failed", "error"))
            golden = [n for n in caught_by if GOLDEN.search(n)]
            results.append({**{k: f[k] for k in ("id", "title", "category", "description", "file", "old", "new")},
                            "ui_tests_included": bool(f.get("ui")), "caught": bool(caught_by),
                            "n_caught_by": len(caught_by), "caught_by": caught_by,
                            "caught_by_golden": golden,
                            "caught_by_behavioral": [n for n in caught_by if n not in golden],
                            "golden_only": bool(caught_by) and len(golden) == len(caught_by),
                            "n_tests_run": len(statuses), "duration_s": round(time.monotonic() - t0, 1)})
            log(f"{f['id']} {f['title']}: {'caught by ' + str(len(caught_by)) if caught_by else 'NOT CAUGHT'}")
    n_caught = sum(r["caught"] for r in results)
    report = {
        "synthetic": True, "note": NOTE, "requirement": "VAL-04",
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": _git_head(repo),
        "method": ("Temporary copy of the repo; one fault applied at a time; full pytest suite; a test 'catches' a "
                   "fault if it passed on the unmodified copy and fails or errors with the fault."),
        "ui_policy": ("The network-bound Playwright UI tests (" + ", ".join(UI_TESTS) + ") are excluded from fault "
                      "runs, except for faults marked ui_tests_included. The fault runner's own tests (" + ", ".join(SELF_TESTS) +
                      ") are always excluded."),
        "baseline": {"n_tests": len(base), "n_tests_with_ui": len(base_ui) if base_ui else None},
        "n_faults": len(results), "n_caught": n_caught,
        "detection_rate": round(n_caught / len(results), 4) if results else None,
        "uncaught": [r["id"] for r in results if not r["caught"]],
        "golden_definition": ("A golden-file test (name ends in _is_current / _are_current) re-derives a committed "
                              "output and compares it byte for byte; a behavioural test checks a stated property."),
        "n_caught_behavioral": sum(bool(r["caught_by_behavioral"]) for r in results),
        "behavioral_detection_rate": (round(sum(bool(r["caught_by_behavioral"]) for r in results) / len(results), 4)
                                      if results else None),
        "golden_only": [r["id"] for r in results if r["golden_only"]],
        "duration_s": round(time.monotonic() - started, 1),
        "faults": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def _git_head(repo: Path):
    try:
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=10)
        return p.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def main(argv=None) -> None:
    report = run()
    print(f"detection rate {report['n_caught']}/{report['n_faults']} = {report['detection_rate']:.0%} "
          f"(behavioural tests: {report['n_caught_behavioral']}/{report['n_faults']}; "
          f"golden-file only: {report['golden_only'] or 'none'}); "
          f"uncaught: {report['uncaught'] or 'none'} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
