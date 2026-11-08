"""Read results/tests/run-*.json in either format (VAL-01, VAL-02).

test-run/1 files (before the VAL-01 sidecar change) hold docstring and source inline.
test-run/2 files hold body_sha256; the text is in results/tests/bodies/<sha>.json.
`load_run` returns every test with docstring, source and body_sha256 filled in, whatever the format.
"""
import hashlib
import json
from pathlib import Path

RUNS = Path(__file__).resolve().parents[2] / "results" / "tests"
SCHEMAS = ("test-run/1", "test-run/2")


def canonical_body(docstring: str, source: str) -> bytes:
    """Same bytes as tests/conftest.py canonical_body (a test checks they agree)."""
    text = json.dumps({"docstring": docstring, "source": source}, sort_keys=True, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def run_files(runs_dir: Path = RUNS) -> list[Path]:
    """Every run file, oldest first. The timestamped names sort chronologically."""
    return sorted(Path(runs_dir).glob("run-*.json"))


def read_body(runs_dir: Path, sha: str) -> dict:
    path = Path(runs_dir) / "bodies" / f"{sha}.json"
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError(f"body file {path.name} does not hash to its name")
    return json.loads(raw)


def load_run(path: Path) -> dict:
    path = Path(path)
    run = json.loads(path.read_text(encoding="utf-8"))
    if run.get("schema") not in SCHEMAS:
        raise ValueError(f"{path.name}: unknown schema {run.get('schema')!r}")
    for t in run["tests"]:
        if "body_sha256" in t:
            body = read_body(path.parent, t["body_sha256"])
            t["docstring"], t["source"] = body["docstring"], body["source"]
        else:
            t["body_sha256"] = hashlib.sha256(canonical_body(t["docstring"], t["source"])).hexdigest()
    run["file"] = path.name
    return run


# ---- coverage summaries, one per `make test` run (VAL-03) -------------------------------------------

def coverage_summary(cov: dict) -> dict:
    """Per-module line coverage from a pytest-cov JSON report (format 3), without line lists."""
    modules = [{"module": name, "statements": f["summary"]["num_statements"],
                "missing": f["summary"]["missing_lines"],
                "percent": round(f["summary"]["percent_covered"], 2)}
               for name, f in sorted(cov["files"].items())]
    t = cov["totals"]
    return {"coverage_timestamp": cov["meta"]["timestamp"], "coverage_version": cov["meta"]["version"],
            "modules": modules,
            "totals": {"statements": t["num_statements"], "missing": t["missing_lines"],
                       "percent": round(t["percent_covered"], 2)}}


def attach_coverage(coverage_json: Path, runs_dir: Path = RUNS) -> Path:
    """Archive the coverage summary of the newest run as results/tests/coverage/<run file name>.

    The report must have been written during that run (between its start and 2 minutes after its end),
    otherwise it belongs to another run and nothing is written (ValueError).
    """
    from datetime import datetime, timedelta
    newest = run_files(runs_dir)[-1]
    run = json.loads(newest.read_text(encoding="utf-8"))
    summary = coverage_summary(json.loads(Path(coverage_json).read_text(encoding="utf-8")))
    started = datetime.fromisoformat(run["started"]).replace(tzinfo=None)
    finished = datetime.fromisoformat(run["finished"]).replace(tzinfo=None)
    stamp = datetime.fromisoformat(summary["coverage_timestamp"])
    if not started <= stamp <= finished + timedelta(minutes=2):
        raise ValueError(f"coverage report ({stamp}) was not written during {newest.name}")
    out = Path(runs_dir) / "coverage" / newest.name
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"run": newest.name, **summary}, indent=1) + "\n", encoding="utf-8")
    return out


def main(argv=None) -> None:
    import sys
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] != ["attach-coverage"]:
        raise SystemExit("usage: python -m src.validation.runs attach-coverage [results/tests/coverage/latest.json]")
    cov = Path(argv[1]) if len(argv) > 1 else RUNS / "coverage" / "latest.json"
    print(attach_coverage(cov).relative_to(RUNS.parents[1]))


if __name__ == "__main__":
    main()
