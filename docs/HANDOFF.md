# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T05:50:09-05:00
Current phase: P2 (analysis). .phase is "P2:planning". The P2 plan is approved (see progress.md P2 step 0). Steps 0–3 are done and committed;
the session stopped at the ANL-04 hand-coding hand-off, as Aayush asked.
Last completed task: P2 step 3. Coder rules frozen at 32f3cd2. Held-out macro-F1 0.829. Hand-coding sample written
  (data/reference/hand_code_sample.csv, 30 rows, blank labels).
Next task (exact, actionable):
  1. If Aayush has filled in data/reference/hand_code_sample.csv: run `make analysis` (writes results/kappa.json), then `make test`.
     test_human_agreement_kappa_reported must now pass, not skip. Report the kappas and commit.
  2. Continue the approved P2 plan with step 4 (ANL-05/11/12 descriptives with a cluster bootstrap that resamples institutions,
     2,000 resamples, fixed seed). Then step 5 (ANL-06/07/14), 6 (ANL-13), 7 (ANL-08 recovery: ratio ±25% + clustered-CI coverage on ≥4/5 seeds +
     null non-significant when clustered), 8 (ANL-09 schemas), 9 (ANL-10 methods.md). Commit after each step.
  Do NOT change src/analysis/code_text.py or docs/codebook.md: the rules are frozen, and test_heldout_report_is_current_and_rules_are_frozen guards them.
Files touched this session: data/reference/real_universities.txt, src/data/generate.py, src/analysis/__init__.py, data/raw/*,
  Makefile (data target), tests/{datautil,test_data_generate,test_data_statements,test_data_courses,test_data_truth,
  test_data_schema,test_data_dictionary}.py, docs/data-dictionary.md, docs/progress.md, docs/HANDOFF.md,
  docs/review-log.md (Aayush's text, human: commit), specs/P2-analysis.md (ANL-14, at Aayush's direction),
  .phase (human: commits), results/tests/run-*.json, logs/events.jsonl (hook-written)
Test status (command + result): `make test`: 322 passed, 1 skipped (kappa, awaiting human coding). Previous: `make test`: 244 passed (2026-11-08T05:35)
Decisions this session (HUMAN/AGENT):
  HUMAN: 7 terms (fall + spring). HUMAN: tools_named is multi-label, empty when policy = 0. HUMAN: a missing policy blanks all policy-derived
    fields and keeps assessment_adaptation. HUMAN: duplicates in courses only. HUMAN: moderate effects with exact parameters in ground_truth.json.
  HUMAN: the DATA-16 pooled-group rewrite is a fair fix, plus a Cochran–Armitage trend test (5/5 seeds significant).
  HUMAN: statement text is a real coding test (9 phrasings per bank, hard cases, held-out-only phrasings).
  HUMAN: ANL-14 clustering added to the P2 spec. HUMAN: P1 accepted; real-university list spot-checked.
  AGENT: stdlib-only generator; dev/held-out split by institution parity; data/raw committed with a staleness test.
Open questions for Aayush:
  - ANL-04: hand-code the 30 statements in data/reference/hand_code_sample.csv.
  - Should ANL-03 reference the split rule in docs/data-dictionary.md? (Ask in the P2 plan.)
  - [P5, raised by HUMAN 2026-11-08] PROV-02 labels "prompts" as HUMAN, but UserPromptSubmit also fires for
    scheduled tasks, background subagents, and cross-session messages. So a logged prompt is not necessarily
    human-typed. P5 must distinguish these sources (or label them "shared"/non-human) rather than assume every
    UserPromptSubmit event is HUMAN. Possible spec change to PROV-02; decide before P5 planning.
  - [P5] Per Aayush's P1 review-log note: some decisions logged as "HUMAN" were drafted with Claude chat. P5 should tell
    "decided by Aayush" apart from "written by Aayush" (or use "shared").
Gotchas for the next session:
  - The project path has spaces. The Makefile uses relative paths only; quote paths in shell commands.
  - Use .venv/bin/python (3.11) or /usr/bin/python3.
  - tests/conftest.py must contain only the plugin. Helpers go in tests/hookutil.py (hooks) or tests/datautil.py (data).
  - Tests load the generator via importlib (datautil.gen_module); no pythonpath is set. P2 will need a decision on how tests import src/analysis.
  - Any change to src/data/generate.py needs `make data` and a commit of data/raw/. Statement and course generation share one random stream.
  - src/analysis/ must never mention ground_truth (DATA-05 grep, case-insensitive, any file type). Only the __init__ docstring is exempt.
  - The DATA-10 null shows row-level gaps up to about ±0.12 across seeds. Clustered inference (ANL-14) is required.
  - Never edit logs/ or raw_logs/. Hooks own them.
