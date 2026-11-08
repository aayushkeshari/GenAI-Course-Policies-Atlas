# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T08:43:43-05:00
Current phase: P4 (validation explorer) is done and reviewed: VAL-01..08 are implemented, and the P3 and P4 review-log entries are committed. .phase is "P4:writing-code" (only Aayush changes it).
Last completed task: added the PROV-02 prompt categories to specs/P5-provenance.md (9bd44d7). Everything is pushed except this checkpoint commit.
Next task (exact, actionable):
  1. Ask Aayush to confirm the PROV-02 wording (open question below) and to set .phase to P5:planning. Wait for both.
  2. Then read specs/P5-provenance.md only and propose a P5 plan (contribution timeline) in chat. Write no code before approval.
     Constraints for the plan:
     - Sources: logs/events.jsonl (hooks; never edit), git log (`agent:` / `human:` prefixes), docs/review-log.md, spec-file history in git.
     - PROV-02 actor rules are in the spec. Ambiguous items are "shared"; never guess.
     - The site is static in site/ with no build step, pinned CDN, a synthetic banner, and no emails, home paths or secrets.
       Reuse src/validation/redact.py for any published prompt text. Prompts may contain paths and emails, and logs/events.jsonl is already redacted by the hook.
     - Data building hooks into `make timeline` (a stub in the Makefile today) and is wired so `make report` or P7's `make site` can call it.
     - Every requirement needs tests tagged @pytest.mark.req("PROV-0x"). The explorer's traceability view shows PROV as red until they exist.
Files touched in P4: specs/P4-validation.md (VAL-01/02), specs/P5-provenance.md (PROV-02 categories), tests/conftest.py (test-run/2 + body sidecars),
  Makefile (test: --cov + attach-coverage; faults; report), .gitignore, src/validation/{__init__,runs,specs,redact,faults}.py,
  src/report/build_validation_data.py, src/report/claims.json, src/report/schemas/faults.schema.json, results/faults.json,
  results/tests/{bodies,coverage}/, site/validation/{index.html,style.css,app.js,data/**}, site/dashboard/app.js (Evidence links),
  tests/{test_runfile,test_makefile,test_dash_ui,test_dash_data,test_anl_clean,test_anl_inference,test_anl_descriptives,test_anl_rhetoric,
  test_val_specs,test_val_data,test_val_faults,test_val_claims,test_val_ui}.py, docs/{progress,review-log,HANDOFF}.md
Test status (command + result): `make test`: 508 passed (2026-11-08T08:43). `make faults`: 10/10 caught, 10/10 by behavioral tests.
Decisions (HUMAN/AGENT):
  HUMAN: VAL-01/02 store test bodies by content hash and keep every run. marked 12.0.2 + DOMPurify 3.1.6. Faults skip the UI tests except for F09.
  HUMAN: one claim per panel plus the headline tiles. Truth-derived files appear only on "Recovery vs. ground truth (validation only)".
  HUMAN: add behavioral tests for the golden-only faults (done: F01/F05/F07/F08/F09). Accepted the decoded-JSON privacy-test change.
  HUMAN: PROV-02 categories: human-typed ("[drafted by Aayush" marker) / automated (subagent reports, scheduled tasks, cross-session messages) / shared.
  AGENT: the explorer snapshot is the newest `make test` run; freshness is checked by rebuilding from manifest.run.
  AGENT: published test text is redacted with visible placeholders. Fault runs set PYTHONDONTWRITEBYTECODE=1 and exclude test_val_faults.py.
Key facts for P5:
  - After any code change, run `make test && make report` twice so the explorer snapshot is an all-green run.
  - Changing specs, review-log.md, claims.json or results/faults.json requires `make report`; spec text feeds the traceability view.
  - GitHub Pages is not enabled. P7 (PUB-02) deploys to https://aayushkeshari.github.io/genai-cs-policy/.
Open questions for Aayush:
  - PROV-02 wording: the P4 review log lists four categories (human-typed / drafted with Claude chat / automated / shared), but the spec now has
    three, with "[drafted by Aayush" defining human-typed. Should "drafted with Claude chat" be its own category, identified by that marker?
  - .phase → P5:planning.
  - Possible error in the committed P2 review-log entry (stance 0.76 vs macro-F1 0.741 / accuracy 0.761). Aayush chose to leave it.
Gotchas for the next session:
  - The project path has spaces, so quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = . (import src.*). Scratch scripts need PYTHONPATH=.
  - `make test` takes ~30 s, including the UI tests, which need the network (rare CDN stalls have timed out once). `make faults` takes ~2.5 min.
  - While building, run only the tests you're changing; run the full suite before each commit (Aayush's instruction).
  - Every top-level results/*.json needs a schema in src/report/schemas/ (ANL-09). The full coverage report lives at results/tests/coverage/latest.json (gitignored).
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md: the rules are frozen (SHA-256 test).
  - src/analysis/ and both src/report builders must never mention ground_truth or import src.evaluation (tested).
  - The dashboard's .panel-foot may hold only data-source links; Evidence links go below it.
  - When appending Aayush's text to docs/review-log.md, check for duplicates first (a double append happened once).
  - tests/conftest.py must contain only the plugin. Never edit logs/ or raw_logs/; hooks own them.
