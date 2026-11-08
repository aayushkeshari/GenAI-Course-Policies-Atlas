# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T05:12:41-05:00
Current phase: P1 (synthetic data). All P1 work is complete and pushed; 244 tests pass. Not yet Done: Aayush has to
spot-check the real-university list and write a P1 review-log entry. .phase is "P1:planning"; change it only if Aayush says to.
Last completed task: statement text rewrite (generator v2), the DATA-16 Cochran–Armitage trend test, and the ANL-14 spec addition. Then a checkpoint.
Next task (exact, actionable):
  1. Ask Aayush whether the P1 review is done: the real-university list spot-check (data/reference/real_universities.txt, 159 names)
     and a docs/review-log.md entry for P1. Do not start P2 code before that.
  2. Once Aayush confirms, read specs/P2-analysis.md only and propose a P2 plan (ANL-01..14). Write no code before approval.
     The plan must:
     - use the public dev/held-out split from docs/data-dictionary.md (odd inst_id number = held-out) for ANL-03
     - satisfy ANL-14 (institution clustering)
     - ask Aayush whether ANL-03 should name that split rule in the spec
Files touched this session: data/reference/real_universities.txt, src/data/generate.py, src/analysis/__init__.py, data/raw/*,
  Makefile (data target), tests/{datautil,test_data_generate,test_data_statements,test_data_courses,test_data_truth,
  test_data_schema,test_data_dictionary}.py, docs/data-dictionary.md, docs/progress.md, docs/HANDOFF.md,
  specs/P2-analysis.md (ANL-14, at Aayush's direction), .phase (human: commit), results/tests/run-*.json, logs/events.jsonl (hook-written)
Test status (command + result): `make test`: 244 passed (2026-11-08T05:12)
Decisions this session (HUMAN/AGENT):
  HUMAN: 7 terms (fall + spring). HUMAN: tools_named is multi-label, empty when policy = 0. HUMAN: a missing policy blanks all policy-derived fields
    and keeps assessment_adaptation. HUMAN: duplicates in courses only. HUMAN: moderate effects with exact parameters in ground_truth.json.
  HUMAN: the DATA-16 pooled-group rewrite is a fair fix. Added a Cochran–Armitage trend test that must be significant on at least 4 of 5 seeds (all 5 pass, |z| ≈ 17–18).
  HUMAN: statement text must be a real coding test: 9 phrasings per bank, negations, hedges, AI-without-stance, keyword traps,
    and phrasings reserved for the held-out half.
  HUMAN: add ANL-14 (institution clustering) to the P2 spec. HUMAN: Aayush spot-checks the real-university list.
  AGENT: stdlib-only generator; statement count is a fixed mix (348); a persistent course_effect; policy rounds halves up.
  AGENT: the dev/held-out split is by institution parity (public rule in the data dictionary). Keyword traps only for integrity and collaboration.
  AGENT: data/raw and ground_truth.json are committed; a test fails if they go stale relative to the generator.
Open questions for Aayush:
  - Should ANL-03 reference the split rule in docs/data-dictionary.md? Decide during P2 planning.
  - Spot-check of real_universities.txt and the P1 review-log entry (both Aayush).
  - [P5, raised by HUMAN 2026-11-08] PROV-02 labels "prompts" as HUMAN, but UserPromptSubmit also fires for
    scheduled tasks, background subagents, and cross-session messages. So a logged prompt is not necessarily
    human-typed. P5 must distinguish these sources (or label them "shared"/non-human) rather than assume every
    UserPromptSubmit event is HUMAN. Possible spec change to PROV-02; decide before P5 planning.
Gotchas for the next session:
  - The project path has spaces. The Makefile uses relative paths only; quote paths in shell commands.
  - Use .venv/bin/python (3.11) or /usr/bin/python3.
  - tests/conftest.py must contain only the plugin. Helpers go in tests/hookutil.py (hooks) or tests/datautil.py (data).
  - Tests load the generator via importlib (datautil.gen_module), so no pythonpath or package install is needed.
  - Any change to src/data/generate.py needs `make data` and a commit of data/raw/, or test_committed_data_matches_generator fails.
    Changing statement generation also shifts the course data, because both draw from one random stream; recheck any quoted numbers.
  - src/analysis/ must never mention ground_truth (DATA-05 grep, case-insensitive, any file type). Only the __init__ docstring is exempt.
  - The DATA-10 null still shows sampling gaps up to about ±0.12 across seeds. P2 must use clustered inference (ANL-14).
  - Never edit logs/ or raw_logs/. Hooks own them.
