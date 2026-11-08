"""Shared paths and deterministic writers for the analysis (P2). Never touches the hidden truth file."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
RESULTS = ROOT / "results"
TERMS = ["F23", "S24", "F24", "S25", "F25", "S26", "F26"]
LEVELS = ["intro", "intermediate", "upper", "graduate"]
SYNTHETIC_NOTE = "SYNTHETIC DATA: every institution, course and statement is invented."


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):  # numpy scalars
        obj = obj.item()
    if isinstance(obj, float):
        return None if math.isnan(obj) else round(obj, 6)
    return obj


def write_json(path: Path, obj: dict) -> None:
    """Write a results file: sorted keys, rounded floats, a synthetic-data note, no timestamps."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"synthetic": True, "note": SYNTHETIC_NOTE, **obj}
    path.write_text(json.dumps(_jsonable(body), sort_keys=True, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def read_raw(name: str, raw_dir: Path = RAW) -> pd.DataFrame:
    """Read a raw CSV as text, keeping blanks as empty strings (no automatic NA guessing)."""
    return pd.read_csv(Path(raw_dir) / f"{name}.csv", dtype=str, keep_default_na=False)


def read_clean(name: str, clean_dir: Path = CLEAN) -> pd.DataFrame:
    """Read a cleaned CSV with proper types: policy as nullable Int64, booleans as bool/boolean."""
    df = pd.read_csv(Path(clean_dir) / f"{name}.csv", dtype=str, keep_default_na=False)
    if name == "courses":
        df["policy"] = pd.array([int(x) if x != "" else pd.NA for x in df["policy"]], dtype="Int64")
        df["is_se"] = df["is_se"] == "true"
        df["term_index"] = df["term_index"].astype(int)
    if name == "institutions":
        df["cs_enrollment"] = df["cs_enrollment"].astype(int)
    return df
