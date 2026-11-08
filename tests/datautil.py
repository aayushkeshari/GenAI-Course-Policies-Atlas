"""Shared helpers for the P1 data tests: load the generator, generate into temp dirs, read tables."""
import csv
import functools
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "src" / "data" / "generate.py"
RAW = ROOT / "data" / "raw"
FILES = ["institutions.csv", "statements.csv", "courses.csv", "ground_truth.json"]


@functools.lru_cache(maxsize=None)
def gen_module():
    spec = importlib.util.spec_from_file_location("generate", GENERATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@functools.lru_cache(maxsize=None)
def generated_dir(seed: int) -> Path:
    """Generate the dataset for `seed` once per test session into a fresh temp dir."""
    out = Path(tempfile.mkdtemp(prefix=f"p1-seed{seed}-"))
    gen_module().generate(seed, out)
    return out


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load(seed: int) -> dict:
    return load_dir(generated_dir(seed))


def load_dir(d: Path) -> dict:
    tables = {p.stem: read_csv(p) for p in sorted(d.glob("*.csv"))}
    tables["ground_truth"] = json.loads((d / "ground_truth.json").read_text(encoding="utf-8"))
    return tables
