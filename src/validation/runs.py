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
