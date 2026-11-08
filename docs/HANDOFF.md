# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T05:04:53-05:00
Current phase: P1 (synthetic data). Code complete, 236 tests pass, pushed. Not yet Done: Aayush reviews the
open items below and adds a review-log entry. .phase is "P1:planning" (Aayush set it); change it only if Aayush says to.
Last completed task: P1 steps 1–6 (generator, planted effects, mess, schema tests, data dictionary).
Next task (exact, actionable):
  1. Wait for Aayush's P1 review: the real-university list spot-check, the DATA-16 test change (see progress.md P1 entry), and a review-log entry.
  2. After Aayush approves, read specs/P2-analysis.md only and propose a P2 plan. Write no code before approval.
Files touched this session: data/reference/real_universities.txt, src/data/generate.py, src/analysis/__init__.py,
  data/raw/{institutions,statements,courses}.csv, data/raw/ground_truth.json, Makefile (data target),
  tests/{datautil,test_data_generate,test_data_statements,test_data_courses,test_data_truth,test_data_schema,test_data_dictionary}.py,
  docs/data-dictionary.md, docs/progress.md, docs/HANDOFF.md, results/tests/run-*.json
Test status (command + result): `make test`: 236 passed (2026-11-08T05:04)
Decisions this session (HUMAN/AGENT):
  HUMAN: terms are fall + spring, 7 terms. HUMAN: tools_named is multi-label, empty when policy = 0.
  HUMAN: a missing policy blanks policy/disclosure_required/allowed_uses/tools_named and keeps assessment_adaptation.
  HUMAN: duplicates in courses.csv only. HUMAN: moderate effects with exact parameters in ground_truth.json.
  HUMAN: real-university list written from memory. HUMAN: commit per step, run through step 6, push at the end.
  AGENT: stdlib-only generator; statement count is a fixed mix (348); a persistent course_effect; policy rounds halves up.
  AGENT: the DATA-16 observed test uses pooled policy groups; per-level order is checked on the planted weights (needs Aayush's review).
  AGENT: data/raw and ground_truth.json are committed; a test fails if they go stale relative to the generator.
Open questions for Aayush:
  - Review the DATA-16 test change. Is it an acceptable fix or a weakened test? (progress.md P1 entry)
  - Spot-check data/reference/real_universities.txt (159 names, written from memory).
  - [P2] DATA-10 null: the observed public−private gap reaches −0.21 at seed 2 (sampling noise from institution effects). P2 should account for institution clustering.
  - [P5, raised by HUMAN 2026-11-08] PROV-02 labels "prompts" as HUMAN, but UserPromptSubmit also fires for
    scheduled tasks, background subagents, and cross-session messages. So a logged prompt is not necessarily
    human-typed. P5 must distinguish these sources (or label them "shared"/non-human) rather than assume every
    UserPromptSubmit event is HUMAN. Possible spec change to PROV-02; decide before P5 planning.
Gotchas for the next session:
  - The project path has spaces. The hook command quotes "$CLAUDE_PROJECT_DIR/...", and the Makefile uses relative paths only.
  - Use /usr/bin/python3 or .venv/bin/python. Both work.
  - tests/conftest.py must contain only the plugin. Helpers go in tests/hookutil.py (hooks) or tests/datautil.py (data).
  - Tests load the generator via importlib (datautil.gen_module), so src/ needs no package install or pythonpath.
  - Any change to src/data/generate.py needs `make data` and a commit of data/raw/, or test_committed_data_matches_generator fails.
  - src/analysis/ must never mention ground_truth (DATA-05 grep, case-insensitive, any file type). Only the __init__ docstring is exempt.
  - Never edit logs/ or raw_logs/. Hooks own them.
