"""ANL-01: clean the raw synthetic data into data/clean/ and log what changed.

- Exact duplicate rows are dropped (first occurrence kept).
- `level` is normalized to lowercase (stripped).
- A missing policy stays missing (written blank, read back as NA). Nothing is imputed.
- `term_index` (0 = F23 .. 6 = F26) is added to courses for modelling.
"""
from __future__ import annotations

import sys
from pathlib import Path

from src.analysis.common import CLEAN, RAW, RESULTS, TERMS, read_raw, write_csv, write_json

TABLES = ["institutions", "statements", "courses"]


def clean(raw_dir: Path = RAW, out_dir: Path = CLEAN) -> dict:
    log = {"tables": {}}
    for name in TABLES:
        df = read_raw(name, raw_dir)
        before = len(df)
        df = df.drop_duplicates(keep="first").reset_index(drop=True)
        entry = {"rows_before": before, "rows_after": len(df), "duplicates_removed": before - len(df)}
        if name == "courses":
            raw_levels = df["level"]
            df["level"] = raw_levels.str.strip().str.lower()
            entry["level_values_before"] = dict(sorted(raw_levels.value_counts().items()))
            entry["level_values_normalized"] = int((raw_levels != df["level"]).sum())
            entry["policy_missing"] = int((df["policy"] == "").sum())
            entry["policy_missing_share"] = entry["policy_missing"] / len(df)
            df["term_index"] = df["term"].map(TERMS.index)
        write_csv(Path(out_dir) / f"{name}.csv", df)
        log["tables"][name] = entry
    return log


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    raw_dir, out_dir = (Path(argv[0]), Path(argv[1])) if len(argv) == 2 else (RAW, CLEAN)
    log = clean(raw_dir, out_dir)
    write_json(RESULTS / "clean_log.json", {"requirement": "ANL-01", **log})


if __name__ == "__main__":
    main()
