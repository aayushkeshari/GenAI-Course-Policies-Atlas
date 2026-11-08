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


def _texts(bank):
    return [e["text"] for e in bank]


@pytest.mark.req("DATA-03")
@pytest.mark.parametrize("seed", [2026, 1])
def test_text_is_assembled_from_phrase_banks_keyed_to_labels(seed):
    """Each statement contains exactly one stance sentence, taken from its own stance's bank (at any
    position), and contains a sentence from a label's bank exactly when that hidden label is true."""
    mod = gen_module()
    _, rows = _labelled(seed)
    for s, lab, _ in rows:
        found = {k for k, bank in mod.STANCE_SENTENCES.items() for x in _texts(bank) if x in s["text"]}
        assert found == {lab["stance"]}, (s["stmt_id"], found)
        assert sum(x in s["text"] for bank in mod.STANCE_SENTENCES.values() for x in _texts(bank)) == 1
        for label, bank in mod.LABEL_SENTENCES.items():
            assert any(x in s["text"] for x in _texts(bank)) == lab[label], (s["stmt_id"], label)


@pytest.mark.req("DATA-03")
def test_phrase_banks_have_variety():
    """HUMAN: every stance level and every label has at least 8 phrasings; all phrasings across all banks
    are distinct; and the stance sentence is not always first (position carries no signal)."""
    mod = gen_module()
    banks = list(mod.STANCE_SENTENCES.values()) + list(mod.LABEL_SENTENCES.values())
    assert all(len(b) >= 8 for b in banks)
    every = [x for b in banks + [mod.NEUTRAL_SENTENCES] for x in _texts(b)]
    assert len(every) == len(set(every))
    _, rows = _labelled(2026)
    first = sum(any(s["text"].startswith(x) for x in _texts(mod.STANCE_SENTENCES[lab["stance"]])) for s, lab, _ in rows)
    assert first < 0.7 * len(rows)


@pytest.mark.req("DATA-03")
def test_hard_cases_are_in_banks_and_in_the_data():
    """HUMAN: the banks hold at least 3 negations and 3 hedges among stance sentences, and at least 4
    AI-mentions-without-stance and 4 keyword traps among neutral sentences; each kind appears in at least
    10 statements of the seed-2026 data. Keyword traps reuse a label keyword (integrity, collaboration)
    in an unrelated sense, and at least one statement with each trap has that label false."""
    mod = gen_module()
    stance_tags = [e["tag"] for b in mod.STANCE_SENTENCES.values() for e in b]
    neutral_tags = [e["tag"] for e in mod.NEUTRAL_SENTENCES]
    assert stance_tags.count("negation") >= 3 and stance_tags.count("hedge") >= 3
    assert neutral_tags.count("ai_no_stance") >= 4 and neutral_tags.count("keyword_trap") >= 4
    _, rows = _labelled(2026)
    for tag in mod.HARD_CASE_TAGS:
        assert sum(tag in lab["hard_cases"] for _, lab, _ in rows) >= 10, tag
    for word, label in [("integrity", "mentions_integrity"), ("collaborat", "mentions_collaboration")]:
        traps = [e["text"] for e in mod.NEUTRAL_SENTENCES if e["tag"] == "keyword_trap" and word in e["text"]]
        assert traps
        assert any(any(t in s["text"] for t in traps) and not lab[label] for s, lab, _ in rows), word


@pytest.mark.req("DATA-03")
@pytest.mark.parametrize("seed", [2026, 1, 2])
def test_reserved_phrasings_appear_only_in_held_out_half(seed):
    """HUMAN: the dev/held-out split follows the public rule (odd inst_id number -> held-out). No dev
    statement contains any reserved phrasing (checked on the text itself), over half of held-out statements
    contain at least one, and at least 80% of reserved phrasings occur somewhere in the held-out half, so
    ANL-03's held-out score measures generalization rather than memorization."""
    mod = gen_module()
    _, rows = _labelled(seed)
    banks = list(mod.STANCE_SENTENCES.values()) + list(mod.LABEL_SENTENCES.values()) + [mod.NEUTRAL_SENTENCES]
    reserved = [e["text"] for b in banks for e in b if e["heldout"]]
    for s, lab, _ in rows:
        assert lab["split"] == ("heldout" if int(s["inst_id"][1:]) % 2 else "dev")
    dev = [s["text"] for s, lab, _ in rows if lab["split"] == "dev"]
    held = [s["text"] for s, lab, _ in rows if lab["split"] == "heldout"]
    assert dev and held
    assert not [t for t in dev if any(r in t for r in reserved)]
    assert sum(any(r in t for r in reserved) for t in held) > 0.5 * len(held)
    seen = sum(any(r in t for t in held) for r in reserved)
    assert seen >= 0.8 * len(reserved)


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
