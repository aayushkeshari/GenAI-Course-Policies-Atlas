"""ANL-05 / ANL-11 / ANL-12 descriptives and the cluster bootstrap they use (ANL-14)."""
import json

import numpy as np
import pandas as pd
import pytest

from src.analysis import descriptives as D
from src.analysis.common import CLEAN, RESULTS, TERMS
from src.analysis.stats import N_BOOT, SEED, ClusterBootstrap, cramers_v


@pytest.fixture(scope="module")
def results():
    return {n: json.loads((RESULTS / f"{n}.json").read_text(encoding="utf-8"))
            for n in ["descriptives", "allowed_uses", "assessment"]}


def known_courses():
    c = D.load_courses(CLEAN)
    k = c[c["policy"].notna()].reset_index(drop=True)
    k["policy"] = k["policy"].astype(int)
    return k


# --- cluster bootstrap unit tests (ANL-05, ANL-14) -------------------------------------------------------
@pytest.mark.req("ANL-05")
@pytest.mark.req("ANL-14")
def test_cluster_bootstrap_resamples_whole_institutions_deterministically():
    """Each of the 2,000 resamples draws exactly K institutions (weights sum to K), the same seed gives the
    same weights, and every row of an institution shares that institution's weight."""
    ids = pd.Series(["I3", "I1", "I1", "I2", "I3", "I3"])
    a, b = ClusterBootstrap(ids), ClusterBootstrap(ids)
    assert a.weights.shape == (N_BOOT, 3)
    assert (a.weights.sum(axis=1) == 3).all()
    assert np.array_equal(a.weights, b.weights)
    assert list(a.clusters) == ["I1", "I2", "I3"]
    assert list(a.sums(np.ones(6))) == [2, 1, 3]


@pytest.mark.req("ANL-14")
def test_identical_institutions_give_zero_width_interval():
    """If every institution has the same share, resampling institutions cannot change it: the CI collapses."""
    ids = pd.Series([f"I{i}" for i in range(10) for _ in range(4)])
    num = np.tile([1, 1, 0, 0], 10)
    boot = ClusterBootstrap(ids).ratio(num, np.ones(40))
    assert np.allclose(boot, 0.5)


@pytest.mark.req("ANL-14")
@pytest.mark.kind("property")
def test_clustered_intervals_are_wider_than_row_level_intervals():
    """For the overall mean policy and for the private-minus-public gap (the planted null), cluster-bootstrap
    CIs are at least 1.5x as wide as a naive bootstrap that resamples rows independently (observed ~2x on
    seed 2026). Ignoring institution clustering would overstate precision exactly where a false positive
    is possible. (Within a single term each institution has only ~2 rows, so the effect there is small, ~1.04x,
    and is not tested.)"""
    k = known_courses()
    inst = D.read_clean("institutions", CLEAN)
    private = (k["inst_id"].map(dict(zip(inst["inst_id"], inst["control"]))) == "private").to_numpy()
    pol, ones = k["policy"].to_numpy(float), np.ones(len(k))
    cb = ClusterBootstrap(k["inst_id"])
    naive = ClusterBootstrap(pd.Series(range(len(k))).astype(str))  # every row its own cluster

    def width(boot):
        return np.ptp(np.percentile(boot, [2.5, 97.5]))

    def gap(b):
        return b.ratio(np.where(private, pol, 0.0), private) - b.ratio(np.where(~private, pol, 0.0), ~private)

    assert width(cb.ratio(pol, ones)) / width(naive.ratio(pol, ones)) > 1.5
    assert width(gap(cb)) / width(gap(naive)) > 1.5


# --- ANL-05 ------------------------------------------------------------------------------------------
@pytest.mark.req("ANL-05")
def test_descriptives_record_bootstrap_settings(results):
    """descriptives.json states the method: cluster bootstrap over inst_id, 2,000 resamples, fixed seed, 95%."""
    b = results["descriptives"]["bootstrap"]
    assert b == {"method": "cluster bootstrap (percentile)", "cluster": "inst_id", "resamples": 2000, "seed": SEED, "ci_level": 0.95}


@pytest.mark.req("ANL-05")
@pytest.mark.parametrize("by", ["level", "is_se_label", "term", "census_region", "all"])
def test_policy_estimates_match_direct_computation(results, by):
    """Mean policy and the share of each policy value per group equal a direct pandas computation; shares
    in each group sum to 1; each estimate lies inside its CI; groups come in natural order."""
    k = known_courses()
    recs = [r for r in results["descriptives"]["policy"] if r["by"] == by]
    means = {r["group"]: r for r in recs if r["category"] == "mean"}
    direct = k.groupby(by)["policy"].mean()
    for g, r in means.items():
        assert r["estimate"] == pytest.approx(direct[g], abs=1e-6)
        assert r["ci_low"] <= r["estimate"] <= r["ci_high"]
    for g in means:
        shares = [r["estimate"] for r in recs if r["group"] == g and r["category"] != "mean"]
        assert sum(shares) == pytest.approx(1.0, abs=1e-5)
    if by == "term":
        assert list(means) == TERMS


@pytest.mark.req("ANL-05")
@pytest.mark.parametrize("by", ["carnegie", "year", "census_region", "all"])
def test_statement_code_prevalence_matches_coded_data(results, by):
    """Coded stance means and theme prevalence by carnegie, year, census_region and overall equal a direct
    computation from the coder's output (not the truth)."""
    s = D.load_statements(CLEAN)
    recs = [r for r in results["descriptives"]["statement_codes"] if r["by"] == by]
    for r in recs:
        sel = s[s[by] == r["group"]]
        if r["category"] == "mean":
            assert r["estimate"] == pytest.approx(sel["stance"].mean(), abs=1e-6)
        elif r["outcome"].startswith("coded_mentions"):
            assert r["estimate"] == pytest.approx(sel[r["outcome"][6:]].mean(), abs=1e-6)
    assert {r["outcome"] for r in recs} >= {"stance", "coded_stance", "coded_mentions_integrity",
                                            "coded_mentions_collaboration", "coded_mentions_careers"}


@pytest.mark.req("ANL-05")
def test_missing_policy_excluded_not_imputed(results):
    """Policy descriptives use known-policy rows only, and report how many rows were excluded."""
    c = results["descriptives"]["courses"]
    assert c["n_rows"] - c["n_known_policy"] == c["n_excluded_missing_policy"] > 0
    assert sum(r["n_rows"] for r in results["descriptives"]["policy"] if r["by"] == "level" and r["category"] == "mean") == c["n_known_policy"]


@pytest.mark.req("ANL-05")
def test_census_region_and_overall_groupings_cover_every_row(results):
    """The census_region groups are the four regions in a fixed order, and their row counts add up to the
    single overall group, which holds every known-policy course row (or every statement)."""
    d = results["descriptives"]
    for key, total in [("policy", d["courses"]["n_known_policy"]), ("statement_codes", d["statements"]["n"])]:
        means = [r for r in d[key] if r["category"] == "mean"]
        region = [r for r in means if r["by"] == "census_region"]
        overall = [r for r in means if r["by"] == "all"]
        assert [r["group"] for r in region] == ["Northeast", "Midwest", "South", "West"]
        assert [r["group"] for r in overall] == ["all"]
        assert sum(r["n_rows"] for r in region) == overall[0]["n_rows"] == total


# --- ANL-11 ------------------------------------------------------------------------------------------
@pytest.mark.req("ANL-11")
def test_allowed_uses_prevalence_by_level_and_se(results):
    """Each use's prevalence is reported by level and by SE vs non-SE, matching a direct computation over rows
    with policy >= 1."""
    c = D.load_courses(CLEAN)
    allow = c[c["policy"].notna() & (c["policy"] >= 1)]
    for r in results["allowed_uses"]["uses"]:
        sel = allow[allow[r["by"]] == r["group"]]
        assert r["estimate"] == pytest.approx(sel["allowed_uses"].str.split(";").apply(lambda xs: r["outcome"] in xs).mean(), abs=1e-6)
    assert {(r["by"], r["outcome"]) for r in results["allowed_uses"]["uses"]} == {
        (b, u) for b in ["level", "is_se_label"] for u in D.USES}


@pytest.mark.req("ANL-11")
@pytest.mark.kind("recovery")
def test_intro_gap_between_learning_uses_and_code_generation_shows_up(results):
    """DATA-15 recovery: in intro courses that allow AI, explanation and debugging are each allowed more often
    than code_generation, and the whole 95% cluster-bootstrap CI of each gap is above 0."""
    gaps = results["allowed_uses"]["intro_learning_vs_generation_gap"]
    assert {g["minuend"] for g in gaps} == {"explanation", "debugging"}
    assert all(g["ci_low"] > 0 for g in gaps)


# --- ANL-12 ------------------------------------------------------------------------------------------
@pytest.mark.req("ANL-12")
def test_assessment_by_policy_and_level_with_chi_square_and_cramers_v(results):
    """assessment_adaptation shares are reported by policy and by level (shares per group sum to 1); each
    association has a chi-square with a p-value labelled naive, and Cramér's V with a cluster-bootstrap CI."""
    a = results["assessment"]
    for by in ["policy", "level"]:
        groups = {r["group"] for r in a["shares"] if r["by"] == by}
        for g in groups:
            assert sum(r["estimate"] for r in a["shares"] if r["by"] == by and r["group"] == g) == pytest.approx(1, abs=1e-5)
    assert {x["col"] for x in a["association"]} == {"policy", "level"}
    for x in a["association"]:
        assert "naive" in x["p_value_note"] and "p_value_naive" in x
        assert x["cramers_v_ci"][0] <= x["cramers_v"] <= x["cramers_v_ci"][1]
        assert "cluster bootstrap" in x["cramers_v_ci_method"]
        assert x["cramers_v"] == pytest.approx(float(cramers_v(np.array(x["table"]))), abs=1e-6)


@pytest.mark.req("ANL-12")
def test_cramers_v_known_values():
    """Cramér's V is 1 for a perfectly associated table and 0 for an independent one."""
    assert cramers_v(np.array([[10, 0], [0, 10]])) == pytest.approx(1.0)
    assert cramers_v(np.array([[5, 5], [10, 10]])) == pytest.approx(0.0)


@pytest.mark.req("ANL-05")
@pytest.mark.req("ANL-11")
@pytest.mark.req("ANL-12")
def test_committed_descriptive_results_are_current(tmp_path):
    """results/{descriptives,allowed_uses,assessment}.json equal a fresh run on data/clean/."""
    D.main([str(CLEAN), str(tmp_path)])
    for n in ["descriptives", "allowed_uses", "assessment"]:
        assert (RESULTS / f"{n}.json").read_bytes() == (tmp_path / f"{n}.json").read_bytes(), n
