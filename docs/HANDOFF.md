# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T06:17:53-05:00
Current phase: P2 (analysis). Code complete, 395 tests pass, pushed. .phase is still "P2:planning" (Aayush changes it).
Not yet Done: Aayush's P2 review and review-log entry.
Last completed task: P2 steps 4–9 (descriptives, inference, rhetoric, recovery, schemas, methods). All ANL-01..14 are implemented and tested.
Next task (exact, actionable):
  1. Ask Aayush for the P2 review: the two tests changed after failing (see progress.md P2 steps 2 and 4), results, and a review-log entry.
  2. When Aayush moves .phase to P3: read specs/P3-dashboard.md only and propose a P3 plan (no code before approval).
     Every dashboard number must come from results/*.json (schemas in src/report/schemas/).
Files touched this session (P2): requirements.txt, pytest.ini, Makefile, src/__init__.py, src/analysis/{common,clean,code_text,stats,descriptives,
  inference,rhetoric,run}.py, src/evaluation/{__init__,truth,coder_eval,hand_sample,rhetoric_eval,recovery,run}.py, src/report/schemas/*.json,
  data/clean/*, data/reference/hand_code_sample.csv (Aayush's codes + header comment), results/*.json,
  tests/test_anl_{clean,coder,eval,descriptives,inference,rhetoric,recovery,schemas,methods}.py, docs/{codebook,methods,progress,HANDOFF}.md,
  specs/P2-analysis.md (ANL-03 split wording, ANL-04 "Aayush vs", ANL-14; all at Aayush's direction)
Test status (command + result): `make test`: 395 passed (2026-11-08T06:17)
Decisions this session (HUMAN/AGENT):
  HUMAN: src/evaluation/ is the only non-test code that may read the truth. HUMAN: ANL-03 cites the data-dictionary split; tune on dev only.
  HUMAN: clustered SEs by inst_id are the main regression inference. HUMAN: chi-square p is labelled naive, with Cramér's V cluster-bootstrap CI as the main inference.
  HUMAN: ±25% ratio check plus clustered-CI coverage on ≥4/5 seeds. HUMAN: the kappa test is SKIPPED until coded; ANL-04 kappa is labelled "Aayush vs coder/truth".
  AGENT: every coder rule must cite dev text (4 ungrounded rules removed); rules frozen at 32f3cd2 and guarded by a SHA-256 test.
  AGENT: the regression bootstrap cross-check uses 500 refits; descriptives use 2,000. The staleness test skips the slow bootstrap.
  AGENT: magnitudes are compared as ratios to the term effect; methods.md quotes no numbers.
Open questions for Aayush:
  - Review the tests changed after failing: step 2 (removed 4 rules whose examples were not dev text) and step 4 (clustering-width test retargeted
    from per-term means, ~1.04x, to the overall mean and the private-public gap, ~2x, with a 1.5x floor).
  - P2 review-log entry; .phase → P3 when ready.
  - [P5] PROV-02: UserPromptSubmit also fires for scheduled tasks, background subagents and cross-session messages, so a logged prompt is not
    necessarily human-typed. Also, some "HUMAN" decisions were drafted with Claude chat (Aayush's P1 review note). Decide before P5 planning.
Gotchas for the next session:
  - The project path has spaces; quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = . (import src.*).
  - `make analysis` takes ~80 s (75 s is the 500-refit regression bootstrap). `make test` takes ~9 s.
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md: the rules are frozen (test_heldout_report_is_current_and_rules_are_frozen).
  - src/analysis/ must never mention ground_truth or import src.evaluation (DATA-05 grep + AST test).
  - Any change to inputs needs `make data`/`make analysis` and committing data/ and results/, or the staleness tests fail.
  - tests/conftest.py must contain only the plugin. Helpers go in tests/hookutil.py and tests/datautil.py.
  - Never edit logs/ or raw_logs/. Hooks own them.
