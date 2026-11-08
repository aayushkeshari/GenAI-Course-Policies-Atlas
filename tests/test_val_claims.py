"""VAL-06: every finding on the dashboard links to the tests that support it."""
import json
import re

import pytest

from hookutil import ROOT
from src.report import build_validation_data as V

CLAIMS = json.loads((ROOT / "src" / "report" / "claims.json").read_text())["claims"]
SITE_CLAIMS = json.loads((ROOT / "site" / "validation" / "data" / "claims.json").read_text())
TESTS = {t["nodeid"]: t for t in json.loads((ROOT / "site" / "validation" / "data" / "tests.json").read_text())["tests"]}
APP = (ROOT / "site" / "dashboard" / "app.js").read_text()


@pytest.mark.req("VAL-06")
def test_every_dashboard_finding_has_exactly_one_claim():
    """The claims are exactly the dashboard's 11 chart panels plus its 6 headline tiles: every panel(...) id and every
    tile claim id in site/dashboard/app.js has one claim, and no claim points at something the dashboard doesn't show."""
    panels = re.findall(r'panel\(box, \{\s*id: "([\w-]+)"', APP)
    tiles = re.findall(r'`, "(kpi-[\w-]+)"\]', APP) + re.findall(r'", "(kpi-[\w-]+)"\]', APP)
    assert len(panels) == 11 and len(set(tiles)) == 6
    ids = [c["id"] for c in CLAIMS]
    assert len(ids) == len(set(ids))
    assert sorted(ids) == sorted(panels + list(set(tiles)))
    for c in CLAIMS:
        assert (c["panel"] == f"panel-{c['id']}") if c["kind"] == "panel" else (c["panel"] == "kpis")


@pytest.mark.req("VAL-06")
def test_every_claim_has_computation_tests_that_exist():
    """Each claim lists at least two tests that check the computation itself (not just the dashboard's display), and
    every listed test exists in the explorer's snapshot run."""
    for c in CLAIMS:
        assert set(c["tests"]) <= set(TESTS), (c["id"], set(c["tests"]) - set(TESTS))
        compute = [n for n in c["tests"] if not n.startswith(("tests/test_dash_ui.py", "tests/test_dash_data.py"))]
        assert len(compute) >= 2, c["id"]


@pytest.mark.req("VAL-06")
def test_published_claim_status_is_the_rollup_of_its_tests():
    """site/validation/data/claims.json carries each claim's tests with their snapshot status, and the claim's status is
    their rollup (failing if any test failed or is missing)."""
    assert [c["id"] for c in SITE_CLAIMS["claims"]] == [c["id"] for c in CLAIMS]
    for c in SITE_CLAIMS["claims"]:
        assert c["test_status"] == {n: TESTS[n]["status"] for n in c["tests"]}
        assert c["status"] == V.rollup(list(c["test_status"].values()))


@pytest.mark.req("VAL-06")
def test_claims_with_conditional_wording_match_the_data():
    """Two dashboard takeaways change wording with the data. The claim text must say what the dashboard says:
    'barely predicts' only while |r| < 0.2, and 'does not matter' only while private's clustered p >= 0.05."""
    by_id = {c["id"]: c for c in CLAIMS}
    r = json.loads((ROOT / "results" / "rhetoric.json").read_text())["correlation"]["pearson_r"]
    assert ("barely predicts" in by_id["rhetoric"]["claim"]) == (abs(r) < 0.2)
    coefs = json.loads((ROOT / "results" / "regression.json").read_text())["coefficients"]
    p = next(c for c in coefs if c["term"] == "private")["p_clustered"]
    assert ("does not matter" in by_id["coef"]["claim"]) == (p >= 0.05)


@pytest.mark.req("VAL-06")
def test_dashboard_links_every_finding_to_its_claim():
    """The dashboard's panel footer and each headline tile render an Evidence link to the explorer's Claims view for
    that finding (checked in the source; test_val_ui clicks one)."""
    assert 'href="../validation/#view=claims&amp;claim=${claimId}"' in APP
    assert "${evidence(id)}" in APP and "${evidence(claim)}" in APP
