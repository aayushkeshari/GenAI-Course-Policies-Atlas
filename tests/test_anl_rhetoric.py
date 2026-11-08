"""ANL-13: rhetoric vs practice per institution, and recovery of the DATA-17 rhetoric-gap institutions."""
import json
import math

import numpy as np
import pytest

from datautil import RAW, load_dir
from src.analysis import rhetoric as RH
from src.analysis.common import CLEAN, RESULTS, _jsonable
from src.evaluation import rhetoric_eval


@pytest.fixture(scope="module")
def rh():
    return json.loads((RESULTS / "rhetoric.json").read_text(encoding="utf-8"))


@pytest.mark.req("ANL-13")
def test_institution_scores_are_standardized_and_gap_defined(rh):
    """Per-institution mean coded stance and mean policy are z-standardized (mean 0, SD 1), the gap is
    z_stance - z_policy, and the correlation equals Pearson r of the two means, inside its bootstrap CI."""
    inst = rh["institutions"]
    for z in ["z_stance", "z_policy"]:
        vals = np.array([r[z] for r in inst])
        assert vals.mean() == pytest.approx(0, abs=1e-5) and vals.std(ddof=1) == pytest.approx(1, abs=1e-4)
    assert all(r["gap"] == pytest.approx(r["z_stance"] - r["z_policy"], abs=1e-5) for r in inst)
    r = np.corrcoef([x["mean_stance"] for x in inst], [x["mean_policy"] for x in inst])[0, 1]
    assert rh["correlation"]["pearson_r"] == pytest.approx(r, abs=1e-5)
    lo, hi = rh["correlation"]["ci"]
    assert lo <= rh["correlation"]["pearson_r"] <= hi


@pytest.mark.req("ANL-13")
def test_top_decile_lists_the_largest_gaps(rh):
    """The list holds ceil(10%) of institutions, they are the ones with the largest |gap|, and each direction
    label matches the sign of its gap."""
    n = rh["n_institutions"]
    assert rh["top_decile_k"] == math.ceil(0.1 * n) == len(rh["top_decile"])
    cutoff = min(abs(r["gap"]) for r in rh["top_decile"])
    listed = {r["inst_id"] for r in rh["top_decile"]}
    assert all(abs(r["gap"]) <= cutoff + 1e-9 for r in rh["institutions"] if r["inst_id"] not in listed)
    for r in rh["top_decile"]:
        assert r["direction"] == ("rhetoric more permissive than courses" if r["gap"] > 0 else "courses more permissive than rhetoric")


@pytest.mark.req("ANL-13")
@pytest.mark.kind("recovery")
def test_rhetoric_gap_institutions_are_recovered():
    """Recovery (reads the truth): results/rhetoric_recovery.json's precision and recall are correct against the
    DATA-17 flags; precision is well above the base rate of flagged institutions (> 3x), and each recovered
    institution's gap points the way its planted mismatch does."""
    saved = json.loads((RESULTS / "rhetoric_recovery.json").read_text(encoding="utf-8"))
    flags = load_dir(RAW)["ground_truth"]["institutions"]
    rh = json.loads((RESULTS / "rhetoric.json").read_text(encoding="utf-8"))
    listed = {r["inst_id"] for r in rh["top_decile"]}
    eligible = {r["inst_id"] for r in rh["institutions"]}
    flagged = {i for i, h in flags.items() if h["rhetoric_gap"] and i in eligible}
    assert saved["precision"] == pytest.approx(len(listed & flagged) / len(listed), abs=1e-6)
    assert saved["recall"] == pytest.approx(len(listed & flagged) / len(flagged), abs=1e-6)
    assert saved["precision"] > 3 * saved["base_rate"]
    assert saved["direction_correct"] == len(saved["hits"])


@pytest.mark.req("ANL-13")
def test_committed_rhetoric_results_are_current(tmp_path):
    """results/rhetoric.json and results/rhetoric_recovery.json equal fresh computations."""
    RH.main([str(CLEAN), str(tmp_path)])
    assert (RESULTS / "rhetoric.json").read_bytes() == (tmp_path / "rhetoric.json").read_bytes()
    saved = json.loads((RESULTS / "rhetoric_recovery.json").read_text(encoding="utf-8"))
    fresh = _jsonable(rhetoric_eval.recovery(tmp_path))
    assert {k: saved[k] for k in fresh} == fresh
