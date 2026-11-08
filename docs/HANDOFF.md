# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T05:35:58-05:00
Current phase: P2 (analysis), planning. .phase is "P2:planning" (set by Aayush). P1 is Done: code, tests, and docs are pushed,
and Aayush's review-log entry is committed (461b7ac).
Last completed task: P1 closed out. Aayush's P1 review-log entry was committed; checkpoint before /clear.
Next task (exact, actionable):
  Read specs/P2-analysis.md only (ANL-01..14) and propose a P2 plan in chat. Write no code before Aayush approves it.
  The plan must cover:
  - Steps, each committed separately with tests tagged @pytest.mark.req("ANL-xx").
  - New pinned deps in requirements.txt (P2 needs pandas, statsmodels, scipy, jsonschema or similar; currently only test tooling is pinned).
  - ANL-03: tune rules on the dev half only and report on the held-out half. Use the public split in docs/data-dictionary.md
    (odd inst_id number = held-out).
  - ANL-14: cluster by inst_id for every inferential result.
  - ANL-04: a HUMAN task for Aayush to hand-code 30 held-out statements.
  - src/analysis/ must never mention ground_truth. Recovery tests (ANL-08, -11, -13) live in tests/ and may read it.
  Questions to ask Aayush in the plan:
  - Should ANL-03 cite the split rule in the spec?
  - Which clustering method: cluster-robust SEs, a mixed model, or a cluster bootstrap?
Files touched this session: data/reference/real_universities.txt, src/data/generate.py, src/analysis/__init__.py, data/raw/*,
  Makefile (data target), tests/{datautil,test_data_generate,test_data_statements,test_data_courses,test_data_truth,
  test_data_schema,test_data_dictionary}.py, docs/data-dictionary.md, docs/progress.md, docs/HANDOFF.md,
  docs/review-log.md (Aayush's text, human: commit), specs/P2-analysis.md (ANL-14, at Aayush's direction),
  .phase (human: commits), results/tests/run-*.json, logs/events.jsonl (hook-written)
Test status (command + result): `make test`: 244 passed (2026-11-08T05:35)
Decisions this session (HUMAN/AGENT):
  HUMAN: 7 terms (fall + spring). HUMAN: tools_named is multi-label, empty when policy = 0. HUMAN: a missing policy blanks all policy-derived
    fields and keeps assessment_adaptation. HUMAN: duplicates in courses only. HUMAN: moderate effects with exact parameters in ground_truth.json.
  HUMAN: the DATA-16 pooled-group rewrite is a fair fix, plus a Cochran–Armitage trend test (5/5 seeds significant).
  HUMAN: statement text is a real coding test (9 phrasings per bank, hard cases, held-out-only phrasings).
  HUMAN: ANL-14 clustering added to the P2 spec. HUMAN: P1 accepted; real-university list spot-checked.
  AGENT: stdlib-only generator; dev/held-out split by institution parity; data/raw committed with a staleness test.
Open questions for Aayush:
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
