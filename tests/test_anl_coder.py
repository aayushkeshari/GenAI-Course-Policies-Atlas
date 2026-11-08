"""ANL-02 (codebook + transparent rule-based coder) and the ANL-03 leakage guards.

Leakage guards: the coder never opens the truth file, src/analysis never imports src/evaluation, the dev
report depends on dev labels only, and no wording reserved for the held-out half appears in the rules or
codebook.
"""
import ast
import json
import re
import shutil
import sys

import pytest

from datautil import RAW, load_dir
from src.analysis import code_text
from src.analysis.common import CLEAN, ROOT, read_clean
from src.evaluation import coder_eval, truth

CODEBOOK = ROOT / "docs" / "codebook.md"
CODER = ROOT / "src" / "analysis" / "code_text.py"


def statements():
    return read_clean("statements", CLEAN)


def dev_texts():
    s = statements()
    return [t for t, i in zip(s["text"], s["inst_id"]) if truth.split_of(i) == "dev"]


# --- ANL-02 ----------------------------------------------------------------------------------------
@pytest.mark.req("ANL-02")
def test_codebook_defines_every_code_with_include_exclude_and_examples():
    """docs/codebook.md has a stance table with rows -2..+2 and a theme table with the three mention codes,
    each with Include, Exclude and example columns, and states that the data is synthetic."""
    text = CODEBOOK.read_text(encoding="utf-8")
    assert "SYNTHETIC" in text
    for header in ["| Code | Meaning | Include | Exclude | Dev example |", "| Code | Include | Exclude | Dev example |"]:
        assert header in text
    for code in ["−2", "−1", "0", "+1", "+2"]:
        assert re.search(rf"^\| {re.escape(code)} \|", text, re.M), code
    for label in code_text.LABELS:
        assert f"| `{label}` |" in text


@pytest.mark.req("ANL-02")
def test_rule_table_in_codebook_matches_code():
    """The rule table between the rules:start/end markers is exactly code_text.rules_markdown()."""
    text = CODEBOOK.read_text(encoding="utf-8")
    block = text.split("<!-- rules:start -->\n", 1)[1].split("\n<!-- rules:end -->", 1)[0]
    assert block == code_text.rules_markdown()


@pytest.mark.req("ANL-02")
@pytest.mark.req("ANL-03")
@pytest.mark.parametrize("rule", code_text.ALL_RULES, ids=lambda r: r.id)
def test_every_rule_is_grounded_in_dev_text(rule):
    """Each rule's example occurs verbatim in a DEV statement, and the rule's pattern matches that example,
    so every rule was derived from dev data."""
    assert any(rule.example in t for t in dev_texts()), rule.id
    assert rule.regex.search(rule.example)


@pytest.mark.req("ANL-02")
def test_every_coded_value_traces_to_a_rule():
    """Each coded stance names the rule that set it (or S0-default), and that rule fires on the text with that
    value; each true label lists the rules that fired, each of which matches the text; false labels list none."""
    by_id = {r.id: r for r in code_text.ALL_RULES}
    coded = code_text.code_statements(statements())
    for (_, row), txt in zip(coded.iterrows(), statements()["text"]):
        if row["stance_rule"] == code_text.DEFAULT_STANCE_RULE:
            assert row["stance"] == 0 and not any(r.regex.search(txt) for r in code_text.STANCE_RULES)
        else:
            r = by_id[row["stance_rule"]]
            assert r.value == row["stance"] and r.regex.search(txt)
        for label in code_text.LABELS:
            ids = [x for x in row[f"{label}_rules"].split(";") if x]
            assert bool(ids) == row[label]
            assert all(by_id[i].code == label and by_id[i].regex.search(txt) for i in ids)


@pytest.mark.req("ANL-02")
def test_coder_uses_no_llm_or_network():
    """code_text.py imports only the standard library, pandas and src.analysis.common: no LLM SDK, no HTTP."""
    tree = ast.parse(CODER.read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods <= {"__future__", "re", "sys", "dataclasses", "pathlib", "pandas", "src.analysis.common"}, mods


@pytest.mark.req("ANL-02")
def test_negation_rules_precede_their_cue_words():
    """Hard cases from the codebook: negated cues are coded by the negation rule, not the bare cue."""
    cases = {"AI use is not prohibited; students may use these tools as long as they cite them.": 1,
             "The department neither endorses nor bans generative AI; course policies differ.": 0,
             "AI assistants are not permitted by default; any use needs an instructor's approval.": -1,
             "Course pages explain how to protect data integrity when submitting files.": 0}
    for text, stance in cases.items():
        assert code_text.code_statement(text)["stance"] == stance, text
    assert not code_text.code_statement("Course pages explain how to protect data integrity when submitting files.")["mentions_integrity"]
    assert not code_text.code_statement("This page was prepared in collaboration with the campus library.")["mentions_collaboration"]


@pytest.mark.req("ANL-02")
def test_committed_coded_statements_are_current(tmp_path):
    """data/clean/statements_coded.csv is exactly what the current coder produces."""
    shutil.copy(CLEAN / "statements.csv", tmp_path / "statements.csv")
    code_text.main([str(tmp_path)])
    assert (tmp_path / "statements_coded.csv").read_bytes() == (CLEAN / "statements_coded.csv").read_bytes()


# --- ANL-03 leakage guards -------------------------------------------------------------------------------
@pytest.mark.req("ANL-03")
def test_coder_never_opens_the_truth_file():
    """Running the coder over every statement opens no file whose name contains 'ground_truth'
    (checked with a Python audit hook on every open() call)."""
    opened, active = [], [True]

    def hook(event, args):
        if active[0] and event == "open":
            opened.append(str(args[0]))
    sys.addaudithook(hook)  # audit hooks cannot be removed; `active` switches this one off afterwards
    try:
        code_text.code_statements(statements())
    finally:
        active[0] = False
    assert not [p for p in opened if "ground_truth" in p]


@pytest.mark.req("ANL-03")
def test_analysis_package_never_imports_evaluation():
    """No module in src/analysis imports src.evaluation (the only package that reads the truth)."""
    for f in (ROOT / "src" / "analysis").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not [n for n in names if n.startswith("src.evaluation")], f.name


@pytest.mark.req("ANL-03")
def test_dev_truth_loader_returns_only_dev_statements():
    """load_truth('dev') returns exactly the statements whose institution is dev under the public rule."""
    s = statements()
    inst = dict(zip(s["stmt_id"], s["inst_id"]))
    dev = truth.load_truth("dev", inst)
    assert set(dev) == {sid for sid, i in inst.items() if truth.split_of(i) == "dev"}
    assert all(truth.split_of(inst[sid]) == "dev" for sid in dev)


@pytest.mark.req("ANL-03")
def test_dev_report_is_unchanged_when_held_out_labels_are_scrambled(tmp_path, monkeypatch):
    """With every held-out label in the truth file replaced by a wrong value, the dev report is identical:
    tuning output depends on dev labels only."""
    before = coder_eval.dev_report()
    gt = json.loads((RAW / "ground_truth.json").read_text(encoding="utf-8"))
    for sid, lab in gt["statements"].items():
        if lab["split"] == "heldout":
            lab.update({"stance": 2 - (lab["stance"] + 2), "mentions_integrity": not lab["mentions_integrity"],
                        "mentions_collaboration": not lab["mentions_collaboration"],
                        "mentions_careers": not lab["mentions_careers"]})
    scrambled = tmp_path / "ground_truth.json"
    scrambled.write_text(json.dumps(gt), encoding="utf-8")
    monkeypatch.setattr(truth, "TRUTH_FILE", scrambled)
    monkeypatch.setattr(truth.load_truth, "__defaults__", (scrambled,))
    assert coder_eval.dev_report() == before


def _grams(text, n=4):
    words = re.findall(r"[a-z0-9'-]+", text.lower())
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


@pytest.mark.req("ANL-03")
def test_no_held_out_only_wording_in_rules_or_codebook():
    """No 4-word sequence that occurs only in held-out-reserved phrasings (and in no dev-eligible phrasing)
    appears in code_text.py or docs/codebook.md. The rules were not written from held-out wording."""
    banks = load_dir(RAW)["ground_truth"]["parameters"]["phrase_banks"]
    entries = [e for b in banks["stance"].values() for e in b] + [e for b in banks["labels"].values() for e in b] + banks["neutral"]
    shared = set().union(*(_grams(e["text"]) for e in entries if not e["heldout"]))
    reserved_only = set().union(*(_grams(e["text"]) for e in entries if e["heldout"])) - shared
    assert reserved_only
    for f in [CODER, CODEBOOK]:
        hits = reserved_only & _grams(f.read_text(encoding="utf-8"))
        assert not hits, (f.name, sorted(hits)[:5])


@pytest.mark.req("ANL-02")
@pytest.mark.req("ANL-03")
def test_codebook_examples_are_dev_text():
    """Every quoted example in the codebook's stance and theme tables occurs verbatim in a DEV statement."""
    text = CODEBOOK.read_text(encoding="utf-8").split("## Rule table", 1)[0]
    examples = re.findall(r'\| "([^"|]+)" \|', text)
    assert len(examples) >= 8
    dev = dev_texts()
    missing = [e for e in examples if not any(e in t for t in dev)]
    assert not missing, missing
