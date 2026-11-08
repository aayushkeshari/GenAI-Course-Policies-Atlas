"""ANL-06 (chi-square + Cramér's V), ANL-07 (ordinal logistic regression), ANL-14 (institution clustering)."""
import json

import numpy as np
import pytest
from scipy.stats import norm

from src.analysis import inference as INF
from src.analysis.common import CLEAN, RESULTS, _jsonable, read_clean
from src.analysis.stats import cramers_v


@pytest.fixture(scope="module")
def reg():
    return json.loads((RESULTS / "regression.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def assoc():
    return json.loads((RESULTS / "association.json").read_text(encoding="utf-8"))


def coef(reg, term):
    return next(c for c in reg["coefficients"] if c["term"] == term)


# --- ANL-06 ------------------------------------------------------------------------------------------
@pytest.mark.req("ANL-06")
def test_policy_by_level_and_by_se_associations(assoc):
    """association.json has policy x level and policy x is_se: the contingency table, a chi-square p-value
    labelled naive, Cramér's V computed from the table, and its cluster-bootstrap CI (the main inference)."""
    assert [(a["row"], a["col"]) for a in assoc["associations"]] == [("policy", "level"), ("policy", "is_se_label")]
    for a in assoc["associations"]:
        assert a["n"] == assoc["n_used"] == np.array(a["table"]).sum()
        assert "naive" in a["p_value_note"]
        assert a["cramers_v"] == pytest.approx(float(cramers_v(np.array(a["table"]))), abs=1e-6)
        assert a["cramers_v_ci"][0] <= a["cramers_v"] <= a["cramers_v_ci"][1]
        assert a["cramers_v_ci"][0] > 0


@pytest.mark.req("ANL-06")
def test_committed_association_is_current(tmp_path, assoc):
    """results/association.json equals a fresh computation on data/clean/."""
    assert assoc == json.loads(json.dumps(_jsonable({"synthetic": True, "note": assoc["note"], **INF.associations(CLEAN)})))


# --- ANL-07 ------------------------------------------------------------------------------------------
@pytest.mark.req("ANL-07")
def test_regression_reports_coefficients_cis_and_n(reg):
    """regression.json reports every predictor of policy ~ level + is_se + term_index + control + carnegie with
    a coefficient and 95% CI, the reference categories, and n used (+ n excluded = all cleaned rows)."""
    assert [c["term"] for c in reg["coefficients"]] == INF.PREDICTORS
    assert reg["reference_categories"] == {"level": "intro", "control": "public", "carnegie": "R1"}
    assert reg["n_used"] + reg["n_excluded_missing_policy"] == len(read_clean("courses", CLEAN))
    assert reg["converged"]
    z = norm.ppf(0.975)
    for c in reg["coefficients"]:
        lo, hi = c["ci_clustered"]
        assert lo == pytest.approx(c["coef"] - z * c["se_clustered"], abs=1e-4)
        assert hi == pytest.approx(c["coef"] + z * c["se_clustered"], abs=1e-4)
    assert len(reg["thresholds"]) == 4  # five ordered policy levels


@pytest.mark.req("ANL-07")
@pytest.mark.req("ANL-14")
def test_committed_regression_is_current(reg):
    """results/regression.json equals a fresh fit (all fields except the slow bootstrap cross-check, which
    test_bootstrap_cross_check_agrees_with_sandwich covers)."""
    fresh = _jsonable(INF.regression(CLEAN, with_bootstrap=False))
    for c_saved, c_fresh in zip(reg["coefficients"], fresh["coefficients"]):
        assert {k: v for k, v in c_saved.items() if "bootstrap" not in k} == c_fresh
    for k in ["n_used", "n_excluded_missing_policy", "n_clusters", "thresholds", "ratios_to_term_effect", "reference_categories"]:
        assert reg[k] == fresh[k], k


# --- ANL-14 ------------------------------------------------------------------------------------------
@pytest.mark.req("ANL-14")
def test_main_inference_is_clustered_by_institution(reg):
    """The regression's main inference is cluster-robust SEs grouped by inst_id over all 150 institutions;
    naive SEs are reported only alongside."""
    assert reg["inference"]["main"] == "cluster-robust (sandwich) SEs grouped by inst_id"
    assert reg["n_clusters"] == 150
    assert any("naive" in x for x in reg["inference"]["also_reported"])


@pytest.mark.req("ANL-14")
@pytest.mark.kind("property")
def test_clustering_widens_institution_level_predictors(reg):
    """For predictors that are constant within an institution (control, carnegie), clustered SEs are at least
    1.5x the naive SEs: the naive model overstates precision for exactly these comparisons."""
    for t in ["private", "R2", "Masters", "Baccalaureate"]:
        c = coef(reg, t)
        assert c["se_clustered"] > 1.5 * c["se_naive"], t


@pytest.mark.req("ANL-14")
def test_bootstrap_cross_check_agrees_with_sandwich(reg):
    """The cluster-bootstrap SE (500 institution resamples) is within 25% of the sandwich SE for every
    predictor, so the main method is not an artifact of the sandwich estimator."""
    for c in reg["coefficients"]:
        assert abs(c["se_cluster_bootstrap"] / c["se_clustered"] - 1) < 0.25, c["term"]


@pytest.mark.req("ANL-07")
def test_ratio_ci_delta_method():
    """ratio_ci() gives the delta-method SE: for independent a, d with SEs sa, sd the variance is
    sa^2/d^2 + a^2 sd^2/d^4."""
    import pandas as pd

    class R:
        params = pd.Series({"x": 2.0, "term_index": 0.5})

        def cov_params(self):
            return pd.DataFrame([[0.04, 0.0], [0.0, 0.0025]], index=["x", "term_index"], columns=["x", "term_index"])
    r = INF.ratio_ci(R(), "x")
    assert r["estimate"] == pytest.approx(4.0)
    assert r["se"] == pytest.approx(np.sqrt(0.04 / 0.25 + 4 * 0.0025 / 0.0625))
