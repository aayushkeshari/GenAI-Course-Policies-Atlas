"""The only reader of the hidden truth file (besides tests). Access is always by split."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRUTH_FILE = ROOT / "data" / "raw" / "ground_truth.json"
LABEL_KEYS = ["stance", "mentions_integrity", "mentions_collaboration", "mentions_careers"]


def split_of(inst_id: str) -> str:
    """Public rule from docs/data-dictionary.md: odd inst_id number -> held-out, even -> dev."""
    return "heldout" if int(inst_id[1:]) % 2 else "dev"


def load_truth(split: str, statements_inst: dict[str, str], path: Path = TRUTH_FILE) -> dict[str, dict]:
    """Labels for the statements in one split only. statements_inst maps stmt_id -> inst_id (public data),
    so the split is decided by the public rule, never by fields in the truth file."""
    if split not in ("dev", "heldout"):
        raise ValueError(split)
    wanted = {sid for sid, iid in statements_inst.items() if split_of(iid) == split}
    allstmts = json.loads(Path(path).read_text(encoding="utf-8"))["statements"]
    return {sid: {k: allstmts[sid][k] for k in LABEL_KEYS} for sid in sorted(wanted)}


def load_statement_meta(stmt_ids: list[str], path: Path = TRUTH_FILE) -> dict[str, dict]:
    """Reporting metadata (split, reserved_phrasings, hard_cases) for the given statements. Not labels."""
    allstmts = json.loads(Path(path).read_text(encoding="utf-8"))["statements"]
    return {sid: {k: allstmts[sid][k] for k in ("split", "reserved_phrasings", "hard_cases")} for sid in stmt_ids}
