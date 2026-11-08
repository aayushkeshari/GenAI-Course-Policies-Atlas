# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T08:26:59-05:00
Current phase: P4 (validation explorer). VAL-01..08 are implemented and tested. 502 tests pass. .phase is "P4:writing-code" (only Aayush changes it).
Last completed task: P4 step 6, the VAL-08 Playwright tests, plus a final `make faults` on the full suite. All commits are pushed.
Next task (exact, actionable):
  1. Tell Aayush P4 is ready for review: `make serve`, then http://127.0.0.1:8000/validation/ (the dashboard is at /dashboard/).
     - Ask for a P4 review-log entry; the P3 one is also still pending, since Aayush is checking the dashboard first. Append either one verbatim to docs/review-log.md and commit it as `human: P<n> review-log entry`. Then `make test && make report && make test`, because the review log is an input to the explorer.
     - Ask whether .phase should move to P5.
  2. Once .phase is P5, read specs/P5-provenance.md only and propose a plan. Settle PROV-02 (below) first.
Files touched in P4: specs/P4-validation.md (VAL-01/02, approved), tests/conftest.py (test-run/2 + body sidecars), Makefile (test: --cov + attach-coverage; faults; report),
  .gitignore, src/validation/{__init__,runs,specs,redact,faults}.py, src/report/build_validation_data.py, src/report/claims.json,
  src/report/schemas/faults.schema.json, results/faults.json, results/tests/{bodies,coverage}/, site/validation/{index.html,style.css,app.js,data/**},
  site/dashboard/app.js (Evidence links), tests/{test_runfile,test_makefile,test_dash_ui,test_val_specs,test_val_data,test_val_faults,test_val_claims,test_val_ui}.py, docs/{progress,HANDOFF}.md
Test status (command + result): `make test`: 502 passed (2026-11-08T08:26:59-05:00). `make faults`: 10/10 caught, 5/10 by behavioral tests.
Decisions (HUMAN/AGENT):
  HUMAN: VAL-01/02 spec change: body sidecars by content hash (results/tests/bodies/<sha>.json), keep every run and body.
  HUMAN: marked 12.0.2 + DOMPurify 3.1.6 (cdnjs) for the review log. Faults skip the UI tests except for F09. One claim per panel plus the headline tiles.
  HUMAN: truth-derived recovery files are shown only on "Recovery vs. ground truth (validation only)"; site/data and the dashboard stay truth-free (tested).
  AGENT: the old test-run/1 files are left as they are; the reader accepts both formats.
  AGENT: the snapshot is the newest `make test` run (one with results/tests/coverage/<run>); freshness is checked by rebuilding from manifest.run.
  AGENT: published test text is redacted (src/validation/redact.py) with visible ‹redacted-…› placeholders. The P3 privacy test now scans decoded JSON strings, which is strictly stronger.
  AGENT: fault runs set PYTHONDONTWRITEBYTECODE=1 (a stale .pyc otherwise hides same-size edits) and always exclude tests/test_val_faults.py.
  AGENT: the fault report separates golden-file catches (*_is_current / *_are_current) from behavioral ones.
Key facts for P5+:
  - After any code change, run `make test && make report` twice so the snapshot is an all-green run; `test_validation_data_is_current` rebuilds from manifest.run.
  - Changing results/faults.json, claims.json, specs or review-log.md requires `make report`. Changing a fault target's code may break "old text occurs exactly once" (tested).
  - GitHub Pages is NOT enabled yet. P7 (PUB-02) deploys; the expected URL is https://aayushkeshari.github.io/genai-cs-policy/validation/.
Open questions for Aayush:
  - P3 and P4 review-log entries; .phase → P5.
  - Add behavioral tests for the five golden-only faults (F01 regression sign, F05 term_index base, F07 gap denominator, F08 gap sign, F09 export fields)? Not done; it wasn't asked for.
  - Review the P3 privacy-test change (decoded JSON scan) and the redaction of INST-09's "/Users/<name>" example in the published spec text.
  - [P5] PROV-02: UserPromptSubmit also fires for scheduled tasks, background subagents and cross-session messages, so a logged prompt is not
    necessarily human-typed. Some "HUMAN" decisions were drafted with Claude chat. Decide before P5 planning.
  - Possible error in the committed P2 review-log entry (stance 0.76 vs macro-F1 0.741 / accuracy 0.761). Aayush chose to leave it.
Gotchas for the next session:
  - The project path has spaces, so quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = . (import src.*).
  - `make test` takes ~30 s, including the UI tests, which need the network. `make faults` takes ~2.5 min. `make analysis` takes ~80 s.
  - Every top-level results/*.json needs a schema in src/report/schemas/ (ANL-09). The full coverage report lives at results/tests/coverage/latest.json (gitignored).
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md: the rules are frozen (SHA-256 test).
  - src/analysis/ must never mention ground_truth or import src.evaluation; the same applies to both src/report builders (tested).
  - The dashboard's .panel-foot may hold only data-source links (P3 test); Evidence links go below it.
  - tests/conftest.py must contain only the plugin. Never edit logs/ or raw_logs/; hooks own them.
