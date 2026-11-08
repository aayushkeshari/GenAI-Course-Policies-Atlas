"""Synthetic data generator for P1 (specs/P1-data.md, DATA-01..DATA-17).

Usage:  python src/data/generate.py --seed 2026 [--out data/raw]

ALL DATA PRODUCED HERE IS SYNTHETIC. Institution names are fictional, built from word lists.

Determinism (DATA-01): standard library only, one random.Random(seed) consumed in a fixed order,
CSV rows written in a fixed order with "\n" line endings, JSON written with sorted keys and
rounded floats, and nothing time-dependent in any output.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL_UNIVERSITIES = ROOT / "data" / "reference" / "real_universities.txt"
DEFAULT_OUT = ROOT / "data" / "raw"
GENERATOR_VERSION = 1

# ---------------------------------------------------------------------------------------------
# Institutions (DATA-02)
# ---------------------------------------------------------------------------------------------
N_INST = 150
P_PUBLIC = 0.55
CARNEGIE = ["R1", "R2", "Masters", "Baccalaureate"]
CARNEGIE_WEIGHTS = [0.25, 0.25, 0.30, 0.20]
ENROLL_MEDIAN = {"R1": 1800, "R2": 800, "Masters": 350, "Baccalaureate": 110}
ENROLL_LOG_SD = 0.35

# Town names are prefix + suffix ("Cedarbrook", "Heronvale"). Combinations known to be real
# college names were avoided when choosing the lists; the generator also rejects any name that
# appears in data/reference/real_universities.txt.
TOWN_PREFIX = ["Alder", "Amber", "Briar", "Cedar", "Copper", "Falcon", "Fern", "Glen", "Hazel",
               "Heron", "Iron", "Juniper", "Larch", "Laurel", "Maple", "Marsh", "Pine", "Quarry",
               "Raven", "Silver", "Thorn", "Willow", "Wren", "Bramble"]
TOWN_SUFFIX = ["brook", "crest", "dale", "field", "ford", "gate", "haven", "holm", "moor", "ridge",
               "vale", "wick", "mere", "stead", "shire"]
NAME_PATTERNS = {
    "public": ["University of {t}", "{t} State University", "{t} University"],
    "private": ["{t} University", "{t} College", "{t} Institute of Technology"],
    "Baccalaureate": ["{t} College"],
}

STATES = [  # (postal code, census region)
    ("CT", "Northeast"), ("ME", "Northeast"), ("MA", "Northeast"), ("NH", "Northeast"),
    ("RI", "Northeast"), ("VT", "Northeast"), ("NJ", "Northeast"), ("NY", "Northeast"),
    ("PA", "Northeast"),
    ("IL", "Midwest"), ("IN", "Midwest"), ("MI", "Midwest"), ("OH", "Midwest"), ("WI", "Midwest"),
    ("IA", "Midwest"), ("KS", "Midwest"), ("MN", "Midwest"), ("MO", "Midwest"), ("NE", "Midwest"),
    ("ND", "Midwest"), ("SD", "Midwest"),
    ("DE", "South"), ("FL", "South"), ("GA", "South"), ("MD", "South"), ("NC", "South"),
    ("SC", "South"), ("VA", "South"), ("WV", "South"), ("AL", "South"), ("KY", "South"),
    ("MS", "South"), ("TN", "South"), ("AR", "South"), ("LA", "South"), ("OK", "South"),
    ("TX", "South"),
    ("AZ", "West"), ("CO", "West"), ("ID", "West"), ("MT", "West"), ("NV", "West"), ("NM", "West"),
    ("UT", "West"), ("WY", "West"), ("AK", "West"), ("CA", "West"), ("HI", "West"), ("OR", "West"),
    ("WA", "West"),
]

INSTITUTION_COLUMNS = ["inst_id", "name", "state", "census_region", "control", "carnegie",
                       "cs_enrollment"]


def load_real_names(path: Path = REAL_UNIVERSITIES) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]


def make_institutions(rng: random.Random, real_names: list[str]) -> list[dict]:
    """Institution rows. Names are rejected if they match a real name (case-insensitive) or repeat."""
    real = {n.casefold() for n in real_names}
    used: set[str] = set()
    rows = []
    for i in range(1, N_INST + 1):
        control = "public" if rng.random() < P_PUBLIC else "private"
        carnegie = rng.choices(CARNEGIE, weights=CARNEGIE_WEIGHTS)[0]
        state, region = rng.choice(STATES)
        patterns = NAME_PATTERNS["Baccalaureate" if carnegie == "Baccalaureate" else control]
        while True:
            town = rng.choice(TOWN_PREFIX) + rng.choice(TOWN_SUFFIX)
            name = rng.choice(patterns).format(t=town)
            if name.casefold() not in real and name.casefold() not in used:
                break
        used.add(name.casefold())
        enrollment = round(ENROLL_MEDIAN[carnegie] * math.exp(rng.gauss(0, ENROLL_LOG_SD)))
        rows.append({"inst_id": f"I{i:03d}", "name": name, "state": state, "census_region": region,
                     "control": control, "carnegie": carnegie, "cs_enrollment": enrollment})
    return rows


# ---------------------------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------------------------
def _round_floats(obj, ndigits=4):
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: _cell(r[c]) for c in columns})


def _cell(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    return v


def write_json(path: Path, obj) -> None:
    text = json.dumps(_round_floats(obj), sort_keys=True, indent=1, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def build(seed: int) -> dict:
    """Generate every table in memory. Returns {"institutions": [...], ..., "ground_truth": {...}}."""
    rng = random.Random(seed)
    institutions = make_institutions(rng, load_real_names())
    ground_truth = {
        "synthetic": True,
        "note": "SYNTHETIC DATA. Hidden labels and planted effects. Analysis code must never read this file.",
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
    }
    return {"institutions": institutions, "ground_truth": ground_truth}


def generate(seed: int, out: Path = DEFAULT_OUT) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tables = build(seed)
    write_csv(out / "institutions.csv", INSTITUTION_COLUMNS, tables["institutions"])
    write_json(out / "ground_truth.json", tables["ground_truth"])
    return tables


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Generate the SYNTHETIC P1 dataset.")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    generate(args.seed, args.out)
    print(f"wrote synthetic data (seed {args.seed}) to {args.out}")


if __name__ == "__main__":
    main()
