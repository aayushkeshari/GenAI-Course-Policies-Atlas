"""ANL-02: rule-based coding of statement text (no LLM calls, no learned weights).

Every coded value records the rule that produced it, so each decision traces to a rule in
docs/codebook.md. Rules were written and tuned on the DEV half only (docs/data-dictionary.md):
each rule cites an `example` that occurs verbatim in a dev statement, and tests enforce that.

Stance: rules are tried in order; the first rule whose pattern matches any sentence decides the
stance. Negation rules come first so "not prohibited" is never read as "prohibited". If nothing
matches, the stance is 0 (rule S0-default).

Mentions: a label is true if any of its rules matches any sentence.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.analysis.common import CLEAN, read_clean, write_csv

LABELS = ["mentions_integrity", "mentions_collaboration", "mentions_careers"]


@dataclass(frozen=True)
class Rule:
    id: str
    code: str        # "stance" or a label name
    value: int       # stance value, or 1 for a label rule
    pattern: str     # case-insensitive regex
    example: str     # verbatim text from a DEV statement that the rule matches

    @property
    def regex(self) -> re.Pattern:
        return re.compile(self.pattern, re.IGNORECASE)


STANCE_RULES = [
    # --- negations and other phrases that contain a misleading cue word: checked first ---
    Rule("S+1-not-prohibited", "stance", 1, r"\bnot prohibited\b", "AI use is not prohibited"),
    Rule("S-1-not-by-default", "stance", -1, r"\bnot permitted by default\b", "are not permitted by default"),
    Rule("S0-no-single-rule", "stance", 0, r"\bnot adopted a single\b", "has not adopted a single rule on AI tools"),
    Rule("S0-neither-nor", "stance", 0, r"\bneither endorses nor bans\b", "neither endorses nor bans generative AI"),
    # --- -2 prohibited ---
    Rule("S-2-prohibit", "stance", -2, r"\bprohibit(s|ed)?\b", "The department prohibits the use of generative AI tools"),
    Rule("S-2-not-permitted", "stance", -2, r"\bnot permitted\b", "is not permitted in computer science courses"),
    Rule("S-2-may-not-use", "stance", -2, r"\bmay not use\b", "Students may not use generative AI systems"),
    Rule("S-2-ban", "stance", -2, r"\bban\w*", "AI assistants are banned from all programming assignments"),
    Rule("S-2-no-credit", "stance", -2, r"\bno credit\b", "will receive no credit"),
    # --- -1 limited / cautious ---
    Rule("S-1-caution", "stance", -1, r"\bcaution\b", "The department urges caution with generative AI"),
    Rule("S-1-concerns", "stance", -1, r"\bserious concerns\b", "Generative AI tools raise serious concerns"),
    Rule("S-1-not-allowed-unless", "stance", -1, r"\bnot allowed unless\b", "they are not allowed unless told otherwise"),
    Rule("S-1-avoid", "stance", -1, r"\bavoid\b", "Students should generally avoid AI tools"),
    Rule("S-1-limited", "stance", -1, r"\blimited (use|to)\b", "Limited use of AI for looking up concepts"),
    Rule("S-1-restrict", "stance", -1, r"\brestrict\w*", "restrict them in most courses"),
    # --- 0 instructor decides ---
    Rule("S0-each-instructor", "stance", 0, r"\beach instructor\b", "Each instructor sets the policy"),
    Rule("S0-vary", "stance", 0, r"\bvary by course\b", "vary by course and are described in each syllabus"),
    Rule("S0-left-to-faculty", "stance", 0, r"\bleft to individual\b", "a decision left to individual faculty members"),
    Rule("S0-differ", "stance", 0, r"\bdiffer\b", "rules on AI assistance differ between classes"),
    # --- +1 permitted with conditions ---
    Rule("S+1-thoughtful", "stance", 1, r"\bsupports? thoughtful\b", "The department supports thoughtful use"),
    Rule("S+1-welcome", "stance", 1, r"\bwelcome to use\b", "Students are welcome to use AI assistants"),
    Rule("S+1-support-learning", "stance", 1, r"\bsupport learning\b", "Generative AI can support learning"),
    Rule("S+1-adopting", "stance", 1, r"\badopting\b", "the faculty are adopting it in a growing number of courses"),
    Rule("S+1-may-use", "stance", 1, r"\bmay use\b", "students may use AI tools for some tasks"),
    Rule("S+1-responsible", "stance", 1, r"\bresponsible use\b", "Responsible use of AI assistants is allowed"),
    # --- +2 embraced / integrated ---
    Rule("S+2-embrace", "stance", 2, r"\bembrace\w*", "The department embraces generative AI"),
    Rule("S+2-curriculum", "stance", 2, r"\bthroughout the curriculum\b", "integrating AI coding assistants throughout the curriculum"),
    Rule("S+2-transforming", "stance", 2, r"\btransforming\b", "Generative AI is transforming software development"),
    Rule("S+2-required", "stance", 2, r"\brequired part\b", "is a required part of our programming courses"),
]
DEFAULT_STANCE_RULE = "S0-default"

LABEL_RULES = [
    Rule("I-academic-integrity", "mentions_integrity", 1, r"\bacademic integrity\b", "a violation of the academic integrity policy"),
    Rule("I-honor-code", "mentions_integrity", 1, r"\bhonor code\b", "will be handled under the honor code"),
    Rule("I-originality", "mentions_integrity", 1, r"\boriginality\b", "responsible for the originality of their work"),
    Rule("I-misrepresent", "mentions_integrity", 1, r"\bmisrepresent\w*", "must not misrepresent AI output as their own"),
    Rule("I-dishonesty", "mentions_integrity", 1, r"\bdishonest\w*", "counts as academic dishonesty"),
    Rule("I-conduct", "mentions_integrity", 1, r"\bstudent conduct\b", "referred to the office of student conduct"),
    Rule("I-plagiarism", "mentions_integrity", 1, r"\bplagiari\w*", "Plagiarism rules apply to text and code"),
    Rule("C-collaborators", "mentions_collaboration", 1, r"\bcollaborators?\b", "treat AI tools as collaborators"),
    Rule("C-teamwork", "mentions_collaboration", 1, r"\bteamwork\b", "how AI assistants can support teamwork"),
    Rule("C-collab-problem", "mentions_collaboration", 1, r"\bcollaborative problem", "collaborative problem-solving exercises"),
    Rule("C-teammate", "mentions_collaboration", 1, r"\bteammates?\b", "AI tools can act as a teammate"),
    Rule("C-partners", "mentions_collaboration", 1, r"(?<!internship )\bpartners?\b", "alongside human partners"),  # dev: "Internship partners" is careers, not collaboration
    Rule("C-group-work", "mentions_collaboration", 1, r"\bgroup (projects?|assignments?)\b", "Group assignments may ask teams"),
    Rule("C-co-design", "mentions_collaboration", 1, r"\bco-design\w*", "co-designing course activities"),
    Rule("C-together", "mentions_collaboration", 1, r"\b(working|decide) together\b", "Faculty and students are working together"),
    Rule("K-employers", "mentions_careers", 1, r"\bemployers?\b", "Employers increasingly expect graduates"),
    Rule("K-industry", "mentions_careers", 1, r"\bindustry\b", "an industry reshaped by AI"),
    Rule("K-careers", "mentions_careers", 1, r"\bcareers?\b", "an important skill for careers in software"),
    Rule("K-internship", "mentions_careers", 1, r"\binternships?\b", "Internship partners report"),
    Rule("K-job", "mentions_careers", 1, r"\bjobs?\b", "Graduates will enter a job market"),
]
ALL_RULES = STANCE_RULES + LABEL_RULES


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def code_statement(text: str) -> dict:
    """Code one statement. Returns stance, each label, and the rule IDs behind each value."""
    sents = sentences(text)
    out = {"stance": 0, "stance_rule": DEFAULT_STANCE_RULE}
    for rule in STANCE_RULES:
        if any(rule.regex.search(s) for s in sents):
            out["stance"], out["stance_rule"] = rule.value, rule.id
            break
    for label in LABELS:
        fired = [r.id for r in LABEL_RULES if r.code == label and any(r.regex.search(s) for s in sents)]
        out[label] = bool(fired)
        out[f"{label}_rules"] = ";".join(fired)
    return out


def code_statements(statements: pd.DataFrame) -> pd.DataFrame:
    coded = pd.DataFrame([code_statement(t) for t in statements["text"]])
    return pd.concat([statements[["stmt_id", "inst_id"]].reset_index(drop=True), coded], axis=1)


def rules_markdown() -> str:
    """The rule table embedded in docs/codebook.md (a test keeps the two identical)."""
    lines = ["| Order | Rule | Code | Value | Pattern (case-insensitive) | Dev example |", "|---|---|---|---|---|---|"]
    for k, r in enumerate(ALL_RULES, 1):
        order = str(k) if r.code == "stance" else "any"
        pattern = r.pattern.replace("|", "\\|")
        lines.append(f"| {order} | `{r.id}` | {r.code} | {r.value} | `{pattern}` | \"{r.example}\" |")
    lines.append(f"| last | `{DEFAULT_STANCE_RULE}` | stance | 0 | (no stance rule matched) | — |")
    return "\n".join(lines)


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    clean_dir = Path(argv[0]) if argv else CLEAN
    coded = code_statements(read_clean("statements", clean_dir))
    for label in LABELS:
        coded[label] = coded[label].map({True: "true", False: "false"})
    write_csv(clean_dir / "statements_coded.csv", coded)


if __name__ == "__main__":
    main()
