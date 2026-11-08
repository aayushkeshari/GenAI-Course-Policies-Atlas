"""ANL-03: score the rule-based coder against the truth.

`dev` mode (for tuning) only ever loads dev labels. `heldout` mode is for the final report, run after
the rules are frozen; it records a hash of the coder and codebook so a later rule change is detectable.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

from src.analysis.code_text import LABELS, code_statements
from src.analysis.common import CLEAN, RESULTS, read_clean, write_json
from src.evaluation.truth import load_truth

ROOT = Path(__file__).resolve().parents[2]
STANCES = [-2, -1, 0, 1, 2]
RULE_FILES = [ROOT / "src" / "analysis" / "code_text.py", ROOT / "docs" / "codebook.md"]


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "support": tp + fn}


def score(truth: dict[str, dict], coded: pd.DataFrame) -> dict:
    """Per-label P/R/F1 (positive class), stance per-class P/R/F1 + confusion matrix, and macro-F1.
    macro_f1 = mean of the three label F1s and the stance macro-F1 (mean over the 5 stance classes)."""
    c = coded.set_index("stmt_id").loc[sorted(truth)]
    out = {"n": len(truth), "labels": {}}
    for label in LABELS:
        t = [truth[s][label] for s in c.index]
        p = list(c[label])
        tp = sum(a and b for a, b in zip(t, p))
        fp = sum(b and not a for a, b in zip(t, p))
        fn = sum(a and not b for a, b in zip(t, p))
        out["labels"][label] = prf(tp, fp, fn)
    t = [truth[s]["stance"] for s in c.index]
    p = [int(x) for x in c["stance"]]
    confusion = {str(a): {str(b): sum(1 for x, y in zip(t, p) if x == a and y == b) for b in STANCES} for a in STANCES}
    per_class = {}
    for k in STANCES:
        tp = sum(x == k and y == k for x, y in zip(t, p))
        fp = sum(x != k and y == k for x, y in zip(t, p))
        fn = sum(x == k and y != k for x, y in zip(t, p))
        per_class[str(k)] = prf(tp, fp, fn)
    present = [v["f1"] for k, v in per_class.items() if v["support"] > 0]
    stance_macro = sum(present) / len(present)
    out["stance"] = {"per_class": per_class, "macro_f1": stance_macro,
                     "accuracy": sum(x == y for x, y in zip(t, p)) / len(t),
                     "confusion_matrix": {"rows_true_cols_coded": confusion}}
    parts = [out["labels"][l]["f1"] for l in LABELS] + [stance_macro]
    out["macro_f1"] = sum(parts) / len(parts)
    return out


def rules_sha256() -> str:
    h = hashlib.sha256()
    for f in RULE_FILES:
        h.update(f.read_bytes())
    return h.hexdigest()


def evaluate(split: str, clean_dir: Path = CLEAN) -> dict:
    statements = read_clean("statements", clean_dir)
    truth = load_truth(split, dict(zip(statements["stmt_id"], statements["inst_id"])))
    coded = code_statements(statements)
    return score(truth, coded)


def dev_report(clean_dir: Path = CLEAN) -> dict:
    """Tuning aid: dev-half scores plus every dev disagreement with the rule that fired."""
    statements = read_clean("statements", clean_dir)
    truth = load_truth("dev", dict(zip(statements["stmt_id"], statements["inst_id"])))
    coded = code_statements(statements).set_index("stmt_id")
    text = dict(zip(statements["stmt_id"], statements["text"]))
    errors = []
    for sid, lab in truth.items():
        row = coded.loc[sid]
        diffs = {k: {"truth": lab[k], "coded": (int(row[k]) if k == "stance" else bool(row[k]))}
                 for k in ["stance"] + LABELS if (int(row[k]) if k == "stance" else bool(row[k])) != lab[k]}
        if diffs:
            errors.append({"stmt_id": sid, "diffs": diffs, "stance_rule": row["stance_rule"], "text": text[sid]})
    return {"scores": score(truth, coded.reset_index()), "errors": errors}


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "dev":
        rep = dev_report()
        write_json(RESULTS / "coder_dev_eval.json", {"requirement": "ANL-03", "split": "dev", **rep})
        print(f"dev macro-F1 {rep['scores']['macro_f1']:.3f}, {len(rep['errors'])} statements with errors")


if __name__ == "__main__":
    main()
