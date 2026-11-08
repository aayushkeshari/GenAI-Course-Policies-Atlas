"""P1 schema tests (DATA-13): types, allowed values, row counts within +-10%, referential integrity.

They run on the committed data/raw/ (what P2 reads) and on a freshly generated other seed, so the schema
holds for the generator in general, not just for one file.
"""
import re
from datetime import date

import pytest

from datautil import RAW, gen_module, generated_dir, load_dir

DATASETS = {"committed": RAW, "seed7": None}


@pytest.fixture(params=sorted(DATASETS), scope="module")
def data(request):
    return load_dir(DATASETS[request.param] or generated_dir(7))


def within(n, target):
    return 0.9 * target <= n <= 1.1 * target


@pytest.mark.req("DATA-13")
def test_row_counts_within_ten_percent(data):
    """institutions ~150, statements ~350, courses ~2,000, each within +-10%."""
    assert within(len(data["institutions"]), 150)
    assert within(len(data["statements"]), 350)
    assert within(len(data["courses"]), 2000)


@pytest.mark.req("DATA-13")
def test_institution_types_and_values(data):
    """inst_id is I### and unique; state is a US postal code whose census_region matches; control,
    carnegie are from their allowed sets; cs_enrollment is a positive integer."""
    regions = dict(gen_module().STATES)
    ids = [r["inst_id"] for r in data["institutions"]]
    assert len(set(ids)) == len(ids)
    for r in data["institutions"]:
        assert re.fullmatch(r"I\d{3}", r["inst_id"])
        assert r["name"].strip() == r["name"] != ""
        assert regions[r["state"]] == r["census_region"]
        assert r["control"] in {"public", "private"}
        assert r["carnegie"] in {"R1", "R2", "Masters", "Baccalaureate"}
        assert re.fullmatch(r"[1-9]\d*", r["cs_enrollment"])


@pytest.mark.req("DATA-13")
def test_statement_types_and_values(data):
    """stmt_id is S#### and unique; pub_type is allowed; pub_date is a valid YYYY-MM month from 2023-01 to
    2026-10; text is non-empty."""
    ids = [r["stmt_id"] for r in data["statements"]]
    assert len(set(ids)) == len(ids)
    for r in data["statements"]:
        assert re.fullmatch(r"S\d{4}", r["stmt_id"])
        assert r["pub_type"] in {"policy_page", "news", "strategic_plan", "syllabus_template", "faq"}
        y, m = map(int, r["pub_date"].split("-"))
        assert date(2023, 1, 1) <= date(y, m, 1) <= date(2026, 10, 1)
        assert r["text"].strip()


@pytest.mark.req("DATA-13")
def test_course_types_and_values(data):
    """course_id is C####, code is 'CS ###'; level lowercases to an allowed level; is_se is true/false;
    term is one of the 7 terms; policy is blank or 0-4; disclosure_required is blank/true/false;
    assessment_adaptation, tools_named and allowed_uses use only their fixed vocabularies; a blank policy
    comes with blank derived fields."""
    tools = {"chat assistant", "IDE autocomplete", "agentic coding tool"}
    uses = {"explanation", "debugging", "code_generation", "testing", "writing"}
    for r in data["courses"]:
        assert re.fullmatch(r"C\d{4}", r["course_id"])
        assert re.fullmatch(r"CS \d{3}", r["code"])
        assert r["level"].lower() in {"intro", "intermediate", "upper", "graduate"}
        assert r["is_se"] in {"true", "false"}
        assert r["term"] in {"F23", "S24", "F24", "S25", "F25", "S26", "F26"}
        assert r["policy"] in {"", "0", "1", "2", "3", "4"}
        assert r["disclosure_required"] in {"", "true", "false"}
        assert r["assessment_adaptation"] in {"none", "in_class_exams", "oral_defense", "process_logs", "ai_critique"}
        assert set(filter(None, r["tools_named"].split(";"))) <= tools
        assert set(filter(None, r["allowed_uses"].split(";"))) <= uses
        if r["policy"] == "":
            assert r["disclosure_required"] == r["tools_named"] == r["allowed_uses"] == ""


@pytest.mark.req("DATA-13")
def test_referential_integrity(data):
    """Every statement and course inst_id exists in institutions; every course_id belongs to one
    institution; ground_truth.json keys refer to existing institutions, statements, and course rows."""
    inst = {r["inst_id"] for r in data["institutions"]}
    assert {r["inst_id"] for r in data["statements"]} <= inst
    assert {r["inst_id"] for r in data["courses"]} <= inst
    owner = {}
    for r in data["courses"]:
        assert owner.setdefault(r["course_id"], r["inst_id"]) == r["inst_id"]
    gt = data["ground_truth"]
    assert set(gt["institutions"]) == inst
    assert set(gt["statements"]) == {r["stmt_id"] for r in data["statements"]}
    assert set(gt["courses"]) == set(owner)
    assert {(r["course_id"], r["term"]) for r in gt["course_rows"]} == {(r["course_id"], r["term"]) for r in data["courses"]}


@pytest.mark.req("DATA-13")
@pytest.mark.req("DATA-01")
def test_committed_data_matches_generator(tmp_path):
    """data/raw/ is exactly what `make data` (seed 2026) produces now, so the committed data is never stale."""
    gen_module().generate(2026, tmp_path)
    for f in ["institutions.csv", "statements.csv", "courses.csv", "ground_truth.json"]:
        assert (RAW / f).read_bytes() == (tmp_path / f).read_bytes(), f"{f} is stale: run `make data`"
