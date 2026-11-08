"""ANL-04: the hand-coding sample (30 held-out statements, blank labels) and Cohen's kappa once it is filled.

The sample is chosen with the public split rule only (no truth needed). It is never overwritten once any
label has been filled in. Kappa is computed only when every row is fully coded; until then the status is
"pending" and no results/kappa.json is written.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

from src.analysis.code_text import LABELS, code_statements
from src.analysis.common import CLEAN, RESULTS, read_clean, write_json
from src.evaluation.truth import load_truth, split_of

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "reference" / "hand_code_sample.csv"
SAMPLE_SEED = 4005
SAMPLE_SIZE = 30
CODE_COLUMNS = ["stance"] + LABELS
COLUMNS = ["stmt_id", "text"] + CODE_COLUMNS
ALLOWED = {"stance": {"-2", "-1", "0", "1", "2"}, **{l: {"true", "false"} for l in LABELS}}


def read_sample(path: Path = SAMPLE) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def status(rows: list[dict]) -> str:
    """'blank' (nothing coded), 'partial', or 'complete'."""
    filled = [r[c].strip() != "" for r in rows for c in CODE_COLUMNS]
    return "complete" if all(filled) else ("partial" if any(filled) else "blank")


def make_sample(clean_dir: Path = CLEAN, path: Path = SAMPLE) -> bool:
    """Write the blank sample. Returns False (and writes nothing) if a sample with any coding already exists."""
    path = Path(path)
    if path.exists() and status(read_sample(path)) != "blank":
        return False
    s = read_clean("statements", clean_dir)
    held = sorted(sid for sid, iid in zip(s["stmt_id"], s["inst_id"]) if split_of(iid) == "heldout")
    chosen = sorted(random.Random(SAMPLE_SEED).sample(held, SAMPLE_SIZE))
    text = dict(zip(s["stmt_id"], s["text"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for sid in chosen:
            w.writerow({"stmt_id": sid, "text": text[sid], **{c: "" for c in CODE_COLUMNS}})
    return True


def cohen_kappa(a: list, b: list) -> float:
    """Unweighted Cohen's kappa for two equal-length lists of category labels."""
    n = len(a)
    cats = sorted(set(a) | set(b), key=str)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def kappa_report(clean_dir: Path = CLEAN, path: Path = SAMPLE) -> dict | None:
    rows = read_sample(path)
    if status(rows) != "complete":
        return None
    s = read_clean("statements", clean_dir)
    coded = code_statements(s).set_index("stmt_id")
    truth = load_truth("heldout", dict(zip(s["stmt_id"], s["inst_id"])))
    ids = [r["stmt_id"] for r in rows]
    human = {c: [r[c].strip().lower() for r in rows] for c in CODE_COLUMNS}
    coder = {c: [str(int(coded.loc[i, c])) if c == "stance" else str(bool(coded.loc[i, c])).lower() for i in ids] for c in CODE_COLUMNS}
    true = {c: [str(truth[i][c]) if c == "stance" else str(truth[i][c]).lower() for i in ids] for c in CODE_COLUMNS}
    return {"n": len(rows),
            "human_vs_coder": {c: cohen_kappa(human[c], coder[c]) for c in CODE_COLUMNS},
            "human_vs_truth": {c: cohen_kappa(human[c], true[c]) for c in CODE_COLUMNS},
            "kappa": "unweighted Cohen's kappa per code"}


def main(argv=None) -> None:
    if make_sample():
        print(f"wrote blank hand-coding sample: {SAMPLE.relative_to(ROOT)}")
    rep = kappa_report()
    if rep is None:
        print("ANL-04 kappa: awaiting human coding")
    else:
        write_json(RESULTS / "kappa.json", {"requirement": "ANL-04", **rep})


if __name__ == "__main__":
    main()
