# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T06:25:31-05:00
Current phase: P2 (analysis). All ANL-01..14 are implemented and tested, 395 tests pass, pushed. .phase is "P2:planning" (only Aayush changes it).
  Aayush has accepted both test changes made after failures. Not yet Done: Aayush's P2 review-log entry.
Last completed task: confirmed that the ANL-05 descriptive bootstraps use 2,000 resamples (500 only for the regression cross-check); checkpoint.
Next task (exact, actionable):
  1. Ask Aayush whether the P2 review-log entry is written and whether .phase should move to P3. If Aayush pastes an entry, append it verbatim
     to docs/review-log.md and commit it as `human: P2 review-log entry`.
  2. Once .phase is P3: read specs/P3-dashboard.md only and propose a P3 plan in chat (no code before approval). Constraints for the plan:
     - Every dashboard number comes from results/*.json; read them by their schemas in src/report/schemas/.
     - Static HTML/CSS/JS in site/, with no build step and every CDN library pinned to an exact version.
     - Every page says the data is synthetic. No secrets, home paths or emails under site/.
     - Show clustered vs naive inference where it matters (regression.json has both; association/assessment p-values are labelled naive).
Files touched in P2: requirements.txt, pytest.ini, Makefile, src/__init__.py, src/analysis/{common,clean,code_text,stats,descriptives,inference,
  rhetoric,run}.py, src/evaluation/{__init__,truth,coder_eval,hand_sample,rhetoric_eval,recovery,run}.py, src/report/schemas/*.schema.json (12),
  data/clean/*, data/reference/hand_code_sample.csv, results/*.json (12), tests/test_anl_*.py (9 files), docs/{codebook,methods,progress,HANDOFF}.md,
  specs/P2-analysis.md (ANL-03, ANL-04, ANL-14 edits at Aayush's direction)
Test status (command + result): `make test`: 395 passed (2026-11-08T06:25)
Decisions (HUMAN/AGENT):
  HUMAN: only src/evaluation/ and tests may read the truth. HUMAN: ANL-03 cites the data-dictionary split; coder tuned on dev only.
  HUMAN: clustered SEs by inst_id are the main regression inference. HUMAN: chi-square p labelled naive; Cramér's V cluster-bootstrap CI is the main inference.
  HUMAN: ±25% ratio sanity check plus clustered-CI coverage ≥4/5 seeds. HUMAN: kappa labelled "Aayush vs coder" / "Aayush vs truth".
  HUMAN: both test changes made after failures are accepted. HUMAN: 2,000 resamples for descriptives; 500 only for the regression cross-check.
  AGENT: every coder rule cites dev text; rules frozen at 32f3cd2 and guarded by a SHA-256 test. AGENT: magnitudes compared as ratios to the term effect.
  AGENT: methods.md quotes no numbers (numbers live only in results/).
Key results (seed 2026), for the dashboard plan:
  - Held-out coder macro-F1 0.829 (target 0.80).
  - Directions DATA-06..09 recovered; null private p = 0.64 clustered (0.21 naive).
  - Baccalaureate naive p = 0.007 vs clustered p = 0.28 (a false positive removed by clustering).
  - Ratios within ±25% of planted (6–15% low); coverage ≥4/5 for all.
  - Rhetoric-gap list precision 0.93, recall 0.68.
Open questions for Aayush:
  - P2 review-log entry; .phase → P3.
  - [P5] PROV-02: UserPromptSubmit also fires for scheduled tasks, background subagents and cross-session messages, so a logged prompt is not
    necessarily human-typed. Also, some "HUMAN" decisions were drafted with Claude chat (Aayush's P1 review note). Decide before P5 planning.
Gotchas for the next session:
  - The project path has spaces; quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = . (import src.*).
  - `make analysis` takes ~80 s (75 s is the 500-refit regression bootstrap). `make test` takes ~9 s.
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md: the rules are frozen (test_heldout_report_is_current_and_rules_are_frozen).
  - src/analysis/ must never mention ground_truth or import src.evaluation (DATA-05 grep + AST test).
  - Changing data or analysis code needs `make data`/`make analysis` and committing data/ and results/, or the staleness tests fail.
  - tests/conftest.py must contain only the plugin. Helpers go in tests/hookutil.py and tests/datautil.py.
  - Never edit logs/ or raw_logs/. Hooks own them.
