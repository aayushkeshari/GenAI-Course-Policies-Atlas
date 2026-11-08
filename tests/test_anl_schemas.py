"""ANL-09: every results/*.json file follows its JSON Schema in src/report/schemas/."""
import copy
import json

import pytest
from jsonschema import Draft202012Validator

from src.analysis.common import RESULTS, ROOT

SCHEMAS = ROOT / "src" / "report" / "schemas"
RESULT_FILES = sorted(p.stem for p in RESULTS.glob("*.json"))


def schema(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def result(name):
    return json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.req("ANL-09")
def test_every_results_file_has_a_schema_and_vice_versa():
    """There is exactly one schema per top-level results/*.json file (results/tests/ run files are P0's)."""
    assert RESULT_FILES, "no results files"
    assert sorted(p.name.removesuffix(".schema.json") for p in SCHEMAS.glob("*.schema.json")) == RESULT_FILES


@pytest.mark.req("ANL-09")
@pytest.mark.parametrize("name", RESULT_FILES)
def test_results_file_validates_against_its_schema(name):
    """The schema is a valid Draft 2020-12 schema and the committed results file validates against it."""
    sc = schema(name)
    Draft202012Validator.check_schema(sc)
    errors = sorted(Draft202012Validator(sc).iter_errors(result(name)), key=str)
    assert not errors, [e.message for e in errors[:3]]


@pytest.mark.req("ANL-09")
@pytest.mark.parametrize("name", RESULT_FILES)
def test_schema_rejects_a_file_without_the_synthetic_flag(name):
    """Schemas are not vacuous: dropping the synthetic flag, or adding an unknown top-level key, fails validation."""
    v = Draft202012Validator(schema(name))
    bad = copy.deepcopy(result(name))
    del bad["synthetic"]
    assert list(v.iter_errors(bad))
    bad = copy.deepcopy(result(name))
    bad["unexpected"] = 1
    assert list(v.iter_errors(bad))


@pytest.mark.req("ANL-09")
def test_schema_rejects_malformed_values():
    """Spot checks that value constraints bite: a CI with one bound, a probability above 1, and a regression
    whose main inference is not clustered are all rejected."""
    reg = copy.deepcopy(result("regression"))
    reg["coefficients"][0]["ci_clustered"] = [0.1]
    assert list(Draft202012Validator(schema("regression")).iter_errors(reg))
    reg = copy.deepcopy(result("regression"))
    reg["inference"]["main"] = "naive"
    assert list(Draft202012Validator(schema("regression")).iter_errors(reg))
    ev = copy.deepcopy(result("coder_eval"))
    ev["heldout"]["macro_f1"] = 1.2
    assert list(Draft202012Validator(schema("coder_eval")).iter_errors(ev))
