"""ANL-05 (descriptives), ANL-11 (allowed uses), ANL-12 (assessment) with cluster-bootstrap 95% CIs.

Writes results/descriptives.json, results/allowed_uses.json, results/assessment.json.
Rows with a missing policy are excluded from anything that conditions on policy (listed as n_excluded).
Statement stance and themes come from the rule-based coder (data/clean/statements_coded.csv), not the truth.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.common import CLEAN, LEVELS, RESULTS, TERMS, read_clean, write_json
from src.analysis.stats import BOOTSTRAP_INFO, ClusterBootstrap, association, interval, mean_records, share_records

POLICIES = [0, 1, 2, 3, 4]
ORDER = {"level": LEVELS, "term": TERMS, "is_se_label": ["non-SE", "SE"],
         "carnegie": ["R1", "R2", "Masters", "Baccalaureate"], "policy": POLICIES,
         "census_region": ["Northeast", "Midwest", "South", "West"], "all": ["all"]}
OVERALL = "all"  # by == group == "all": one group holding every row (overall prevalence)
STANCES = [-2, -1, 0, 1, 2]
THEMES = ["mentions_integrity", "mentions_collaboration", "mentions_careers"]
USES = ["explanation", "debugging", "code_generation", "testing", "writing"]
ASSESSMENTS = ["none", "in_class_exams", "oral_defense", "process_logs", "ai_critique"]


def load_courses(clean_dir: Path) -> pd.DataFrame:
    c = read_clean("courses", clean_dir)
    c["is_se_label"] = np.where(c["is_se"], "SE", "non-SE")
    c["level"] = pd.Categorical(c["level"], LEVELS, ordered=True).astype(str)
    inst = read_clean("institutions", clean_dir)[["inst_id", "census_region"]]
    c = c.merge(inst, on="inst_id", how="left", validate="many_to_one")
    c[OVERALL] = OVERALL
    return c


def load_statements(clean_dir: Path) -> pd.DataFrame:
    coded = pd.read_csv(Path(clean_dir) / "statements_coded.csv", dtype=str, keep_default_na=False)
    s = read_clean("statements", clean_dir)[["stmt_id", "pub_date"]]
    inst = read_clean("institutions", clean_dir)[["inst_id", "carnegie", "census_region"]]
    df = coded.merge(s, on="stmt_id").merge(inst, on="inst_id")
    df["stance"] = df["stance"].astype(int)
    for t in THEMES:
        df[t] = df[t] == "true"
    df["year"] = df["pub_date"].str[:4]
    df[OVERALL] = OVERALL
    return df


def descriptives(clean_dir: Path = CLEAN) -> dict:
    c = load_courses(clean_dir)
    known = c[c["policy"].notna()].reset_index(drop=True)
    known["policy"] = known["policy"].astype(int)
    cb = ClusterBootstrap(known["inst_id"])
    policy = []
    for by in ["level", "is_se_label", "term", "census_region", OVERALL]:
        policy += share_records(known, by, "policy", POLICIES, cb, order=ORDER.get(by))
        policy += mean_records(known, by, "policy", cb, order=ORDER.get(by))
    s = load_statements(clean_dir)
    sb = ClusterBootstrap(s["inst_id"])
    statements = []
    for by in ["carnegie", "year", "census_region", OVERALL]:
        statements += share_records(s, by, "stance", STANCES, sb, "coded_stance", order=ORDER.get(by))
        statements += mean_records(s, by, "stance", sb, order=ORDER.get(by))
        for t in THEMES:
            statements += share_records(s, by, t, [True], sb, f"coded_{t}", order=ORDER.get(by))
    return {"requirement": "ANL-05", "bootstrap": BOOTSTRAP_INFO,
            "courses": {"n_rows": len(c), "n_known_policy": len(known), "n_excluded_missing_policy": len(c) - len(known),
                        "term_order": TERMS, "level_order": LEVELS},
            "statements": {"n": len(s), "n_institutions": s["inst_id"].nunique(),
                           "source": "rule-based coder (data/clean/statements_coded.csv)"},
            "policy": policy, "statement_codes": statements}


def allowed_uses(clean_dir: Path = CLEAN) -> dict:
    c = load_courses(clean_dir)
    allow = c[c["policy"].notna() & (c["policy"] >= 1)].reset_index(drop=True)
    for u in USES:
        allow[u] = allow["allowed_uses"].str.split(";").apply(lambda xs, u=u: u in xs)
    cb = ClusterBootstrap(allow["inst_id"])
    records = []
    for by in ["level", "is_se_label"]:
        for u in USES:
            records += share_records(allow, by, u, [True], cb, u, order=ORDER.get(by))
    intro = (allow["level"] == "intro").to_numpy()
    gaps = []
    for learn in ["explanation", "debugging"]:
        a, b = intro & allow[learn].to_numpy(), intro & allow["code_generation"].to_numpy()
        boot = cb.ratio(a, intro) - cb.ratio(b, intro)
        est = (a.sum() - b.sum()) / intro.sum()
        lo, hi = interval(boot)
        gaps.append({"group": "intro", "minuend": learn, "subtrahend": "code_generation", "estimate": float(est),
                     "ci_low": lo, "ci_high": hi, "n_rows": int(intro.sum())})
    return {"requirement": "ANL-11", "bootstrap": BOOTSTRAP_INFO,
            "denominator": "course-term rows with known policy >= 1 (allowed_uses is empty at policy 0 by design)",
            "n_rows": len(allow), "uses": records, "intro_learning_vs_generation_gap": gaps}


def assessment(clean_dir: Path = CLEAN) -> dict:
    c = load_courses(clean_dir)
    cb_all = ClusterBootstrap(c["inst_id"])
    known = c[c["policy"].notna()].reset_index(drop=True)
    known["policy"] = known["policy"].astype(int)
    cb_known = ClusterBootstrap(known["inst_id"])
    records = share_records(known, "policy", "assessment_adaptation", ASSESSMENTS, cb_known, order=POLICIES)
    records += share_records(c, "level", "assessment_adaptation", ASSESSMENTS, cb_all, order=LEVELS)
    return {"requirement": "ANL-12", "bootstrap": BOOTSTRAP_INFO,
            "note": "By policy: known-policy rows only. By level: all rows (assessment_adaptation is never missing).",
            "shares": records,
            "association": [association(known, "assessment_adaptation", "policy", cb_known),
                            association(c, "assessment_adaptation", "level", cb_all)]}


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    clean_dir = Path(argv[0]) if argv else CLEAN
    out = Path(argv[1]) if len(argv) > 1 else RESULTS
    write_json(out / "descriptives.json", descriptives(clean_dir))
    write_json(out / "allowed_uses.json", allowed_uses(clean_dir))
    write_json(out / "assessment.json", assessment(clean_dir))


if __name__ == "__main__":
    main()
