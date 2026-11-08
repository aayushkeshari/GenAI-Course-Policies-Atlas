"""ANL-08: does the analysis recover the planted truth? Writes results/recovery.json (reads the truth).

- Directions: DATA-06..09 from the analysis results.
- Null: DATA-10 private coefficient not significant at alpha = 0.05 under clustered SEs.
- Magnitudes: each regression coefficient divided by the term coefficient, compared with the planted ratio
  (planted effect / planted per-term step). Sanity check: estimate within +-25% of the planted ratio
  (for the null, whose planted ratio is 0, the check is that the CI covers 0).
- Coverage: across seeds 2026, 1, 2, 3, 4 (regenerated, cleaned, refit), the clustered 95% CI of each ratio
  contains the planted value in at least 4 of 5 seeds.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

from src.analysis import clean as clean_mod
from src.analysis import inference
from src.analysis.common import RESULTS, write_json
from src.evaluation.truth import TRUTH_FILE

ROOT = Path(__file__).resolve().parents[2]
SEEDS = [2026, 1, 2, 3, 4]
ALPHA = 0.05
TOLERANCE = 0.25
MIN_COVERED = 4


def planted_ratios(params: dict) -> dict[str, float]:
    m = params["policy_model"]
    step = m["term_effect_per_step"]
    lev = m["level_effect"]
    return {"intermediate": (lev["intermediate"] - lev["intro"]) / step,
            "upper": (lev["upper"] - lev["intro"]) / step,
            "graduate": (lev["graduate"] - lev["intro"]) / step,
            "is_se": m["se_effect"] / step,
            "private": (m["control_effect"]["private"] - m["control_effect"]["public"]) / step}


def _generator():
    spec = importlib.util.spec_from_file_location("generate", ROOT / "src" / "data" / "generate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seed_fit(seed: int) -> tuple[dict, dict]:
    """Regenerate a seed, clean it, refit the clustered regression. Returns (ratios with CIs, private coef)."""
    with tempfile.TemporaryDirectory() as d:
        raw, cln = Path(d) / "raw", Path(d) / "clean"
        _generator().generate(seed, raw)
        clean_mod.clean(raw, cln)
        reg = inference.regression(cln, with_bootstrap=False)
        params = json.loads((raw / "ground_truth.json").read_text(encoding="utf-8"))["parameters"]
    ratios = {r["numerator"]: r for r in reg["ratios_to_term_effect"]["ratios"]}
    private = next(c for c in reg["coefficients"] if c["term"] == "private")
    return ratios, private, planted_ratios(params)


def recovery(results_dir: Path = RESULTS, truth_path: Path = TRUTH_FILE) -> dict:
    res = lambda n: json.loads((Path(results_dir) / f"{n}.json").read_text(encoding="utf-8"))
    desc, reg = res("descriptives"), res("regression")
    params = json.loads(Path(truth_path).read_text(encoding="utf-8"))["parameters"]
    coef = {c["term"]: c for c in reg["coefficients"]}
    mean = lambda by, g: next(r["estimate"] for r in desc["policy"] if r["by"] == by and r["group"] == g and r["category"] == "mean")
    stance = {r["group"]: r["estimate"] for r in desc["statement_codes"] if r["by"] == "carnegie" and r["category"] == "mean"}
    term_means = [mean("term", t) for t in desc["courses"]["term_order"]]
    directions = {
        "DATA-06": {"claim": "intro courses more restrictive than upper-level",
                    "evidence": {"mean_policy_intro": mean("level", "intro"), "mean_policy_upper": mean("level", "upper"),
                                 "coef_upper_vs_intro": coef["upper"]["coef"], "ci_clustered": coef["upper"]["ci_clustered"]},
                    "recovered": mean("level", "intro") < mean("level", "upper") and coef["upper"]["ci_clustered"][0] > 0},
        "DATA-07": {"claim": "SE more permissive than non-SE at the same level (regression controls for level)",
                    "evidence": {"coef_is_se": coef["is_se"]["coef"], "ci_clustered": coef["is_se"]["ci_clustered"]},
                    "recovered": coef["is_se"]["ci_clustered"][0] > 0},
        "DATA-08": {"claim": "permissiveness rises each term",
                    "evidence": {"mean_policy_by_term": term_means, "coef_term_index": coef["term_index"]["coef"],
                                 "ci_clustered": coef["term_index"]["ci_clustered"]},
                    "recovered": coef["term_index"]["ci_clustered"][0] > 0 and all(a < b for a, b in zip(term_means, term_means[1:]))},
        "DATA-09": {"claim": "R1 departments have a more positive (coded) statement stance",
                    "evidence": {"mean_coded_stance_by_carnegie": stance},
                    "recovered": all(stance["R1"] > v for k, v in stance.items() if k != "R1")},
    }
    null = {"DATA-10": {"claim": "control (public/private) has no effect on policy (planted null)",
                        "coef_private": coef["private"]["coef"], "p_clustered": coef["private"]["p_clustered"],
                        "p_naive": coef["private"]["p_naive"], "alpha": ALPHA,
                        "recovered": coef["private"]["p_clustered"] >= ALPHA}}
    planted = planted_ratios(params)
    ratios = {r["numerator"]: r for r in reg["ratios_to_term_effect"]["ratios"]}
    magnitude = []
    for name, true in planted.items():
        est, ci = ratios[name]["estimate"], ratios[name]["ci"]
        within = (ci[0] <= 0 <= ci[1]) if true == 0 else abs(est / true - 1) <= TOLERANCE
        magnitude.append({"ratio": f"{name} / term_index", "planted": true, "estimate": est, "ci": ci,
                          "relative_error": None if true == 0 else est / true - 1, "within_tolerance": within})
    per_seed = []
    for seed in SEEDS:
        r, priv, true = seed_fit(seed)
        per_seed.append({"seed": seed,
                         "covered": {n: r[n]["ci"][0] <= true[n] <= r[n]["ci"][1] for n in true},
                         "private_p_clustered": priv["p_clustered"], "private_p_naive": priv["p_naive"]})
    coverage = {n: sum(s["covered"][n] for s in per_seed) for n in planted}
    return {"requirement": "ANL-08", "kind": "recovery (reads ground truth)",
            "directions": directions, "null": null,
            "magnitude": {"tolerance": TOLERANCE, "ratios": magnitude},
            "coverage": {"seeds": SEEDS, "min_covered": MIN_COVERED, "covered_counts": coverage,
                         "all_met": all(v >= MIN_COVERED for v in coverage.values()), "per_seed": per_seed}}


def main(argv=None) -> None:
    write_json(RESULTS / "recovery.json", recovery())


if __name__ == "__main__":
    main()
