"""DATA-14: docs/data-dictionary.md documents every column and says the data is synthetic."""
import re

import pytest

from datautil import ROOT, load

DICT = ROOT / "docs" / "data-dictionary.md"


def section(text, heading):
    m = re.search(rf"^## {re.escape(heading)}.*?\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"no '## {heading}' section"
    return m.group(1)


@pytest.mark.req("DATA-14")
@pytest.mark.parametrize("table", ["institutions", "statements", "courses"])
def test_every_column_documented(table):
    """Each column of the CSV appears as a `column` row in the dictionary table for that file."""
    body = section(DICT.read_text(encoding="utf-8"), f"{table}.csv")
    for col in load(2026)[table][0]:
        assert re.search(rf"^\| `{col}` \|", body, re.M), f"{table}.{col} undocumented"


@pytest.mark.req("DATA-14")
def test_ground_truth_keys_documented():
    """Every top-level key of ground_truth.json is named in the dictionary's ground_truth.json section."""
    body = section(DICT.read_text(encoding="utf-8"), "ground_truth.json")
    for key in load(2026)["ground_truth"]:
        assert f"`{key}`" in body, key


@pytest.mark.req("DATA-14")
def test_states_data_is_synthetic():
    """The dictionary says, before any table, that all data is SYNTHETIC and that the real university names are
    attached to invented policies and statements (DATA-02 as changed 2026-11-10)."""
    text = DICT.read_text(encoding="utf-8")
    head = " ".join(text.split("|", 1)[0].replace(">", " ").split())
    assert "SYNTHETIC" in head
    assert "Real university names are attached to invented policies and statements" in head
    assert "Nothing here describes what these schools actually do" in head
