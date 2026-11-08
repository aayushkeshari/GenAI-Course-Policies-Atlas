"""Synthetic data generator for P1 (specs/P1-data.md, DATA-01..DATA-17).

Usage:  python src/data/generate.py --seed 2026 [--out data/raw]

ALL DATA PRODUCED HERE IS SYNTHETIC. Institution names are fictional, built from word lists.

Determinism (DATA-01): standard library only, one random.Random(seed) consumed in a fixed order,
CSV rows written in a fixed order with "\n" line endings, JSON written with sorted keys and
rounded floats, and nothing time-dependent in any output.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL_UNIVERSITIES = ROOT / "data" / "reference" / "real_universities.txt"
DEFAULT_OUT = ROOT / "data" / "raw"
GENERATOR_VERSION = 1

# ---------------------------------------------------------------------------------------------
# Institutions (DATA-02)
# ---------------------------------------------------------------------------------------------
N_INST = 150
P_PUBLIC = 0.55
CARNEGIE = ["R1", "R2", "Masters", "Baccalaureate"]
CARNEGIE_WEIGHTS = [0.25, 0.25, 0.30, 0.20]
ENROLL_MEDIAN = {"R1": 1800, "R2": 800, "Masters": 350, "Baccalaureate": 110}
ENROLL_LOG_SD = 0.35

# Town names are prefix + suffix ("Cedarbrook", "Heronvale"). Combinations known to be real
# college names were avoided when choosing the lists; the generator also rejects any name that
# appears in data/reference/real_universities.txt.
TOWN_PREFIX = ["Alder", "Amber", "Briar", "Cedar", "Copper", "Falcon", "Fern", "Glen", "Hazel",
               "Heron", "Iron", "Juniper", "Larch", "Laurel", "Maple", "Marsh", "Pine", "Quarry",
               "Raven", "Silver", "Thorn", "Willow", "Wren", "Bramble"]
TOWN_SUFFIX = ["brook", "crest", "dale", "field", "ford", "gate", "haven", "holm", "moor", "ridge",
               "vale", "wick", "mere", "stead", "shire"]
NAME_PATTERNS = {
    "public": ["University of {t}", "{t} State University", "{t} University"],
    "private": ["{t} University", "{t} College", "{t} Institute of Technology"],
    "Baccalaureate": ["{t} College"],
}

STATES = [  # (postal code, census region)
    ("CT", "Northeast"), ("ME", "Northeast"), ("MA", "Northeast"), ("NH", "Northeast"),
    ("RI", "Northeast"), ("VT", "Northeast"), ("NJ", "Northeast"), ("NY", "Northeast"),
    ("PA", "Northeast"),
    ("IL", "Midwest"), ("IN", "Midwest"), ("MI", "Midwest"), ("OH", "Midwest"), ("WI", "Midwest"),
    ("IA", "Midwest"), ("KS", "Midwest"), ("MN", "Midwest"), ("MO", "Midwest"), ("NE", "Midwest"),
    ("ND", "Midwest"), ("SD", "Midwest"),
    ("DE", "South"), ("FL", "South"), ("GA", "South"), ("MD", "South"), ("NC", "South"),
    ("SC", "South"), ("VA", "South"), ("WV", "South"), ("AL", "South"), ("KY", "South"),
    ("MS", "South"), ("TN", "South"), ("AR", "South"), ("LA", "South"), ("OK", "South"),
    ("TX", "South"),
    ("AZ", "West"), ("CO", "West"), ("ID", "West"), ("MT", "West"), ("NV", "West"), ("NM", "West"),
    ("UT", "West"), ("WY", "West"), ("AK", "West"), ("CA", "West"), ("HI", "West"), ("OR", "West"),
    ("WA", "West"),
]

INSTITUTION_COLUMNS = ["inst_id", "name", "state", "census_region", "control", "carnegie",
                       "cs_enrollment"]


def load_real_names(path: Path = REAL_UNIVERSITIES) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]


def make_institutions(rng: random.Random, real_names: list[str]) -> list[dict]:
    """Institution rows. Names are rejected if they match a real name (case-insensitive) or repeat."""
    real = {n.casefold() for n in real_names}
    used: set[str] = set()
    rows = []
    for i in range(1, N_INST + 1):
        control = "public" if rng.random() < P_PUBLIC else "private"
        carnegie = rng.choices(CARNEGIE, weights=CARNEGIE_WEIGHTS)[0]
        state, region = rng.choice(STATES)
        patterns = NAME_PATTERNS["Baccalaureate" if carnegie == "Baccalaureate" else control]
        while True:
            town = rng.choice(TOWN_PREFIX) + rng.choice(TOWN_SUFFIX)
            name = rng.choice(patterns).format(t=town)
            if name.casefold() not in real and name.casefold() not in used:
                break
        used.add(name.casefold())
        enrollment = round(ENROLL_MEDIAN[carnegie] * math.exp(rng.gauss(0, ENROLL_LOG_SD)))
        rows.append({"inst_id": f"I{i:03d}", "name": name, "state": state, "census_region": region,
                     "control": control, "carnegie": carnegie, "cs_enrollment": enrollment})
    return rows


# ---------------------------------------------------------------------------------------------
# Hidden institution parameters (DATA-09, DATA-10, DATA-11, DATA-17)
# ---------------------------------------------------------------------------------------------
# inst_effect shifts every course policy at the institution (see POLICY_MODEL). It does NOT depend
# on control: the public/private effect is a planted null (DATA-10).
SD_INST_EFFECT = 0.4
# Rhetoric gap (DATA-17): this share of institutions gets an official stance that contradicts its
# courses. Half "enthusiastic_rhetoric_restrictive_courses", half the reverse.
RHETORIC_GAP_SHARE = 0.15
RHETORIC_GAP = {
    "enthusiastic_rhetoric_restrictive_courses": {"inst_effect": -1.0, "stance_latent": 1.5},
    "cautious_rhetoric_permissive_courses": {"inst_effect": 1.0, "stance_latent": -1.5},
}
# Institution stance (continuous, before per-statement noise and rounding), DATA-09 / DATA-11:
#   stance_latent = intercept + carnegie_effect[carnegie] + policy_coupling * inst_effect + N(0, sd)
STANCE_MODEL = {
    "intercept": -0.1,
    "carnegie_effect": {"R1": 0.7, "R2": 0.25, "Masters": 0.0, "Baccalaureate": 0.0},
    "policy_coupling": 1.2,
    "inst_sd": 0.3,
    "statement_sd": 0.5,
}


def make_institution_hidden(rng: random.Random, institutions: list[dict]) -> dict:
    """Per-institution hidden values: inst_effect, stance_latent, rhetoric_gap (None or a kind)."""
    n_gap = round(RHETORIC_GAP_SHARE * len(institutions))
    gap_ids = rng.sample([r["inst_id"] for r in institutions], n_gap)
    kinds = sorted(RHETORIC_GAP)
    gap_kind = {iid: kinds[k % 2] for k, iid in enumerate(gap_ids)}
    hidden = {}
    for r in institutions:
        effect = rng.gauss(0, SD_INST_EFFECT)
        m = STANCE_MODEL
        stance = (m["intercept"] + m["carnegie_effect"][r["carnegie"]]
                  + m["policy_coupling"] * effect + rng.gauss(0, m["inst_sd"]))
        kind = gap_kind.get(r["inst_id"])
        if kind:
            effect = RHETORIC_GAP[kind]["inst_effect"]
            stance = RHETORIC_GAP[kind]["stance_latent"]
        hidden[r["inst_id"]] = {"inst_effect": effect, "stance_latent": stance, "rhetoric_gap": kind}
    return hidden


# ---------------------------------------------------------------------------------------------
# Statements (DATA-03, DATA-11)
# ---------------------------------------------------------------------------------------------
# How many institutions publish 0..4 statements. A fixed mix (shuffled across institutions) keeps the
# total at exactly 348 for every seed; independent draws strayed outside +-10% of ~350.
STATEMENT_COUNT_MIX = {0: 15, 1: 27, 2: 37, 3: 37, 4: 34}
PUB_TYPES = ["policy_page", "news", "strategic_plan", "syllabus_template", "faq"]
PUB_TYPE_WEIGHTS = [0.30, 0.20, 0.10, 0.20, 0.20]
FIRST_MONTH, LAST_MONTH = (2023, 1), (2026, 10)
# P(label = 1 | statement stance s, institution) — DATA-11, "correlated in documented ways":
#   integrity is mentioned more when stance is negative; collaboration and careers more when positive;
#   careers also more at R1s.
LABEL_MODEL = {
    "mentions_integrity": {"base": 0.55, "per_stance": -0.15},
    "mentions_collaboration": {"base": 0.35, "per_stance": 0.12},
    "mentions_careers": {"base": 0.25, "per_stance": 0.10, "r1_bonus": 0.15},
}
STANCE_SENTENCES = {
    -2: ["The department prohibits the use of generative AI tools on any graded work.",
         "Use of AI code generators or chatbots on coursework is not permitted in computer science courses.",
         "Students may not use generative AI systems to complete assignments, projects, or exams."],
    -1: ["The department urges caution with generative AI, and its use is limited to what an instructor explicitly allows.",
         "Generative AI tools raise serious concerns, and students should assume they are not allowed unless told otherwise.",
         "The faculty view AI assistants with caution and restrict them in most courses."],
    0: ["Each instructor sets the policy on generative AI tools for their own course.",
        "The department has not adopted a single rule on AI tools; course syllabi state what is allowed.",
        "Expectations for using AI assistants vary by course and are described in each syllabus."],
    1: ["The department supports thoughtful use of generative AI tools when students disclose how they used them.",
        "Students are welcome to use AI assistants in many courses, provided they follow the course guidelines.",
        "Generative AI can support learning, and the faculty are adopting it in a growing number of courses."],
    2: ["The department embraces generative AI as a core part of how computing is taught and practiced.",
        "We are integrating AI coding assistants throughout the curriculum and expect students to use them well.",
        "Generative AI is transforming software development, and our courses are built to put it to work."],
}
LABEL_SENTENCES = {
    "mentions_integrity": [
        "Submitting AI-generated work as one's own is a violation of the academic integrity policy.",
        "Undisclosed use of AI tools will be handled under the honor code.",
        "Students remain responsible for the originality of their work and must not misrepresent AI output as their own."],
    "mentions_collaboration": [
        "Students are encouraged to treat AI tools as collaborators and to discuss their use openly with peers and instructors.",
        "Faculty and students are working together to explore how AI assistants can support teamwork.",
        "Several courses pair students with AI assistants in collaborative problem-solving exercises."],
    "mentions_careers": [
        "Employers increasingly expect graduates to work effectively with AI-assisted development tools.",
        "Preparing students for an industry reshaped by AI is a priority for the department.",
        "Fluency with AI tools is becoming an important skill for careers in software."],
}
NEUTRAL_SENTENCES = [
    "This guidance applies to undergraduate and graduate courses offered by the department.",
    "The guidance will be reviewed at the end of each academic year.",
    "Questions about this guidance can be directed to the director of undergraduate studies.",
    "A faculty working group prepared this statement after consulting students and staff.",
    "Further details appear on the department's teaching resources page.",
    "Course staff will explain how this guidance applies during the first week of classes.",
]
STATEMENT_COLUMNS = ["stmt_id", "inst_id", "pub_type", "pub_date", "text"]


def _months():
    (y, m), out = FIRST_MONTH, []
    while (y, m) <= LAST_MONTH:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def label_probability(label: str, stance: int, carnegie: str) -> float:
    m = LABEL_MODEL[label]
    p = m["base"] + m["per_stance"] * stance + (m.get("r1_bonus", 0.0) if carnegie == "R1" else 0.0)
    return _clip(p, 0.02, 0.98)


def make_statements(rng: random.Random, institutions: list[dict], hidden: dict):
    """Statement rows plus their hidden labels {stmt_id: {stance, mentions_*}}."""
    months = _months()
    counts = [k for k, n_inst in sorted(STATEMENT_COUNT_MIX.items()) for _ in range(n_inst)]
    assert len(counts) == len(institutions)
    rng.shuffle(counts)
    drafts = []
    for inst, n in zip(institutions, counts):
        h = hidden[inst["inst_id"]]
        for _ in range(n):
            stance = int(_clip(round(h["stance_latent"] + rng.gauss(0, STANCE_MODEL["statement_sd"])), -2, 2))
            labels = {"stance": stance}
            for label in sorted(LABEL_MODEL):
                labels[label] = rng.random() < label_probability(label, stance, inst["carnegie"])
            body = [rng.choice(LABEL_SENTENCES[l]) for l in sorted(LABEL_SENTENCES) if labels[l]]
            n_sentences = max(rng.randint(2, 5), 1 + len(body))
            body += rng.sample(NEUTRAL_SENTENCES, n_sentences - 1 - len(body))
            rng.shuffle(body)
            text = " ".join([rng.choice(STANCE_SENTENCES[stance])] + body)
            drafts.append(({"inst_id": inst["inst_id"],
                            "pub_type": rng.choices(PUB_TYPES, weights=PUB_TYPE_WEIGHTS)[0],
                            "pub_date": rng.choice(months), "text": text}, labels))
    drafts.sort(key=lambda d: (d[0]["inst_id"], d[0]["pub_date"]))  # stable: ties keep draw order
    rows, labels_by_id = [], {}
    for k, (row, labels) in enumerate(drafts, 1):
        sid = f"S{k:04d}"
        rows.append({"stmt_id": sid, **row})
        labels_by_id[sid] = labels
    return rows, labels_by_id


# ---------------------------------------------------------------------------------------------
# Courses (DATA-04, DATA-06, DATA-07, DATA-08, DATA-10, DATA-15, DATA-16)
# ---------------------------------------------------------------------------------------------
TERMS = ["F23", "S24", "F24", "S25", "F25", "S26", "F26"]  # HUMAN: fall + spring, 7 terms
LEVELS = ["intro", "intermediate", "upper", "graduate"]
COURSES_PER_INST = (2, 4)            # uniform; the first course at every institution is intro
LATER_LEVEL_WEIGHTS = {"intermediate": 0.35, "upper": 0.40, "graduate": 0.25}  # no graduate at Baccalaureate
P_SE = 0.40                          # P(is_se) for non-intro courses
P_OFFERED = 0.635                    # P(a course runs in a given term); ~450 courses x 7 terms -> ~2,000 rows
LEVEL_CODE = {"intro": 1, "intermediate": 2, "upper": 4, "graduate": 6}
TITLES = {
    ("intro", False): ["Introduction to Programming", "Introduction to Computer Science",
                       "Programming Fundamentals", "Computational Thinking"],
    ("intermediate", False): ["Data Structures", "Computer Organization", "Discrete Structures", "Algorithms"],
    ("intermediate", True): ["Software Design", "Software Construction", "Object-Oriented Development"],
    ("upper", False): ["Operating Systems", "Database Systems", "Computer Networks", "Compilers",
                       "Machine Learning", "Computer Graphics"],
    ("upper", True): ["Software Engineering", "Software Engineering Capstone", "Software Testing",
                      "Agile Development", "DevOps and Continuous Delivery"],
    ("graduate", False): ["Advanced Algorithms", "Distributed Systems", "Theory of Computation",
                          "Advanced Machine Learning"],
    ("graduate", True): ["Advanced Software Engineering", "Software Architecture",
                         "Empirical Software Engineering"],
}

# Policy (0..4) = clip(nearest integer, halves up, of the latent score), where
#   score = intercept + level_effect[level] + se_effect * is_se + term_effect_per_step * term_index
#           + control_effect[control] + inst_effect + course_effect + row_noise
# term_index is 0 for F23 .. 6 for F26. control_effect is 0 for both: the planted null (DATA-10).
POLICY_MODEL = {
    "intercept": 1.0,
    "level_effect": {"intro": -0.7, "intermediate": 0.0, "upper": 0.5, "graduate": 0.6},
    "se_effect": 0.6,
    "term_effect_per_step": 0.2,
    "control_effect": {"public": 0.0, "private": 0.0},
    "course_effect_sd": 0.4,
    "row_noise_sd": 0.4,
}
DISCLOSURE_PROB = {0: 0.0, 1: 0.4, 2: 1.0, 3: 0.7, 4: 0.6}  # P(disclosure_required | policy)

USES = ["explanation", "debugging", "code_generation", "testing", "writing"]
# P(use allowed | policy >= 1) = clip(base[group][use] * (policy_scale_intercept + policy_scale_slope * policy)).
# group is "se" for any SE course, else the level. DATA-15: intro favours explanation/debugging and
# rarely code_generation; SE courses are the most likely to allow code_generation and testing.
USE_MODEL = {
    "base": {
        "intro":        {"explanation": 0.85, "debugging": 0.70, "code_generation": 0.10, "testing": 0.12, "writing": 0.30},
        "intermediate": {"explanation": 0.80, "debugging": 0.70, "code_generation": 0.30, "testing": 0.30, "writing": 0.35},
        "upper":        {"explanation": 0.75, "debugging": 0.70, "code_generation": 0.45, "testing": 0.40, "writing": 0.40},
        "graduate":     {"explanation": 0.70, "debugging": 0.65, "code_generation": 0.50, "testing": 0.40, "writing": 0.50},
        "se":           {"explanation": 0.75, "debugging": 0.75, "code_generation": 0.75, "testing": 0.75, "writing": 0.45},
    },
    "policy_scale_intercept": 0.7,
    "policy_scale_slope": 0.15,
    "fallback_use": "explanation",   # used when no use is drawn, so policy >= 1 always lists one
}
TOOLS = ["chat assistant", "IDE autocomplete", "agentic coding tool"]
# P(tool named | policy >= 1) = base + per_policy * policy (+ se_bonus for SE courses)
TOOL_MODEL = {
    "chat assistant": {"base": 0.80, "per_policy": 0.0},
    "IDE autocomplete": {"base": 0.25, "per_policy": 0.10},
    "agentic coding tool": {"base": 0.05, "per_policy": 0.12, "se_bonus": 0.15},
    "fallback_tool": "chat assistant",
}
ASSESSMENTS = ["none", "in_class_exams", "oral_defense", "process_logs", "ai_critique"]
# P(assessment_adaptation | policy), DATA-16: restrictive policies lean on in-class exams and oral
# defenses; process logs and AI critiques appear mostly at policy >= 2.
ASSESSMENT_WEIGHTS = {
    0: [0.25, 0.45, 0.25, 0.03, 0.02],
    1: [0.30, 0.35, 0.25, 0.05, 0.05],
    2: [0.35, 0.15, 0.12, 0.20, 0.18],
    3: [0.30, 0.08, 0.07, 0.27, 0.28],
    4: [0.25, 0.05, 0.05, 0.30, 0.35],
}
COURSE_COLUMNS = ["course_id", "inst_id", "code", "title", "level", "is_se", "term", "policy",
                  "disclosure_required", "assessment_adaptation", "tools_named", "allowed_uses"]


def _round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def make_catalog(rng: random.Random, institutions: list[dict]) -> list[dict]:
    """One entry per course (not per term): course_id, inst_id, code, title, level, is_se, course_effect."""
    catalog = []
    for inst in institutions:
        n = rng.randint(*COURSES_PER_INST)
        used_titles, used_codes = set(), set()
        for k in range(n):
            if k == 0:
                level = "intro"
            else:
                weights = dict(LATER_LEVEL_WEIGHTS)
                if inst["carnegie"] == "Baccalaureate":
                    weights.pop("graduate")
                level = rng.choices(list(weights), weights=list(weights.values()))[0]
            is_se = level != "intro" and rng.random() < P_SE
            title = rng.choice([t for t in TITLES[(level, is_se)] if t not in used_titles])
            while True:
                code = f"CS {LEVEL_CODE[level]}{rng.randrange(10, 100)}"
                if code not in used_codes:
                    break
            used_titles.add(title)
            used_codes.add(code)
            catalog.append({"inst_id": inst["inst_id"], "code": code, "title": title, "level": level,
                            "is_se": is_se, "course_effect": rng.gauss(0, POLICY_MODEL["course_effect_sd"])})
    for k, c in enumerate(catalog, 1):
        c["course_id"] = f"C{k:04d}"
    return catalog


def _policy_fields(rng: random.Random, policy: int, level: str, is_se: bool) -> dict:
    """disclosure_required, tools_named, allowed_uses for a known policy (all empty-ish at policy 0)."""
    disclosure = rng.random() < DISCLOSURE_PROB[policy]
    if policy == 0:
        return {"disclosure_required": disclosure, "tools_named": "", "allowed_uses": ""}
    base = USE_MODEL["base"]["se" if is_se else level]
    scale = USE_MODEL["policy_scale_intercept"] + USE_MODEL["policy_scale_slope"] * policy
    uses = [u for u in USES if rng.random() < _clip(base[u] * scale, 0.0, 0.98)]
    tools = []
    for tool in TOOLS:
        m = TOOL_MODEL[tool]
        p = m["base"] + m["per_policy"] * policy + (m.get("se_bonus", 0.0) if is_se else 0.0)
        if rng.random() < _clip(p, 0.0, 0.98):
            tools.append(tool)
    return {"disclosure_required": disclosure,
            "tools_named": ";".join(tools or [TOOL_MODEL["fallback_tool"]]),
            "allowed_uses": ";".join(uses or [USE_MODEL["fallback_use"]])}


def make_courses(rng: random.Random, institutions: list[dict], hidden: dict):
    """Clean course-term rows (before any mess) plus the hidden latent score for each row."""
    control = {r["inst_id"]: r["control"] for r in institutions}
    m = POLICY_MODEL
    rows, latent = [], []
    for c in make_catalog(rng, institutions):
        offered = [t for t in TERMS if rng.random() < P_OFFERED] or [rng.choice(TERMS)]
        for term in offered:
            score = (m["intercept"] + m["level_effect"][c["level"]] + m["se_effect"] * c["is_se"]
                     + m["term_effect_per_step"] * TERMS.index(term)
                     + m["control_effect"][control[c["inst_id"]]]
                     + hidden[c["inst_id"]]["inst_effect"] + c["course_effect"]
                     + rng.gauss(0, m["row_noise_sd"]))
            policy = int(_clip(_round_half_up(score), 0, 4))
            row = {k: c[k] for k in ["course_id", "inst_id", "code", "title", "level", "is_se"]}
            row.update({"term": term, "policy": policy})
            row.update(_policy_fields(rng, policy, c["level"], c["is_se"]))
            row["assessment_adaptation"] = rng.choices(ASSESSMENTS, weights=ASSESSMENT_WEIGHTS[policy])[0]
            rows.append(row)
            latent.append({"course_id": c["course_id"], "term": term, "latent_score": score,
                           "course_effect": c["course_effect"]})
    return rows, latent


# ---------------------------------------------------------------------------------------------
# Realistic mess (DATA-12). Applied to courses.csv only (HUMAN: duplicates in courses only).
# ---------------------------------------------------------------------------------------------
MESS = {
    "missing_policy_share": 0.08,   # MCAR: a uniform sample of rows, independent of every column
    # HUMAN: a missing policy blanks every policy-derived field; assessment_adaptation is kept.
    "missing_policy_blanks": ["policy", "disclosure_required", "tools_named", "allowed_uses"],
    "recased_level_share": 0.10,
    "recased_level_styles": ["title", "upper"],
    "duplicate_share": 0.01,        # exact copies of rows, inserted at random positions
}


def add_mess(rng: random.Random, rows: list[dict]):
    """Return (messy rows, record of every change). Input rows are not modified."""
    rows = [dict(r) for r in rows]
    n = len(rows)
    missing = sorted(rng.sample(range(n), round(MESS["missing_policy_share"] * n)))
    missing_record = []
    for i in missing:
        r = rows[i]
        missing_record.append({"course_id": r["course_id"], "term": r["term"],
                               **{k: r[k] for k in MESS["missing_policy_blanks"]}})
        for k in MESS["missing_policy_blanks"]:
            r[k] = None
    recased = sorted(rng.sample(range(n), round(MESS["recased_level_share"] * n)))
    recased_record = []
    for i in recased:
        style = rng.choice(MESS["recased_level_styles"])
        rows[i]["level"] = rows[i]["level"].title() if style == "title" else rows[i]["level"].upper()
        recased_record.append({"course_id": rows[i]["course_id"], "term": rows[i]["term"],
                               "level_shown": rows[i]["level"]})
    dup_sources = sorted(rng.sample(range(n), round(MESS["duplicate_share"] * n)))
    dup_record = []
    for i in dup_sources:
        dup_record.append({"course_id": rows[i]["course_id"], "term": rows[i]["term"]})
    copies = [dict(rows[i]) for i in dup_sources]
    for c in copies:
        rows.insert(rng.randrange(len(rows) + 1), c)
    return rows, {"missing_policy": missing_record, "recased_level": recased_record,
                  "duplicate_rows": dup_record}


# The planted truth, in words, for P2/P4. Parameter names refer to ground_truth["parameters"].
PLANTED_EFFECTS = {
    "DATA-06": "Intro courses are more restrictive than upper-level courses: policy_model.level_effect "
               "intro -0.7 vs upper +0.5 (difference 1.2 on the latent scale).",
    "DATA-07": "SE courses are more permissive than non-SE courses at the same level: policy_model.se_effect +0.6.",
    "DATA-08": "Permissiveness rises each term: policy_model.term_effect_per_step +0.2 per term, F23 (0) to F26 (6).",
    "DATA-09": "R1 departments have a more positive statement stance: stance_model.carnegie_effect R1 +0.7, "
               "R2 +0.25, others 0.",
    "DATA-10": "Planted null: policy_model.control_effect is 0.0 for public and private. inst_effect and the "
               "rhetoric-gap flags are drawn independently of control.",
    "DATA-11": "Statement labels: stance_latent = intercept + carnegie_effect + policy_coupling (1.2) * "
               "inst_effect + noise, so stance tracks the institution's course policies (except rhetoric-gap "
               "institutions). label_model: integrity more likely at negative stance (-0.15 per stance point), "
               "collaboration (+0.12) and careers (+0.10, +0.15 at R1) more likely at positive stance.",
    "DATA-15": "Allowed uses: use_model.base gives intro low code_generation (0.10) and testing (0.12); SE courses "
               "the highest code_generation and testing (0.75 each); probabilities scale up with policy.",
    "DATA-16": "Assessment: assessment_weights by policy. in_class_exams + oral_defense fall from 0.70 at policy 0 "
               "to 0.10 at policy 4; process_logs + ai_critique rise from 0.05 to 0.65.",
    "DATA-17": "Rhetoric gap: rhetoric_gap_share 0.15 of institutions (institutions[*].rhetoric_gap). "
               "enthusiastic_rhetoric_restrictive_courses: inst_effect -1.0, stance_latent +1.5. "
               "cautious_rhetoric_permissive_courses: inst_effect +1.0, stance_latent -1.5.",
}


# ---------------------------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------------------------
def _round_floats(obj, ndigits=4):
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: _cell(r[c]) for c in columns})


def _cell(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    return v


def write_json(path: Path, obj) -> None:
    text = json.dumps(_round_floats(obj), sort_keys=True, indent=1, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def build(seed: int) -> dict:
    """Generate every table in memory. Returns {"institutions": [...], ..., "ground_truth": {...}}."""
    rng = random.Random(seed)
    institutions = make_institutions(rng, load_real_names())
    hidden = make_institution_hidden(rng, institutions)
    statements, statement_labels = make_statements(rng, institutions, hidden)
    clean_courses, course_latent = make_courses(rng, institutions, hidden)
    courses, mess = add_mess(rng, clean_courses)
    ground_truth = {
        "synthetic": True,
        "note": "SYNTHETIC DATA. Hidden labels and planted effects. Analysis code must never read this file.",
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "parameters": {
            "institutions": {"sd_inst_effect": SD_INST_EFFECT, "rhetoric_gap_share": RHETORIC_GAP_SHARE,
                             "rhetoric_gap": RHETORIC_GAP},
            "stance_model": STANCE_MODEL,
            "label_model": LABEL_MODEL,
            "statement_count_mix": STATEMENT_COUNT_MIX,
            "terms": TERMS,
            "policy_model": POLICY_MODEL,
            "disclosure_prob": DISCLOSURE_PROB,
            "use_model": USE_MODEL,
            "tool_model": TOOL_MODEL,
            "assessment_weights": dict(zip(map(str, ASSESSMENT_WEIGHTS), ASSESSMENT_WEIGHTS.values())),
            "catalog": {"courses_per_inst": COURSES_PER_INST, "later_level_weights": LATER_LEVEL_WEIGHTS,
                        "p_se": P_SE, "p_offered": P_OFFERED},
            "mess": MESS,
        },
        "planted_effects": PLANTED_EFFECTS,
        "institutions": hidden,
        "statements": statement_labels,
        "courses": {r["course_id"]: {"course_effect": r["course_effect"]} for r in course_latent},
        "course_rows": [{"course_id": l["course_id"], "term": l["term"], "latent_score": l["latent_score"],
                         "policy": c["policy"]} for l, c in zip(course_latent, clean_courses)],
        "mess": mess,
    }
    return {"institutions": institutions, "statements": statements, "courses": courses,
            "ground_truth": ground_truth}


def generate(seed: int, out: Path = DEFAULT_OUT) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tables = build(seed)
    write_csv(out / "institutions.csv", INSTITUTION_COLUMNS, tables["institutions"])
    write_csv(out / "statements.csv", STATEMENT_COLUMNS, tables["statements"])
    write_csv(out / "courses.csv", COURSE_COLUMNS, tables["courses"])
    write_json(out / "ground_truth.json", tables["ground_truth"])
    return tables


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Generate the SYNTHETIC P1 dataset.")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    generate(args.seed, args.out)
    print(f"wrote synthetic data (seed {args.seed}) to {args.out}")


if __name__ == "__main__":
    main()
