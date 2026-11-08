"""DASH-01: build site/data/ for the dashboard (run by `make report`).

1. Validates each dashboard results file against its schema in src/report/schemas/ and copies it byte for byte.
2. Exports trimmed raw rows (institutions, course-terms, statements with the coder's labels) for the statement
   explorer (DASH-04) and the institution drilldown (DASH-08).

Reads only results/ and data/clean/. Never reads data/raw/ or the hidden truth, and never imports src.evaluation.
Truth-derived results (recovery, rhetoric_recovery, coder_dev_eval) are not copied: the dashboard only shows
the coder-accuracy aggregates (coder_eval, kappa) that DASH-03 asks for.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import jsonschema
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
CLEAN = ROOT / "data" / "clean"
SCHEMAS = Path(__file__).resolve().parent / "schemas"
SITE_DATA = ROOT / "site" / "data"

# results files the dashboard reads
DASHBOARD_RESULTS = ["descriptives", "allowed_uses", "assessment", "association", "regression",
                     "rhetoric", "coder_eval", "kappa"]
ROWS_NOTE = ("SYNTHETIC DATA: raw synthetic rows, not results. Every institution, course and statement is invented. "
             "Labels are the rule-based coder's output, not the truth.")

INSTITUTION_FIELDS = ["inst_id", "name", "state", "census_region", "control", "carnegie", "cs_enrollment"]
COURSE_FIELDS = ["course_id", "inst_id", "code", "title", "level", "is_se", "term", "term_index", "policy",
                 "disclosure_required", "assessment_adaptation", "tools_named", "allowed_uses"]
THEMES = ["mentions_integrity", "mentions_collaboration", "mentions_careers"]


def _csv(clean_dir: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(Path(clean_dir) / f"{name}.csv", dtype=str, keep_default_na=False)


def _split(value: str) -> list[str]:
    return [x for x in value.split(";") if x]


def institutions(clean_dir: Path) -> list[dict]:
    df = _csv(clean_dir, "institutions")[INSTITUTION_FIELDS]
    return [{**r, "cs_enrollment": int(r["cs_enrollment"])} for r in df.to_dict("records")]


def courses(clean_dir: Path) -> list[dict]:
    rows = []
    for r in _csv(clean_dir, "courses")[COURSE_FIELDS].to_dict("records"):
        rows.append({**r, "is_se": r["is_se"] == "true", "term_index": int(r["term_index"]),
                     "policy": int(r["policy"]) if r["policy"] != "" else None,
                     "disclosure_required": {"true": True, "false": False}.get(r["disclosure_required"]),
                     "tools_named": _split(r["tools_named"]), "allowed_uses": _split(r["allowed_uses"])})
    return rows


def statements(clean_dir: Path) -> list[dict]:
    s = _csv(clean_dir, "statements")[["stmt_id", "inst_id", "pub_type", "pub_date", "text"]]
    coded = _csv(clean_dir, "statements_coded")
    df = s.merge(coded.drop(columns="inst_id"), on="stmt_id", how="left", validate="one_to_one")
    rows = []
    for r in df.to_dict("records"):
        row = {k: r[k] for k in ["stmt_id", "inst_id", "pub_type", "pub_date", "text"]}
        row["year"] = r["pub_date"][:4]
        row["coded_stance"] = int(r["stance"])
        row["coded_stance_rule"] = r["stance_rule"]
        for t in THEMES:
            row[f"coded_{t}"] = r[t] == "true"
            row[f"coded_{t}_rules"] = _split(r[f"{t}_rules"])
        rows.append(row)
    return rows


def _write_rows(path: Path, key: str, rows: list[dict], fields_note: str) -> None:
    body = {"synthetic": True, "note": ROWS_NOTE, "source": fields_note, "n": len(rows), key: rows}
    path.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")


def build(results: Path = RESULTS, clean_dir: Path = CLEAN, out: Path = SITE_DATA) -> list[str]:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name in DASHBOARD_RESULTS:
        src = Path(results) / f"{name}.json"
        schema = json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(json.loads(src.read_text(encoding="utf-8")), schema)
        shutil.copyfile(src, out / src.name)
        written.append(src.name)
    _write_rows(out / "institutions.json", "institutions", institutions(clean_dir), "data/clean/institutions.csv")
    _write_rows(out / "courses.json", "courses", courses(clean_dir), "data/clean/courses.csv")
    _write_rows(out / "statements.json", "statements", statements(clean_dir),
                "data/clean/statements.csv + data/clean/statements_coded.csv (rule-based coder)")
    written += ["institutions.json", "courses.json", "statements.json"]
    return written


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else SITE_DATA
    for name in build(out=out):
        print(f"site/data/{name}")


if __name__ == "__main__":
    main()
