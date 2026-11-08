"""ANL-03 (held-out coder evaluation with frozen rules) and ANL-04 (hand-coding sample and kappa)."""
import csv
import json

import pytest

from datautil import RAW, load_dir
from src.analysis.common import CLEAN, RESULTS, _jsonable, read_clean
from src.evaluation import coder_eval, hand_sample, truth

AWAITING = "awaiting human coding (ANL-04)"


# --- ANL-03 --------------------------------------------------------------------------------------------
@pytest.mark.req("ANL-03")
def test_score_computes_known_metrics():
    """On a hand-checked toy case, score() gives the expected precision, recall, F1, stance confusion matrix
    and macro-F1."""
    import pandas as pd
    t = {"a": {"stance": 1, "mentions_integrity": True, "mentions_collaboration": False, "mentions_careers": True},
         "b": {"stance": 0, "mentions_integrity": True, "mentions_collaboration": True, "mentions_careers": False},
         "c": {"stance": 1, "mentions_integrity": False, "mentions_collaboration": False, "mentions_careers": False}}
    coded = pd.DataFrame([{"stmt_id": "a", "stance": 1, "mentions_integrity": True, "mentions_collaboration": False, "mentions_careers": True},
                          {"stmt_id": "b", "stance": 1, "mentions_integrity": False, "mentions_collaboration": True, "mentions_careers": False},
                          {"stmt_id": "c", "stance": 1, "mentions_integrity": True, "mentions_collaboration": False, "mentions_careers": False}])
    s = coder_eval.score(t, coded)
    assert s["labels"]["mentions_integrity"] == pytest.approx({"precision": 0.5, "recall": 0.5, "f1": 0.5, "support": 2})
    assert s["labels"]["mentions_collaboration"]["f1"] == 1.0
    assert s["stance"]["confusion_matrix"]["rows_true_cols_coded"]["0"]["1"] == 1
    assert s["stance"]["accuracy"] == pytest.approx(2 / 3)
    # stance classes present: 0 (f1 0) and 1 (p 2/3, r 1, f1 0.8) -> macro 0.4
    assert s["stance"]["macro_f1"] == pytest.approx(0.4)
    assert s["macro_f1"] == pytest.approx((0.5 + 1.0 + 1.0 + 0.4) / 4)


@pytest.mark.req("ANL-03")
def test_heldout_report_is_current_and_rules_are_frozen():
    """results/coder_eval.json equals a fresh held-out evaluation, and its rules fingerprint equals the
    current coder + codebook. Any later rule change fails this test until the change is consciously
    re-frozen and re-reported (and logged in progress.md)."""
    saved = json.loads((RESULTS / "coder_eval.json").read_text(encoding="utf-8"))
    assert saved["rules_sha256"] == coder_eval.rules_sha256(), "coder or codebook changed after the freeze"
    fresh = _jsonable(coder_eval.heldout_report())
    for key in ["heldout", "heldout_with_reserved_phrasings", "heldout_without_reserved_phrasings", "dev", "target_met"]:
        assert saved[key] == fresh[key], key


@pytest.mark.req("ANL-03")
def test_heldout_report_covers_the_held_out_half_and_reports_target_honestly():
    """The held-out score covers every held-out statement and no dev statement; the reserved/non-reserved
    subsets partition it; target_met is exactly macro_f1 >= 0.80."""
    saved = json.loads((RESULTS / "coder_eval.json").read_text(encoding="utf-8"))
    s = read_clean("statements", CLEAN)
    n_held = sum(truth.split_of(i) == "heldout" for i in s["inst_id"])
    assert saved["heldout"]["n"] == n_held and saved["dev"]["n"] == len(s) - n_held
    assert saved["heldout_with_reserved_phrasings"]["n"] + saved["heldout_without_reserved_phrasings"]["n"] == n_held
    assert saved["target_met"] == (saved["heldout"]["macro_f1"] >= 0.80)


# --- ANL-04 --------------------------------------------------------------------------------------------
@pytest.mark.req("ANL-04")
def test_hand_sample_is_30_held_out_statements():
    """data/reference/hand_code_sample.csv has the expected columns and 30 distinct held-out statements whose
    text matches statements.csv."""
    rows = hand_sample.read_sample()
    assert list(rows[0]) == hand_sample.COLUMNS
    assert len(rows) == 30 and len({r["stmt_id"] for r in rows}) == 30
    s = read_clean("statements", CLEAN)
    inst, text = dict(zip(s["stmt_id"], s["inst_id"])), dict(zip(s["stmt_id"], s["text"]))
    for r in rows:
        assert truth.split_of(inst[r["stmt_id"]]) == "heldout"
        assert r["text"] == text[r["stmt_id"]]


@pytest.mark.req("ANL-04")
def test_hand_sample_header_comment_names_aayush():
    """The sample file starts with a # comment saying it is coded by Aayush and how kappa is labelled."""
    first = hand_sample.SAMPLE.read_text(encoding="utf-8").splitlines()[0]
    assert first == hand_sample.HEADER_COMMENT
    assert "Coded by Aayush" in first and '"Aayush vs coder"' in first and '"Aayush vs truth"' in first


@pytest.mark.req("ANL-04")
def test_hand_sample_values_are_blank_or_valid():
    """Every code cell is blank (not yet coded) or an allowed value: stance -2..2, labels true/false."""
    for r in hand_sample.read_sample():
        for c in hand_sample.CODE_COLUMNS:
            v = r[c].strip().lower()
            assert v == "" or v in hand_sample.ALLOWED[c], (r["stmt_id"], c, r[c])


@pytest.mark.req("ANL-04")
def test_sample_is_never_overwritten_once_coding_has_started(tmp_path):
    """make_sample() writes a blank sample, but refuses to touch a sample with any coded cell."""
    path = tmp_path / "sample.csv"
    assert hand_sample.make_sample(CLEAN, path)
    rows = hand_sample.read_sample(path)
    rows[0]["stance"] = "1"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hand_sample.COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    before = path.read_bytes()
    assert hand_sample.make_sample(CLEAN, path) is False
    assert path.read_bytes() == before


@pytest.mark.req("ANL-04")
def test_cohen_kappa_known_values():
    """Kappa is 1 for perfect agreement, 0 at chance level, and matches a textbook 2x2 example (0.4)."""
    assert hand_sample.cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    assert hand_sample.cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)
    a = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert hand_sample.cohen_kappa(a, b) == pytest.approx(0.4)


@pytest.mark.req("ANL-04")
def test_kappa_pipeline_works_on_a_truth_filled_copy(tmp_path):
    """Filling a copy of the sample with the true labels gives kappa 1 for Aayush vs truth, and a defined
    kappa for Aayush vs coder: the pipeline works independently of the real coding."""
    gt = load_dir(RAW)["ground_truth"]["statements"]
    rows = hand_sample.read_sample()
    for r in rows:
        r.update({"stance": str(gt[r["stmt_id"]]["stance"]),
                  **{l: str(gt[r["stmt_id"]][l]).lower() for l in hand_sample.CODE_COLUMNS[1:]}})
    path = tmp_path / "filled.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hand_sample.COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    rep = hand_sample.kappa_report(CLEAN, path)
    assert rep["n"] == 30
    assert all(v == pytest.approx(1.0) for v in rep["aayush_vs_truth"].values())
    assert all(-1.0 <= v <= 1.0 for v in rep["aayush_vs_coder"].values())


@pytest.mark.req("ANL-04")
@pytest.mark.kind("integration")
def test_human_agreement_kappa_reported():
    """HUMAN task. Once Aayush has coded every row of the sample, results/kappa.json holds Cohen's kappa for
    "Aayush vs coder" and "Aayush vs truth", and matches a fresh computation. Until then this test is SKIPPED
    (not passed) with reason 'awaiting human coding (ANL-04)', so the validation explorer shows it as pending."""
    rows = hand_sample.read_sample()
    if hand_sample.status(rows) != "complete":
        pytest.skip(AWAITING)
    saved = json.loads((RESULTS / "kappa.json").read_text(encoding="utf-8"))
    fresh = _jsonable(hand_sample.kappa_report())
    assert saved["aayush_vs_coder"] == fresh["aayush_vs_coder"] and saved["aayush_vs_truth"] == fresh["aayush_vs_truth"]
    assert saved["coder_by"] == "Aayush"
    assert saved["comparison_labels"] == {"aayush_vs_coder": "Aayush vs coder", "aayush_vs_truth": "Aayush vs truth"}
