"""ANL-08 recovery tests: the analysis recovers the planted effects (DATA-06..09), does not flag the planted
null (DATA-10), and recovers magnitudes. These tests may read the truth; analysis code may not."""
import json

import pytest

from datautil import RAW, load_dir
from src.analysis.common import RESULTS, _jsonable
from src.evaluation import recovery as REC


@pytest.fixture(scope="module")
def rec():
    return json.loads((RESULTS / "recovery.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def res():
    return {n: json.loads((RESULTS / f"{n}.json").read_text(encoding="utf-8")) for n in ["descriptives", "regression"]}


def coef(res, term):
    return next(c for c in res["regression"]["coefficients"] if c["term"] == term)


def mean_policy(res, by, group):
    return next(r["estimate"] for r in res["descriptives"]["policy"]
                if r["by"] == by and r["group"] == group and r["category"] == "mean")


@pytest.mark.req("ANL-08")
@pytest.mark.kind("recovery")
def test_data06_intro_more_restrictive_than_upper(res):
    """Intro mean policy is below upper-level, and the clustered CI of the upper-vs-intro coefficient is above 0."""
    assert mean_policy(res, "level", "intro") < mean_policy(res, "level", "upper")
    assert coef(res, "upper")["ci_clustered"][0] > 0


@pytest.mark.req("ANL-08")
@pytest.mark.kind("recovery")
def test_data07_se_more_permissive_at_same_level(res):
    """With level in the model, the is_se coefficient's clustered CI is above 0."""
    assert coef(res, "is_se")["ci_clustered"][0] > 0


@pytest.mark.req("ANL-08")
@pytest.mark.kind("recovery")
def test_data08_permissiveness_rises_each_term(res):
    """Mean policy rises from every term to the next, and the term_index clustered CI is above 0."""
    means = [mean_policy(res, "term", t) for t in res["descriptives"]["courses"]["term_order"]]
    assert all(a < b for a, b in zip(means, means[1:])), means
    assert coef(res, "term_index")["ci_clustered"][0] > 0


@pytest.mark.req("ANL-08")
@pytest.mark.kind("recovery")
def test_data09_r1_more_positive_coded_stance(res):
    """Mean coded statement stance is higher at R1 than at every other Carnegie class."""
    st = {r["group"]: r["estimate"] for r in res["descriptives"]["statement_codes"]
          if r["by"] == "carnegie" and r["category"] == "mean"}
    assert all(st["R1"] > v for k, v in st.items() if k != "R1"), st


@pytest.mark.req("ANL-08")
@pytest.mark.req("ANL-14")
@pytest.mark.kind("recovery")
def test_data10_null_not_significant_under_clustering(res):
    """The planted null: the private coefficient is not significant at alpha = 0.05 with clustered SEs."""
    assert coef(res, "private")["p_clustered"] >= 0.05


@pytest.mark.req("ANL-08")
@pytest.mark.kind("recovery")
def test_effect_ratios_within_25_percent_of_planted(rec):
    """Sanity check (HUMAN: +-25%): each coefficient / term coefficient is within 25% of the planted ratio
    (planted effect / planted per-term step, read from ground_truth.json); for the null (planted 0) the CI
    covers 0. Planted ratios are recomputed here from the truth."""
    params = load_dir(RAW)["ground_truth"]["parameters"]["policy_model"]
    step = params["term_effect_per_step"]
    lev = params["level_effect"]
    planted = {"intermediate": (lev["intermediate"] - lev["intro"]) / step, "upper": (lev["upper"] - lev["intro"]) / step,
               "graduate": (lev["graduate"] - lev["intro"]) / step, "is_se": params["se_effect"] / step, "private": 0.0}
    for m in rec["magnitude"]["ratios"]:
        name = m["ratio"].split(" /")[0]
        assert m["planted"] == pytest.approx(planted[name])
        if planted[name] == 0:
            assert m["ci"][0] <= 0 <= m["ci"][1]
        else:
            assert abs(m["estimate"] / planted[name] - 1) <= 0.25, (name, m["estimate"], planted[name])


@pytest.mark.req("ANL-08")
@pytest.mark.req("ANL-14")
@pytest.mark.kind("recovery")
def test_clustered_ci_covers_planted_value_on_at_least_4_of_5_seeds(rec):
    """HUMAN: across seeds 2026, 1, 2, 3, 4 (each regenerated, cleaned and refit), the clustered 95% CI of every
    ratio, including the null, contains the planted value in at least 4 of 5 seeds."""
    cov = rec["coverage"]
    assert cov["seeds"] == [2026, 1, 2, 3, 4] and len(cov["per_seed"]) == 5
    for name, n in cov["covered_counts"].items():
        assert n == sum(s["covered"][name] for s in cov["per_seed"])
        assert n >= 4, (name, n)


@pytest.mark.req("ANL-08")
def test_committed_recovery_is_current(rec):
    """results/recovery.json equals a fresh recovery run (which regenerates and refits all 5 seeds)."""
    fresh = _jsonable(REC.recovery())
    assert {k: rec[k] for k in fresh} == fresh
