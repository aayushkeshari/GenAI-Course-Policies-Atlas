"""DASH-01 site data: site/data/ is a faithful, current, truth-free copy built by `make report`."""
import ast
import json
from pathlib import Path

import pandas as pd
import pytest

from src.report import build_site_data as B

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "data"
ROW_FILES = ["institutions.json", "courses.json", "statements.json"]

# Every per-entity field in data/raw/ground_truth.json, plus its top-level sections: banned in every site file.
TRUTH_KEYS = {"course_effect", "inst_effect", "rhetoric_gap", "stance_latent", "latent_score", "hard_cases",
              "reserved_phrasings", "split", "planted_effects", "parameters", "course_rows", "mess",
              "generator_version"}
# The truth stores hidden labels under the bare names stance / mentions_*. Row files carry only the coder's labels,
# prefixed coded_. (In kappa.json and coder_eval.json these bare names are keys of aggregate scores, not labels.)
TRUTH_LABEL_KEYS = {"stance", "mentions_integrity", "mentions_collaboration", "mentions_careers"}


def all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_keys(v)


@pytest.mark.req("DASH-01")
def test_site_data_is_current(tmp_path):
    """site/data/ equals a fresh `make report` build byte for byte, so the committed site never shows stale numbers."""
    written = B.build(out=tmp_path)
    assert sorted(p.name for p in SITE_DATA.glob("*.json")) == sorted(written)
    for name in written:
        assert (SITE_DATA / name).read_bytes() == (tmp_path / name).read_bytes(), name


@pytest.mark.req("DASH-01")
def test_results_are_copied_unchanged_and_schema_valid():
    """Every dashboard results file in site/data/ is an exact copy of results/<name>.json, and the build validates
    each against its schema before copying (a schema-invalid file stops the build)."""
    for name in B.DASHBOARD_RESULTS:
        assert (SITE_DATA / f"{name}.json").read_bytes() == (ROOT / "results" / f"{name}.json").read_bytes()
        assert (B.SCHEMAS / f"{name}.schema.json").exists()


@pytest.mark.req("DASH-01")
def test_schema_invalid_results_stop_the_build(tmp_path):
    """If a results file breaks its schema (here: synthetic flag removed), build() raises instead of copying it."""
    import jsonschema
    res = tmp_path / "results"
    res.mkdir()
    for name in B.DASHBOARD_RESULTS:
        (res / f"{name}.json").write_bytes((ROOT / "results" / f"{name}.json").read_bytes())
    bad = json.loads((res / "kappa.json").read_text())
    del bad["synthetic"]
    (res / "kappa.json").write_text(json.dumps(bad))
    with pytest.raises(jsonschema.ValidationError):
        B.build(results=res, out=tmp_path / "out")


@pytest.mark.req("DASH-01")
def test_no_ground_truth_reaches_the_site():
    """No file in site/data/ contains a ground-truth field name (latent scores, planted parameters, split flags),
    no row file carries a hidden label under the truth's bare names, the truth-derived recovery files are not copied, and the build module never
    reads data/raw/ or imports src.evaluation."""
    for p in SITE_DATA.glob("*.json"):
        banned = TRUTH_KEYS | (TRUTH_LABEL_KEYS if p.name in ROW_FILES else set())
        leaked = set(all_keys(json.loads(p.read_text(encoding="utf-8")))) & banned
        assert not leaked, f"{p.name}: {leaked}"
    for name in ["recovery.json", "rhetoric_recovery.json", "coder_dev_eval.json", "ground_truth.json"]:
        assert not (SITE_DATA / name).exists()
    src = Path(B.__file__).read_text(encoding="utf-8")
    assert "ground_truth" not in src.replace("Never reads data/raw/ or the hidden truth", "")
    assert "data\" / \"raw" not in src and "data/raw\"" not in src
    imports = [n for n in ast.walk(ast.parse(src)) if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = [a.name for n in imports for a in n.names] + [n.module or "" for n in imports if isinstance(n, ast.ImportFrom)]
    assert not any(x.startswith("src.evaluation") for x in names)


@pytest.mark.req("DASH-01")
def test_statement_labels_are_the_coders_not_the_truth():
    """Each exported statement's coded_* labels equal data/clean/statements_coded.csv, and its text and metadata
    equal data/clean/statements.csv."""
    rows = {r["stmt_id"]: r for r in json.loads((SITE_DATA / "statements.json").read_text())["statements"]}
    coded = pd.read_csv(ROOT / "data/clean/statements_coded.csv", dtype=str, keep_default_na=False)
    raw = pd.read_csv(ROOT / "data/clean/statements.csv", dtype=str, keep_default_na=False)
    assert set(rows) == set(coded["stmt_id"]) == set(raw["stmt_id"])
    for c in coded.to_dict("records"):
        r = rows[c["stmt_id"]]
        assert r["coded_stance"] == int(c["stance"]) and r["coded_stance_rule"] == c["stance_rule"]
        for t in B.THEMES:
            assert r[f"coded_{t}"] == (c[t] == "true")
    for s in raw.to_dict("records"):
        assert {k: rows[s["stmt_id"]][k] for k in s} == s


@pytest.mark.req("DASH-01")
@pytest.mark.req("DASH-02")
def test_row_files_are_labelled_synthetic_raw_rows():
    """Each exported row file says it is synthetic, says it is raw rows rather than results, and its n matches."""
    for name in ROW_FILES:
        d = json.loads((SITE_DATA / name).read_text())
        assert d["synthetic"] is True and "SYNTHETIC" in d["note"] and "raw synthetic rows" in d["note"]
        key = name.removesuffix(".json")
        assert d["n"] == len(d[key]) > 0


@pytest.mark.req("DASH-01")
def test_course_rows_match_clean_data():
    """courses.json has one row per cleaned course-term; a missing policy stays null (not imputed)."""
    rows = json.loads((SITE_DATA / "courses.json").read_text())["courses"]
    clean = pd.read_csv(ROOT / "data/clean/courses.csv", dtype=str, keep_default_na=False)
    assert len(rows) == len(clean)
    assert sum(r["policy"] is None for r in rows) == (clean["policy"] == "").sum() > 0
