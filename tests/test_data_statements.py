"""P1 statement tests: shape (DATA-03), R1 stance effect (DATA-09), label correlations (DATA-11)."""
import statistics
from collections import Counter

import pytest

from datautil import gen_module, load

SEEDS = [2026, 1, 2, 3, 4]


def _labelled(seed):
    t = load(seed)
    labels = t["ground_truth"]["statements"]
    carnegie = {r["inst_id"]: r["carnegie"] for r in t["institutions"]}
    return t, [(s, labels[s["stmt_id"]], carnegie[s["inst_id"]]) for s in t["statements"]]


def _sentences(text):
    assert text.endswith(".")
    return text.count(". ") + 1


@pytest.mark.req("DATA-03")
@pytest.mark.parametrize("seed", SEEDS)
def test_statement_counts_and_fields(seed):
    """statements.csv has ~350 rows (within +-10%), 0-4 per institution, only the allowed pub_types,
    pub_dates from 2023-01 to 2026-10 as YYYY-MM, unique stmt_ids, and 2-5 sentences of text."""
    t = load(seed)
    rows = t["statements"]
    assert list(rows[0].keys()) == ["stmt_id", "inst_id", "pub_type", "pub_date", "text"]
    assert 315 <= len(rows) <= 385
    per_inst = Counter(r["inst_id"] for r in rows)
    assert max(per_inst.values()) <= 4
    assert len(per_inst) < len(t["institutions"]), "some institutions should have 0 statements"
    assert {r["pub_type"] for r in rows} == {"policy_page", "news", "strategic_plan",
                                             "syllabus_template", "faq"}
    assert all("2023-01" <= r["pub_date"] <= "2026-10" and len(r["pub_date"]) == 7 for r in rows)
    assert len({r["stmt_id"] for r in rows}) == len(rows)
    assert all(2 <= _sentences(r["text"]) <= 5 for r in rows)


@pytest.mark.req("DATA-03")
def test_text_is_assembled_from_phrase_banks_keyed_to_labels():
    """Each statement opens with a sentence from its stance's bank, and contains a sentence from a
    label's bank exactly when that hidden label is true."""
    mod = gen_module()
    _, rows = _labelled(2026)
    for s, lab, _ in rows:
        assert any(s["text"].startswith(x) for x in mod.STANCE_SENTENCES[lab["stance"]])
        for label, bank in mod.LABEL_SENTENCES.items():
            assert any(x in s["text"] for x in bank) == lab[label], (s["stmt_id"], label)


@pytest.mark.req("DATA-03")
def test_hidden_labels_are_not_in_statements_csv():
    """statements.csv carries no label columns; the labels exist only in ground_truth.json."""
    t = load(2026)
    assert not {"stance", "mentions_integrity", "mentions_collaboration", "mentions_careers"} & set(t["statements"][0])
    assert set(t["ground_truth"]["statements"]) == {s["stmt_id"] for s in t["statements"]}


@pytest.mark.req("DATA-09")
@pytest.mark.parametrize("seed", SEEDS)
def test_r1_statements_are_more_positive(seed):
    """Mean hidden statement stance at R1 institutions exceeds the non-R1 mean by at least 0.25,
    and the planted parameter puts R1 above every other Carnegie class."""
    _, rows = _labelled(seed)
    r1 = [lab["stance"] for _, lab, c in rows if c == "R1"]
    other = [lab["stance"] for _, lab, c in rows if c != "R1"]
    assert statistics.mean(r1) - statistics.mean(other) >= 0.25
    eff = gen_module().STANCE_MODEL["carnegie_effect"]
    assert all(eff["R1"] > v for k, v in eff.items() if k != "R1")


def _rate(rows, label, pred):
    sel = [lab[label] for _, lab, c in rows if pred(lab, c)]
    return sum(sel) / len(sel)


@pytest.mark.req("DATA-11")
@pytest.mark.parametrize("seed", SEEDS)
def test_labels_correlate_with_stance_as_documented(seed):
    """Integrity is mentioned more by negative-stance statements than positive ones; collaboration
    and careers are mentioned more by positive ones; careers more at R1s."""
    _, rows = _labelled(seed)
    neg = lambda lab, c: lab["stance"] < 0
    pos = lambda lab, c: lab["stance"] > 0
    assert _rate(rows, "mentions_integrity", neg) > _rate(rows, "mentions_integrity", pos)
    assert _rate(rows, "mentions_collaboration", pos) > _rate(rows, "mentions_collaboration", neg)
    assert _rate(rows, "mentions_careers", pos) > _rate(rows, "mentions_careers", neg)
    assert (_rate(rows, "mentions_careers", lambda lab, c: c == "R1")
            > _rate(rows, "mentions_careers", lambda lab, c: c != "R1"))


@pytest.mark.req("DATA-11")
@pytest.mark.parametrize("seed", SEEDS)
def test_stance_tracks_institution_policy_effect_outside_rhetoric_gap(seed):
    """For institutions without a rhetoric gap, statement stance rises with the institution's hidden
    policy effect (correlation > 0.3), the coupling that makes stance and courses agree."""
    t, rows = _labelled(seed)
    insts = t["ground_truth"]["institutions"]
    pairs = [(insts[s["inst_id"]]["inst_effect"], lab["stance"]) for s, lab, _ in rows
             if insts[s["inst_id"]]["rhetoric_gap"] is None]
    assert statistics.correlation(*zip(*pairs)) > 0.3
