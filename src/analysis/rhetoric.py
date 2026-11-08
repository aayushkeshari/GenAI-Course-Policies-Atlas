"""ANL-13: rhetoric vs practice. Per institution, compare coded statement stance with mean course permissiveness.

Both are standardized (z-scores across institutions that have at least one statement). The gap is
z(stance) - z(policy): positive means the official rhetoric is more permissive than the courses, negative
means the courses are more permissive than the rhetoric. Institutions whose |gap| is in the top decile
are listed. Stance comes from the rule-based coder; policy from known-policy course rows.
Writes results/rhetoric.json.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.common import CLEAN, RESULTS, read_clean, write_json
from src.analysis.stats import N_BOOT, SEED, interval


def institution_table(clean_dir: Path = CLEAN) -> pd.DataFrame:
    coded = pd.read_csv(Path(clean_dir) / "statements_coded.csv", dtype=str, keep_default_na=False)
    coded["stance"] = coded["stance"].astype(int)
    st = coded.groupby("inst_id").agg(mean_stance=("stance", "mean"), n_statements=("stance", "size"))
    c = read_clean("courses", clean_dir)
    c = c[c["policy"].notna()]
    pol = c.groupby("inst_id").agg(mean_policy=("policy", lambda s: float(s.astype(float).mean())), n_course_rows=("policy", "size"))
    t = st.join(pol, how="inner").reset_index().sort_values("inst_id").reset_index(drop=True)
    for col, z in [("mean_stance", "z_stance"), ("mean_policy", "z_policy")]:
        t[z] = (t[col] - t[col].mean()) / t[col].std(ddof=1)
    t["gap"] = t["z_stance"] - t["z_policy"]
    return t


def rhetoric(clean_dir: Path = CLEAN) -> dict:
    t = institution_table(clean_dir)
    r = float(np.corrcoef(t["mean_stance"], t["mean_policy"])[0, 1])
    rng = np.random.default_rng(SEED)
    boots = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(t), len(t))  # institutions are the units here, so this is the cluster bootstrap
        s, p = t["mean_stance"].to_numpy()[idx], t["mean_policy"].to_numpy()[idx]
        if s.std() > 0 and p.std() > 0:
            boots.append(np.corrcoef(s, p)[0, 1])
    lo, hi = interval(np.array(boots))
    k = math.ceil(0.10 * len(t))
    top = t.reindex(t["gap"].abs().sort_values(ascending=False, kind="mergesort").index).head(k)
    listed = [{"inst_id": row.inst_id, "gap": row.gap, "z_stance": row.z_stance, "z_policy": row.z_policy,
               "mean_stance": row.mean_stance, "mean_policy": row.mean_policy, "n_statements": int(row.n_statements),
               "direction": "rhetoric more permissive than courses" if row.gap > 0 else "courses more permissive than rhetoric"}
              for row in top.itertuples()]
    return {"requirement": "ANL-13",
            "n_institutions": len(t),
            "note": "Institutions with at least one statement and at least one known-policy course row. Stance is coded "
                    "by the rule-based coder.",
            "correlation": {"pearson_r": r, "ci": [lo, hi],
                            "ci_method": f"bootstrap over institutions ({N_BOOT} resamples, seed {SEED}, percentile)"},
            "gap_definition": "z(mean coded stance) - z(mean course policy)",
            "top_decile_k": k,
            "top_decile": listed,
            "institutions": t[["inst_id", "mean_stance", "mean_policy", "z_stance", "z_policy", "gap", "n_statements",
                               "n_course_rows"]].to_dict(orient="records")}


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    clean_dir = Path(argv[0]) if argv else CLEAN
    out = Path(argv[1]) if len(argv) > 1 else RESULTS
    write_json(out / "rhetoric.json", rhetoric(clean_dir))


if __name__ == "__main__":
    main()
