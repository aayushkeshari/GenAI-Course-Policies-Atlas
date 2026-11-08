"""P1 tests for hidden truth isolation (DATA-05), realistic mess (DATA-12), and the rhetoric gap (DATA-17)."""
import statistics
from collections import Counter
from pathlib import Path

import pytest

from datautil import ROOT, gen_module, load

SEEDS = [2026, 1, 2]
ANALYSIS = ROOT / "src" / "analysis"


def files_mentioning_ground_truth(root: Path) -> list[str]:
    """Every file under root (any type) whose text mentions ground_truth, case-insensitively."""
    hits = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            text = p.read_bytes().decode("utf-8", errors="replace").casefold()
            if "ground_truth" in text.replace("ground-truth", "ground_truth").replace("groundtruth", "ground_truth"):
                hits.append(str(p.relative_to(root)))
    return hits


@pytest.mark.req("DATA-05")
def test_analysis_code_never_references_ground_truth():
    """src/analysis/ exists, and no file in it mentions ground_truth, except the package docstring that
    states the rule itself."""
    assert ANALYSIS.is_dir()
    hits = files_mentioning_ground_truth(ANALYSIS)
    doc = (ANALYSIS / "__init__.py").read_text(encoding="utf-8")
    allowed = ["__init__.py"] if doc.count("ground_truth") == 1 and "must never read" in doc.lower() else []
    assert [h for h in hits if h not in allowed] == []


@pytest.mark.req("DATA-05")
def test_ground_truth_grep_catches_violations(tmp_path):
    """The DATA-05 grep catches the spellings a violation would use (path string, variable, hyphenated)."""
    for i, line in enumerate(['open("data/raw/ground_truth.json")', "GROUND_TRUTH = 1", "x = 'ground-truth'"]):
        (tmp_path / f"m{i}.py").write_text(line)
    (tmp_path / "ok.py").write_text("import csv\n")
    assert files_mentioning_ground_truth(tmp_path) == ["m0.py", "m1.py", "m2.py"]


@pytest.mark.req("DATA-05")
def test_hidden_values_only_in_ground_truth():
    """The public CSVs have no hidden columns (stance, labels, effects, rhetoric gap), while
    ground_truth.json holds them, marks itself synthetic, and records the planted effects."""
    t = load(2026)
    hidden = {"stance", "mentions_integrity", "mentions_collaboration", "mentions_careers",
              "inst_effect", "stance_latent", "rhetoric_gap", "latent_score", "course_effect"}
    for name in ("institutions", "statements", "courses"):
        assert not hidden & set(t[name][0]), name
    gt = t["ground_truth"]
    assert gt["synthetic"] is True and gt["seed"] == 2026
    assert set(gt["planted_effects"]) >= {"DATA-06", "DATA-07", "DATA-08", "DATA-09", "DATA-10",
                                          "DATA-11", "DATA-15", "DATA-16", "DATA-17"}
    assert gt["parameters"]["policy_model"]["control_effect"] == {"public": 0.0, "private": 0.0}


@pytest.mark.req("DATA-05")
def test_ground_truth_records_exact_effect_parameters():
    """ground_truth.json records the exact parameters the generator used (HUMAN: P2 tests recovery
    against known values), matching the generator's constants."""
    mod, params = gen_module(), load(2026)["ground_truth"]["parameters"]
    assert params["policy_model"] == mod.POLICY_MODEL
    assert params["stance_model"] == mod.STANCE_MODEL
    assert params["label_model"] == mod.LABEL_MODEL
    assert params["use_model"] == mod.USE_MODEL


# --- DATA-12 -------------------------------------------------------------------------------------
def _distinct(rows):
    seen, out = set(), []
    for r in rows:
        k = tuple(r.values())
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


@pytest.mark.req("DATA-12")
@pytest.mark.parametrize("seed", SEEDS)
def test_about_8_percent_of_policies_missing_with_derived_fields_blank(seed):
    """7-9% of distinct course rows have a blank policy. In those rows disclosure_required, tools_named and
    allowed_uses are blank too, assessment_adaptation is kept, and ground_truth.json lists exactly them."""
    t = load(seed)
    rows = _distinct(t["courses"])
    missing = [r for r in rows if r["policy"] == ""]
    assert 0.07 <= len(missing) / len(rows) <= 0.09
    for r in missing:
        assert r["disclosure_required"] == r["tools_named"] == r["allowed_uses"] == ""
        assert r["assessment_adaptation"] != ""
    recorded = {(m["course_id"], m["term"]) for m in t["ground_truth"]["mess"]["missing_policy"]}
    assert {(r["course_id"], r["term"]) for r in missing} == recorded


@pytest.mark.req("DATA-12")
@pytest.mark.parametrize("seed", SEEDS)
def test_missingness_is_unrelated_to_true_policy(seed):
    """Missing at random: the mean true policy of the rows that lost it is within 0.3 of the overall mean."""
    gt = load(seed)["ground_truth"]
    true = [r["policy"] for r in gt["course_rows"]]
    lost = [m["policy"] for m in gt["mess"]["missing_policy"]]
    assert abs(statistics.mean(lost) - statistics.mean(true)) < 0.3


@pytest.mark.req("DATA-12")
@pytest.mark.parametrize("seed", SEEDS)
def test_level_casing_is_inconsistent(seed):
    """`level` appears in more than one casing (e.g. intro / Intro / INTRO), but every value lowercases to
    one of the four levels."""
    levels = Counter(r["level"] for r in load(seed)["courses"])
    assert {l.lower() for l in levels} == {"intro", "intermediate", "upper", "graduate"}
    assert len(levels) > 4
    assert sum(n for l, n in levels.items() if l != l.lower()) / sum(levels.values()) > 0.05


@pytest.mark.req("DATA-12")
@pytest.mark.parametrize("seed", SEEDS)
def test_about_1_percent_duplicate_course_rows(seed):
    """0.5-1.5% of courses.csv rows are exact duplicates of another row; statements and institutions have none."""
    t = load(seed)
    rows = t["courses"]
    dups = len(rows) - len(_distinct(rows))
    assert 0.005 <= dups / len(rows) <= 0.015
    assert dups == len(t["ground_truth"]["mess"]["duplicate_rows"])
    for name in ("statements", "institutions"):
        assert len(_distinct(t[name])) == len(t[name])


@pytest.mark.req("DATA-12")
@pytest.mark.parametrize("seed", SEEDS)
def test_some_statements_mention_both_integrity_and_collaboration(seed):
    """At least 5% of statements carry both mentions_integrity and mentions_collaboration, so text coding
    has to handle mixed messages."""
    labels = load(seed)["ground_truth"]["statements"].values()
    both = [l for l in labels if l["mentions_integrity"] and l["mentions_collaboration"]]
    assert len(both) / len(labels) >= 0.05


# --- DATA-17 -------------------------------------------------------------------------------------
@pytest.mark.req("DATA-17")
@pytest.mark.parametrize("seed", SEEDS)
def test_fifteen_percent_flagged_in_ground_truth_only(seed):
    """Exactly 22 of 150 institutions (15%) carry a rhetoric_gap flag, split evenly between the two kinds,
    and institutions.csv has no flag column."""
    t = load(seed)
    kinds = Counter(h["rhetoric_gap"] for h in t["ground_truth"]["institutions"].values() if h["rhetoric_gap"])
    assert kinds == {"enthusiastic_rhetoric_restrictive_courses": 11, "cautious_rhetoric_permissive_courses": 11}
    assert "rhetoric_gap" not in t["institutions"][0]


@pytest.mark.req("DATA-17")
@pytest.mark.parametrize("seed", SEEDS)
def test_rhetoric_gap_is_a_real_mismatch_in_the_data(seed):
    """Enthusiastic-rhetoric institutions have positive mean statement stance but course policy at least 0.5
    below the overall mean; cautious-rhetoric institutions show the reverse."""
    t = load(seed)
    gt = t["ground_truth"]
    kind = {i: h["rhetoric_gap"] for i, h in gt["institutions"].items()}
    pol = [(r["inst_id"], int(r["policy"])) for r in _distinct(t["courses"]) if r["policy"] != ""]
    overall = statistics.mean(p for _, p in pol)
    for k, sign in [("enthusiastic_rhetoric_restrictive_courses", 1), ("cautious_rhetoric_permissive_courses", -1)]:
        stance = [gt["statements"][s["stmt_id"]]["stance"] for s in t["statements"] if kind[s["inst_id"]] == k]
        course = [p for i, p in pol if kind[i] == k]
        assert sign * statistics.mean(stance) > 0.5
        assert sign * (overall - statistics.mean(course)) >= 0.5
