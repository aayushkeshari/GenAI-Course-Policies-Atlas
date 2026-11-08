"""ANL-06 (association), ANL-07 (ordinal logistic regression), ANL-14 (institution clustering).

Main inference for the regression: cluster-robust (sandwich) standard errors grouped by inst_id
(statsmodels OrderedModel.fit(cov_type="cluster")). Naive SEs are reported alongside so the effect of
clustering is visible, and a cluster bootstrap (institutions resampled, refit each time) cross-checks the
sandwich SEs.

Writes results/association.json and results/regression.json.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.miscmodels.ordinal_model import OrderedModel

from src.analysis.common import CLEAN, RESULTS, read_clean, write_json
from src.analysis.stats import BOOTSTRAP_INFO, ClusterBootstrap, association

REGRESSION_BOOT = 500   # refits for the cluster-bootstrap cross-check (main inference is the sandwich SE)
REGRESSION_SEED = 4005
REFERENCE = {"level": "intro", "control": "public", "carnegie": "R1"}
PREDICTORS = ["intermediate", "upper", "graduate", "is_se", "term_index", "private", "R2", "Masters", "Baccalaureate"]
RATIO_BASE = "term_index"
RATIOS = ["intermediate", "upper", "graduate", "is_se", "private"]


def model_frame(clean_dir: Path = CLEAN) -> tuple[pd.Series, pd.DataFrame, pd.Series, int]:
    """Known-policy rows -> (y, X, inst_id groups, n excluded for missing policy)."""
    c = read_clean("courses", clean_dir)
    n_missing = int(c["policy"].isna().sum())
    c = c[c["policy"].notna()].merge(read_clean("institutions", clean_dir)[["inst_id", "control", "carnegie"]],
                                     on="inst_id").reset_index(drop=True)
    X = pd.DataFrame({
        "intermediate": (c["level"] == "intermediate") * 1.0, "upper": (c["level"] == "upper") * 1.0,
        "graduate": (c["level"] == "graduate") * 1.0, "is_se": c["is_se"] * 1.0,
        "term_index": c["term_index"] * 1.0, "private": (c["control"] == "private") * 1.0,
        "R2": (c["carnegie"] == "R2") * 1.0, "Masters": (c["carnegie"] == "Masters") * 1.0,
        "Baccalaureate": (c["carnegie"] == "Baccalaureate") * 1.0})[PREDICTORS]
    return c["policy"].astype(int), X, c["inst_id"], n_missing


def _fit(y, X, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return OrderedModel(y, X, distr="logit").fit(method="bfgs", disp=False, maxiter=2000, **kw)


def fit_clustered(clean_dir: Path = CLEAN):
    """The main model: ordinal logit with SEs clustered by inst_id. Returns (result, y, X, groups, n_missing)."""
    y, X, groups, n_missing = model_frame(clean_dir)
    res = _fit(y, X, cov_type="cluster", cov_kwds={"groups": pd.factorize(groups)[0]})
    return res, y, X, groups, n_missing


def ratio_ci(res, num: str, den: str = RATIO_BASE) -> dict:
    """num/den with a delta-method 95% CI from the (clustered) covariance matrix."""
    b, cov = res.params, res.cov_params()
    a, d = b[num], b[den]
    grad = np.array([1 / d, -a / d ** 2])
    v = cov.loc[[num, den], [num, den]].to_numpy()
    se = float(np.sqrt(grad @ v @ grad))
    z = norm.ppf(0.975)
    return {"numerator": num, "denominator": den, "estimate": float(a / d), "se": se,
            "ci": [float(a / d - z * se), float(a / d + z * se)]}


def bootstrap_se(y, X, groups, start, n_boot: int = REGRESSION_BOOT, seed: int = REGRESSION_SEED) -> pd.Series:
    """Cluster bootstrap SEs: resample institutions with replacement, refit, take the SD of each coefficient."""
    rng = np.random.default_rng(seed)
    clusters = np.array(sorted(groups.unique()))
    rows = {g: np.flatnonzero(groups.to_numpy() == g) for g in clusters}
    draws = []
    for _ in range(n_boot):
        idx = np.concatenate([rows[g] for g in rng.choice(clusters, size=len(clusters), replace=True)])
        yb, Xb = y.iloc[idx].reset_index(drop=True), X.iloc[idx].reset_index(drop=True)
        if yb.nunique() < 5:   # a resample missing a policy level cannot be fit with the same thresholds
            continue
        draws.append(_fit(yb, Xb, start_params=start).params[PREDICTORS])
    return pd.DataFrame(draws).std(ddof=1), len(draws)


def regression(clean_dir: Path = CLEAN, with_bootstrap: bool = True) -> dict:
    res, y, X, groups, n_missing = fit_clustered(clean_dir)
    naive = _fit(y, X)
    z = norm.ppf(0.975)
    if with_bootstrap:
        boot_se, n_ok = bootstrap_se(y, X, groups, res.params.to_numpy())
    coefs = []
    for p in PREDICTORS:
        b = float(res.params[p])
        row = {"term": p, "coef": b,
               "se_clustered": float(res.bse[p]), "ci_clustered": [float(res.conf_int().loc[p, 0]), float(res.conf_int().loc[p, 1])],
               "p_clustered": float(res.pvalues[p]),
               "se_naive": float(naive.bse[p]), "ci_naive": [float(naive.conf_int().loc[p, 0]), float(naive.conf_int().loc[p, 1])],
               "p_naive": float(naive.pvalues[p])}
        if with_bootstrap:
            row["se_cluster_bootstrap"] = float(boot_se[p])
            row["ci_cluster_bootstrap"] = [b - z * float(boot_se[p]), b + z * float(boot_se[p])]
        coefs.append(row)
    out = {"requirement": ["ANL-07", "ANL-14"],
           "model": "ordinal logistic regression (statsmodels OrderedModel, logit link): "
                    "policy ~ level + is_se + term_index + control + carnegie",
           "reference_categories": REFERENCE,
           "n_used": int(len(y)), "n_excluded_missing_policy": n_missing, "n_clusters": int(groups.nunique()),
           "inference": {"main": "cluster-robust (sandwich) SEs grouped by inst_id",
                         "also_reported": ["naive SEs (rows treated as independent)"]},
           "coefficients": coefs,
           "thresholds": [float(v) for v in res.params[len(PREDICTORS):]],
           "ratios_to_term_effect": {
               "description": "coefficient / term_index coefficient: each effect in units of one term of the time "
                              "trend; 95% CI by the delta method on the clustered covariance",
               "ratios": [ratio_ci(res, r) for r in RATIOS]},
           "converged": bool(res.mle_retvals.get("converged", True))}
    if with_bootstrap:
        out["inference"]["also_reported"].append(
            f"cluster bootstrap SEs (cross-check): {REGRESSION_BOOT} institution resamples, seed {REGRESSION_SEED}, "
            f"{n_ok} fitted")
    return out


def associations(clean_dir: Path = CLEAN) -> dict:
    c = read_clean("courses", clean_dir)
    known = c[c["policy"].notna()].reset_index(drop=True)
    known["policy"] = known["policy"].astype(int)
    known["is_se_label"] = np.where(known["is_se"], "SE", "non-SE")
    cb = ClusterBootstrap(known["inst_id"])
    return {"requirement": ["ANL-06", "ANL-14"], "bootstrap": BOOTSTRAP_INFO,
            "n_used": len(known), "n_excluded_missing_policy": int(c["policy"].isna().sum()),
            "associations": [association(known, "policy", "level", cb), association(known, "policy", "is_se_label", cb)]}


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    clean_dir = Path(argv[0]) if argv else CLEAN
    out = Path(argv[1]) if len(argv) > 1 else RESULTS
    write_json(out / "association.json", associations(clean_dir))
    write_json(out / "regression.json", regression(clean_dir))


if __name__ == "__main__":
    main()
