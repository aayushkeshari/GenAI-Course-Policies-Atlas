"""ANL-13 recovery: how many DATA-17 rhetoric-gap institutions land in the analysis's top-decile gap list.

Reads the truth (allowed here). Precision = flagged among listed / listed; recall = flagged among listed /
flagged institutions that could be listed (they have statements). Writes results/rhetoric_recovery.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.analysis.common import RESULTS, write_json
from src.evaluation.truth import TRUTH_FILE

EXPECTED_DIRECTION = {"enthusiastic_rhetoric_restrictive_courses": "rhetoric more permissive than courses",
                      "cautious_rhetoric_permissive_courses": "courses more permissive than rhetoric"}


def recovery(results_dir: Path = RESULTS, truth_path: Path = TRUTH_FILE) -> dict:
    rh = json.loads((Path(results_dir) / "rhetoric.json").read_text(encoding="utf-8"))
    inst_truth = json.loads(Path(truth_path).read_text(encoding="utf-8"))["institutions"]
    eligible = {r["inst_id"] for r in rh["institutions"]}
    flagged = {i for i, h in inst_truth.items() if h["rhetoric_gap"] and i in eligible}
    listed = {r["inst_id"]: r for r in rh["top_decile"]}
    hits = sorted(set(listed) & flagged)
    precision = len(hits) / len(listed) if listed else 0.0
    recall = len(hits) / len(flagged) if flagged else 0.0
    return {"requirement": "ANL-13", "kind": "recovery (reads ground truth)",
            "n_listed": len(listed), "n_flagged_eligible": len(flagged),
            "n_flagged_total": sum(1 for h in inst_truth.values() if h["rhetoric_gap"]),
            "hits": hits, "precision": precision, "recall": recall,
            "base_rate": len(flagged) / len(eligible),
            "direction_correct": sum(listed[i]["direction"] == EXPECTED_DIRECTION[inst_truth[i]["rhetoric_gap"]] for i in hits)}


def main(argv=None) -> None:
    write_json(RESULTS / "rhetoric_recovery.json", recovery())


if __name__ == "__main__":
    main()
