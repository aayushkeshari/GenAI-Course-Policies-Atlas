"""INST-06/07: Makefile targets."""
import shutil
import subprocess

import pytest

from hookutil import ROOT

TARGETS = ["data", "analysis", "test", "report", "tokens", "timeline", "site", "serve", "clean"]


def make_n(target):
    return subprocess.run(["make", "-n", target], cwd=ROOT, capture_output=True, text=True, timeout=30)


@pytest.mark.req("INST-06")
@pytest.mark.parametrize("target", TARGETS)
def test_target_exists(target):
    """Every target named in INST-06 is defined. `make -n` (dry run) succeeds and doesn't
    report 'No rule to make target'."""
    proc = make_n(target)
    assert proc.returncode == 0, proc.stderr


@pytest.mark.req("INST-06")
def test_clean_never_touches_logs_or_run_history():
    """`make clean` doesn't delete logs/, raw_logs/, or results/: hooks own the logs, and
    VAL-02 keeps every run file."""
    cmds = make_n("clean").stdout
    for protected in ("logs", "raw_logs", "results"):
        assert protected not in cmds


@pytest.mark.req("INST-07")
def test_make_test_runs_pytest():
    """`make test` invokes pytest, so the run-file plugin in tests/conftest.py fires."""
    assert "-m pytest" in make_n("test").stdout
