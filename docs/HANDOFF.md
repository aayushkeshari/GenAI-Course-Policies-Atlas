# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-08T07:40:09-05:00
Current phase: P3 (findings dashboard). DASH-01..08 are implemented and tested. 425 tests pass. .phase is "P3:writing-code" (only Aayush changes it).
  Done: P2 review-log entry (5750dc4, pushed). Not pushed: 3b82ea8 (far-from limitation) and this checkpoint commit.
Last completed task: documented the "far from banning" coder error as a known limitation.
  - The dev half has no such wording (only "not prohibited", already covered by rule S+1-not-prohibited), so the rules were not changed.
  - Added the limitation to methods.md §6 and a caveat in the institution drilldown, each with a test.
Next task (exact, actionable):
  1. Tell Aayush P3 is ready for review.
     - Run `make serve` (http://127.0.0.1:8000/dashboard/).
     - Ask for a P3 review-log entry. If Aayush pastes one, append it verbatim to docs/review-log.md and commit it as `human: P3 review-log entry`.
     - Ask whether to push and whether .phase should move to P4.
  2. Once .phase is P4: read specs/P4-validation.md only and propose a P4 plan in chat. Write no code before approval.
     Constraints for the plan:
     - The validation explorer goes in site/validation/, with the same no-build/pinned-CDN/synthetic-banner rules as the dashboard.
     - VAL-01 run files already exist: results/tests/run-*.json, written by tests/conftest.py.
     - `make report` (src/report/build_site_data.py) is where P4 data building should hook in.
     - The truth-derived results kept out of site/data/ for P3 (recovery.json, rhetoric_recovery.json, coder_dev_eval.json) are P4's call; propose explicitly whether the validation explorer shows them.
Files touched in P3: Makefile (report, serve, setup), requirements.txt (playwright 1.63.0, greenlet, pyee),
  src/analysis/descriptives.py, specs/P2-analysis.md (ANL-05 text), src/report/{__init__,build_site_data}.py,
  src/report/schemas/descriptives.schema.json, results/descriptives.json, site/data/*.json (11), site/dashboard/{index.html,style.css,app.js},
  tests/{test_anl_descriptives,test_anl_methods,test_dash_data,test_dash_ui}.py, docs/{methods,progress,review-log,HANDOFF}.md, .phase
Test status (command + result): `make test`: 425 passed (2026-11-08T07:39). The UI tests need the network (Chart.js loads from the pinned CDN).
Decisions (HUMAN/AGENT):
  HUMAN: export trimmed institutions/courses/statements as "raw synthetic rows"; no ground-truth field in site/ (tested).
  HUMAN: ANL-05 gains census_region and overall groupings (P2 spec, schema and tests updated).
  HUMAN: `make report` builds site/data/; `make site` will call it in P7.
  HUMAN: Playwright is pinned, Chromium is installed by `make setup`, and the UI tests fail, never skip.
  HUMAN: the far-from negation is fixed only if dev has the pattern (it doesn't), so it is documented instead. Never tune on held-out.
  HUMAN: the P2 review-log entry stays exactly as committed in 5750dc4.
  AGENT: coder labels are exported as coded_*. Truth-derived recovery files are not in site/data/.
  AGENT: provenance: every displayed number is a <span data-src="file.json#/ptr" data-fmt>, every chart dataset has srcs, and the tests resolve them.
  AGENT: CDN pins are Chart.js 4.4.1 (cdnjs) and chartjs-chart-matrix 2.0.1 (jsdelivr). `make serve` is a minimal http.server (P7 may extend it).
Key facts for P4:
  - 13 charts / 11 panels / 8 tabs. 451 plotted values and 400+ text numbers are checked against results/ by tests/test_dash_ui.py.
  - The top-decile rhetoric gaps include at least one coder error (S0067, "Far from banning", coded −2).
Open questions for Aayush:
  - P3 review-log entry; push; .phase → P4.
  - Possible error in the committed P2 review-log entry: it gives stance as 0.76. The held-out stance macro-F1 is 0.741; accuracy is 0.761. Aayush chose to leave the entry as committed.
  - [P5] PROV-02: UserPromptSubmit also fires for scheduled tasks, background subagents and cross-session messages, so a logged prompt is not
    necessarily human-typed. Some "HUMAN" decisions were drafted with Claude chat. Decide before P5 planning.
Gotchas for the next session:
  - The project path has spaces, so quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = . (import src.*).
  - `make test` takes ~17 s (UI tests included). `make analysis` takes ~80 s.
  - Changing results/ or data/clean/ requires `make report`, then committing site/data/, or test_site_data_is_current fails.
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md: the rules are frozen (SHA-256 test).
  - src/analysis/ must never mention ground_truth or import src.evaluation. The same applies to src/report/build_site_data.py (tested).
  - methods.md must not quote decimals (test). Dashboard text must not hand-type digits: use num() with a JSON pointer (test).
  - tests/conftest.py must contain only the plugin. Helpers go in tests/hookutil.py and tests/datautil.py.
  - Never edit logs/ or raw_logs/. Hooks own them.
