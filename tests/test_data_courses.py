"""P1 course tests: schema (DATA-04) and the planted course effects (DATA-06/07/08/10/15/16).

Effect tests read the generated CSVs the way an analyst would: lower-case `level`, drop exact duplicate
rows, and drop rows with a missing policy. Several seeds are checked so an effect never depends on one
lucky draw. Each seed's data is deterministic, so these tests are not flaky.
"""
import math
import statistics

import pytest

from datautil import gen_module, load

SEEDS = [2026, 1, 2, 3, 4]
USES = ["explanation", "debugging", "code_generation", "testing", "writing"]


def clean(seed):
    seen, out = set(), []
    for r in load(seed)["courses"]:
        key = tuple(r.values())
        if key in seen or r["policy"] == "":
            seen.add(key)
            continue
        seen.add(key)
        out.append({**r, "level": r["level"].strip().lower(), "is_se": r["is_se"] == "true",
                    "policy": int(r["policy"]),
                    "uses": set(filter(None, r["allowed_uses"].split(";")))})
    return out


def mean_policy(rows, pred):
    sel = [r["policy"] for r in rows if pred(r)]
    assert sel, "empty group"
    return statistics.mean(sel)


@pytest.mark.req("DATA-04")
@pytest.mark.parametrize("seed", SEEDS)
def test_course_rows_and_columns(seed):
    """courses.csv has ~2,000 course-term rows (within +-10%), the DATA-04 columns in order, the 7 terms
    F23..F26 (fall + spring), and (course_id, term) unique once exact duplicates are removed."""
    rows = load(seed)["courses"]
    assert list(rows[0]) == ["course_id", "inst_id", "code", "title", "level", "is_se", "term", "policy",
                             "disclosure_required", "assessment_adaptation", "tools_named", "allowed_uses"]
    assert 1800 <= len(rows) <= 2200
    assert {r["term"] for r in rows} == {"F23", "S24", "F24", "S25", "F25", "S26", "F26"}
    distinct = {tuple(r.values()) for r in rows}
    assert len({(r[0], r[6]) for r in distinct}) == len(distinct)


@pytest.mark.req("DATA-04")
@pytest.mark.parametrize("seed", SEEDS)
def test_policy_dependent_fields_follow_policy(seed):
    """At policy 0, allowed_uses and tools_named are empty and disclosure is not required; at policy >= 1
    both list at least one value from their fixed vocabularies; policy 2 always requires disclosure."""
    tools = {"chat assistant", "IDE autocomplete", "agentic coding tool"}
    for r in clean(seed):
        if r["policy"] == 0:
            assert r["allowed_uses"] == r["tools_named"] == "" and r["disclosure_required"] == "false"
        else:
            assert r["uses"] and r["uses"] <= set(USES)
            assert set(r["tools_named"].split(";")) <= tools
        if r["policy"] == 2:
            assert r["disclosure_required"] == "true"


@pytest.mark.req("DATA-04")
def test_same_course_keeps_its_identity_across_terms():
    """A course_id has one inst_id, code, title, level (ignoring case) and is_se in every term."""
    ident = {}
    for r in clean(2026):
        key = (r["inst_id"], r["code"], r["title"], r["level"], r["is_se"])
        assert ident.setdefault(r["course_id"], key) == key


@pytest.mark.req("DATA-06")
@pytest.mark.parametrize("seed", SEEDS)
def test_intro_more_restrictive_than_upper(seed):
    """Mean policy of intro courses is at least 0.8 below upper-level courses (planted gap: 1.2 on the
    latent scale)."""
    rows = clean(seed)
    assert mean_policy(rows, lambda r: r["level"] == "upper") - mean_policy(rows, lambda r: r["level"] == "intro") >= 0.8


@pytest.mark.req("DATA-07")
@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("level", ["intermediate", "upper", "graduate"])
def test_se_more_permissive_than_non_se_at_same_level(seed, level):
    """At each level that has SE courses, SE courses have a higher mean policy than non-SE courses."""
    rows = clean(seed)
    se = mean_policy(rows, lambda r: r["level"] == level and r["is_se"])
    non = mean_policy(rows, lambda r: r["level"] == level and not r["is_se"])
    assert se > non


@pytest.mark.req("DATA-08")
@pytest.mark.parametrize("seed", SEEDS)
def test_permissiveness_rises_every_term(seed):
    """Mean policy strictly increases from each term to the next, F23 through F26."""
    rows = clean(seed)
    means = [mean_policy(rows, lambda r, t=t: r["term"] == t) for t in gen_module().TERMS]
    assert all(a < b for a, b in zip(means, means[1:])), means


@pytest.mark.req("DATA-10")
def test_control_effect_is_planted_as_exactly_zero():
    """The generator's policy model gives public and private exactly the same effect (0.0)."""
    assert gen_module().POLICY_MODEL["control_effect"] == {"public": 0.0, "private": 0.0}


@pytest.mark.req("DATA-10")
@pytest.mark.parametrize("seed", SEEDS)
def test_public_private_gap_is_small_next_to_real_effects(seed):
    """The observed public-private gap in mean policy is under 0.3 and under half of the smallest real
    planted contrast (SE vs non-SE upper-level courses). Some sampling gap remains; that is the point of
    the null: P2 must not call it an effect."""
    rows = clean(seed)
    inst = {r["inst_id"]: r["control"] for r in load(seed)["institutions"]}
    gap = abs(mean_policy(rows, lambda r: inst[r["inst_id"]] == "public")
              - mean_policy(rows, lambda r: inst[r["inst_id"]] == "private"))
    se_gap = (mean_policy(rows, lambda r: r["level"] == "upper" and r["is_se"])
              - mean_policy(rows, lambda r: r["level"] == "upper" and not r["is_se"]))
    assert gap < 0.3 and gap < se_gap / 2


def use_rate(rows, pred, use):
    sel = [use in r["uses"] for r in rows if r["policy"] >= 1 and pred(r)]
    return sum(sel) / len(sel)


GROUPS = {
    "intro": lambda r: r["level"] == "intro",
    "intermediate": lambda r: r["level"] == "intermediate" and not r["is_se"],
    "upper": lambda r: r["level"] == "upper" and not r["is_se"],
    "graduate": lambda r: r["level"] == "graduate" and not r["is_se"],
    "se": lambda r: r["is_se"],
}


@pytest.mark.req("DATA-15")
@pytest.mark.parametrize("seed", SEEDS)
def test_intro_allows_learning_uses_not_code_generation(seed):
    """Among intro courses that allow AI, over 70% allow explanation, over 50% allow debugging, and under
    20% allow code_generation."""
    rows, intro = clean(seed), GROUPS["intro"]
    assert use_rate(rows, intro, "explanation") > 0.7
    assert use_rate(rows, intro, "debugging") > 0.5
    assert use_rate(rows, intro, "code_generation") < 0.2


@pytest.mark.req("DATA-15")
@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("use", ["code_generation", "testing"])
def test_se_courses_most_likely_to_allow_generation_and_testing(seed, use):
    """SE courses allow code_generation and testing more often than every non-SE level group."""
    rows = clean(seed)
    se = use_rate(rows, GROUPS["se"], use)
    assert all(se > use_rate(rows, g, use) for name, g in GROUPS.items() if name != "se")


@pytest.mark.req("DATA-16")
@pytest.mark.parametrize("seed", SEEDS)
def test_restrictive_policies_use_exams_and_oral_defenses(seed):
    """In the data, the share of rows using in_class_exams or oral_defense falls strictly from restrictive
    (policy 0-1) to middle (2) to permissive (3-4) courses, and is over 50% at policy 0 and under 20% at
    policy 4. Single adjacent levels are not compared: the planted 3->4 step is only 0.05 and ~100 rows
    sit at policy 4, so sampling noise can flip it (seed 4 did). The planted weights are checked per level
    in test_planted_exam_share_decreases_at_every_policy_level."""
    rows = clean(seed)

    def share(levels):
        sel = [r["assessment_adaptation"] in ("in_class_exams", "oral_defense") for r in rows if r["policy"] in levels]
        return sum(sel) / len(sel)

    pooled = [share({0, 1}), share({2}), share({3, 4})]
    assert pooled[0] > pooled[1] > pooled[2], pooled
    assert share({0}) > 0.5 and share({4}) < 0.2


def cochran_armitage(rows, outcome):
    """Cochran-Armitage trend test of a binary outcome across policy 0..4 (scores 0..4).
    Returns (z, two-sided p). z < 0 means the outcome becomes less common as policy rises."""
    n = [sum(1 for r in rows if r["policy"] == p) for p in range(5)]
    x = [sum(1 for r in rows if r["policy"] == p and outcome(r)) for p in range(5)]
    big_n, pbar = sum(n), sum(x) / sum(n)
    t = sum(p * (x[p] - n[p] * pbar) for p in range(5))
    var = pbar * (1 - pbar) * (sum(n[p] * p * p for p in range(5)) - sum(n[p] * p for p in range(5)) ** 2 / big_n)
    z = t / math.sqrt(var)
    return z, math.erfc(abs(z) / math.sqrt(2))


def test_cochran_armitage_matches_known_values():
    """Helper check (no requirement): no trend gives z = 0, and a perfectly increasing outcome gives a
    large positive z with p < 1e-6."""
    flat = [{"policy": p, "y": k % 2 == 0} for p in range(5) for k in range(20)]
    assert cochran_armitage(flat, lambda r: r["y"])[0] == pytest.approx(0.0)
    rising = [{"policy": p, "y": k < 4 * p} for p in range(5) for k in range(20)]
    z, p = cochran_armitage(rising, lambda r: r["y"])
    assert z > 0 and p < 1e-6


@pytest.mark.req("DATA-16")
@pytest.mark.kind("property")
def test_assessment_trends_across_policy_are_significant_on_most_seeds():
    """HUMAN: a Cochran-Armitage trend test across policy 0..4 in the generated data is significant
    (p < 0.05) in the planted direction on at least 4 of 5 seeds, for both halves of DATA-16: in-class
    exams/oral defenses fall as policy rises, and process logs/AI critiques rise."""
    exam = lambda r: r["assessment_adaptation"] in ("in_class_exams", "oral_defense")
    logs = lambda r: r["assessment_adaptation"] in ("process_logs", "ai_critique")
    hits_exam = hits_logs = 0
    for seed in SEEDS:
        rows = clean(seed)
        z, p = cochran_armitage(rows, exam)
        hits_exam += z < 0 and p < 0.05
        z, p = cochran_armitage(rows, logs)
        hits_logs += z > 0 and p < 0.05
    assert hits_exam >= 4 and hits_logs >= 4, (hits_exam, hits_logs)


@pytest.mark.req("DATA-16")
def test_planted_exam_share_decreases_at_every_policy_level():
    """The generator's assessment weights give in_class_exams + oral_defense a strictly lower probability
    at each higher policy level, and process_logs + ai_critique a strictly higher one."""
    w = gen_module().ASSESSMENT_WEIGHTS
    exam = [w[p][1] + w[p][2] for p in range(5)]
    logs = [w[p][3] + w[p][4] for p in range(5)]
    assert all(a > b for a, b in zip(exam, exam[1:]))
    assert all(a < b for a, b in zip(logs, logs[1:]))


@pytest.mark.req("DATA-16")
@pytest.mark.parametrize("seed", SEEDS)
def test_process_logs_and_ai_critique_mostly_at_policy_2_plus(seed):
    """Over 75% of rows with process_logs or ai_critique have policy >= 2."""
    sel = [r["policy"] >= 2 for r in clean(seed) if r["assessment_adaptation"] in ("process_logs", "ai_critique")]
    assert sum(sel) / len(sel) > 0.75
