# P1 — Synthetic data

The data is invented, so the analysis can be validated against a known truth: the generator plants
effects, and P2 must recover them.

## Generator
- **DATA-01** `src/data/generate.py --seed 2026` is deterministic: the same seed produces byte-identical files.
- **DATA-02** `data/raw/institutions.csv` has 150 rows with fictional names built from word lists.
  No name exactly matches any entry in `data/reference/real_universities.txt` (~150 real US universities with CS programs).
  Columns: inst_id, name, state, census_region, control (public/private), carnegie (R1/R2/Masters/Baccalaureate), cs_enrollment.
- **DATA-03** `data/raw/statements.csv` has ~350 official-publication excerpts (0–4 per institution).
  Columns: stmt_id, inst_id, pub_type (policy_page/news/strategic_plan/syllabus_template/faq),
  pub_date (2023-01 to 2026-10), text (2–5 sentences assembled from phrase banks, keyed to hidden labels).
- **DATA-04** `data/raw/courses.csv` has ~2,000 course-term rows. Columns: course_id, inst_id, code, title,
  level (intro/intermediate/upper/graduate), is_se (bool), term (F23…F26),
  policy (0 prohibited, 1 limited use, 2 permitted with disclosure, 3 encouraged, 4 integrated/required),
  disclosure_required, assessment_adaptation (none/in_class_exams/oral_defense/process_logs/ai_critique), tools_named,
  allowed_uses (multi-label, semicolon-separated: explanation;debugging;code_generation;testing;writing; empty when policy = 0).
- **DATA-05** Hidden labels and planted effects go only in `data/raw/ground_truth.json`.
  Analysis code must never read this file (enforced by a test that greps src/analysis/).

## Planted effects (the truth P2 must recover)
- **DATA-06** Intro courses are more restrictive than upper-level courses.
- **DATA-07** SE courses are more permissive than non-SE courses at the same level.
- **DATA-08** Permissiveness rises with each term.
- **DATA-09** R1 departments have a more positive statement stance.
- **DATA-10** Planted null: control (public/private) has no effect on policy. This checks for false positives.
- **DATA-15** Learning vs producing: intro courses that allow AI mostly allow explanation and debugging, rarely
  code_generation. SE courses are the most likely to allow code_generation and testing.
- **DATA-11** Statement labels (stance −2..+2, mentions_collaboration, mentions_integrity, mentions_careers)
  are correlated with the planted effects in documented ways.

## Realistic mess
- **DATA-12** 8% of policies missing at random, inconsistent casing in `level`, ~1% duplicate rows,
  some statements that mention both integrity concerns and collaboration.

- **DATA-13** Schema tests: types, allowed values, row counts within ±10%, referential integrity.
- **DATA-14** `docs/data-dictionary.md` documents every column and states that the data is synthetic.
