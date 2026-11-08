"""ANL-01: cleaning dedupes, normalizes casing, keeps missing policy as NA, writes data/clean/, logs counts.

These tests may read the hidden truth (tests are allowed to) to check cleaning against the planted mess.
"""
import json

import pytest

from datautil import RAW, generated_dir, load_dir
from src.analysis import clean as clean_mod
from src.analysis.common import CLEAN, LEVELS, RESULTS, _jsonable, read_clean, read_raw


@pytest.fixture(scope="module", params=["committed", "seed7"])
def cleaned(request, tmp_path_factory):
    raw = RAW if request.param == "committed" else generated_dir(7)
    out = tmp_path_factory.mktemp(f"clean-{request.param}")
    log = clean_mod.clean(raw, out)
    return raw, out, log, load_dir(raw)["ground_truth"]


@pytest.mark.req("ANL-01")
def test_duplicates_removed_match_planted_duplicates(cleaned):
    """Exactly the planted duplicate course rows are dropped; no other table loses rows, and no exact
    duplicates remain."""
    raw, out, log, gt = cleaned
    assert log["tables"]["courses"]["duplicates_removed"] == len(gt["mess"]["duplicate_rows"])
    assert log["tables"]["institutions"]["duplicates_removed"] == 0
    assert log["tables"]["statements"]["duplicates_removed"] == 0
    df = read_clean("courses", out)
    assert not df.duplicated(subset=["course_id", "term"]).any()


@pytest.mark.req("ANL-01")
def test_level_is_normalized(cleaned):
    """Every cleaned level is one of the four lowercase levels, and the log counts how many were changed
    (equal to the planted re-cased rows, minus any whose duplicate copy was dropped)."""
    raw, out, log, gt = cleaned
    df = read_clean("courses", out)
    assert set(df["level"]) == set(LEVELS)
    changed = log["tables"]["courses"]["level_values_normalized"]
    assert 0 < changed <= len(gt["mess"]["recased_level"])
    assert changed == sum(1 for l in read_raw("courses", raw).drop_duplicates()["level"] if l != l.lower())


@pytest.mark.req("ANL-01")
def test_missing_policy_kept_as_na_not_imputed(cleaned):
    """Rows with a missing policy are kept, read back as NA, and their count equals the planted missing
    rows; every other policy is an integer 0-4 equal to the raw value."""
    raw, out, log, gt = cleaned
    df = read_clean("courses", out)
    assert int(df["policy"].isna().sum()) == len(gt["mess"]["missing_policy"]) == log["tables"]["courses"]["policy_missing"]
    known = df["policy"].dropna()
    assert known.between(0, 4).all()
    rawdf = read_raw("courses", raw).drop_duplicates().reset_index(drop=True)
    assert list(rawdf["policy"]) == ["" if na else str(int(v)) for v, na in zip(df["policy"].fillna(-1), df["policy"].isna())]


@pytest.mark.req("ANL-01")
def test_log_counts_match_files(cleaned):
    """The logged rows_before/rows_after equal the raw and cleaned file lengths for every table."""
    raw, out, log, gt = cleaned
    for name, entry in log["tables"].items():
        assert entry["rows_before"] == len(read_raw(name, raw))
        assert entry["rows_after"] == len(read_raw(name, out))


@pytest.mark.req("ANL-01")
def test_committed_clean_data_and_log_are_current(tmp_path):
    """data/clean/ and results/clean_log.json are exactly what cleaning the committed data/raw/ gives now."""
    log = clean_mod.clean(RAW, tmp_path)
    for name in clean_mod.TABLES:
        assert (CLEAN / f"{name}.csv").read_bytes() == (tmp_path / f"{name}.csv").read_bytes(), name
    saved = json.loads((RESULTS / "clean_log.json").read_text(encoding="utf-8"))
    assert saved["tables"] == _jsonable(log["tables"])  # same numbers, rounded as the writer rounds


@pytest.mark.req("ANL-01")
def test_term_index_is_zero_based_position_in_terms(cleaned):
    """Behavioural check (fault F05): term_index is each term's position in TERMS, starting at 0 for F23 and
    ending at 6 for F26, so one regression unit is exactly one term from the start of the panel."""
    from src.analysis.common import TERMS
    _, out, _, _ = cleaned
    df = read_clean("courses", out)
    assert (df["term_index"] == df["term"].map({t: i for i, t in enumerate(TERMS)})).all()
    assert df.loc[df["term"] == "F23", "term_index"].unique().tolist() == [0]
    assert df["term_index"].min() == 0 and df["term_index"].max() == len(TERMS) - 1
