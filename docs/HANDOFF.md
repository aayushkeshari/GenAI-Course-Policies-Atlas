# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-10T14:41:00-05:00
Current phase: P5 (contribution timeline) is implemented. PROV-01..06 are all passing in the explorer's traceability view, and everything is pushed. .phase is "P5:writing-code" (only Aayush changes it).
Last completed task: P5 step 4. Rebuilt the timeline and explorer data, ran the full suite, pushed.
Next task (exact, actionable):
  1. Aayush reviews P5: page at http://127.0.0.1:8000/timeline/ after `make serve`. He may add docs/timeline-narrative.md, then `make timeline`.
  2. Answer the open questions below. Then Aayush writes the P5 review-log entry and sets .phase to P6:planning.
  3. P6: read specs/P6-tokens.md only and propose a plan.
Files touched in P5: specs/P5-provenance.md (PROV-01/02/05 wording), CLAUDE.md (REJECTED: rule), Makefile (timeline),
  src/provenance/{__init__,build_timeline}.py, src/provenance/timeline.schema.json, site/timeline/data/timeline.json, site/timeline/{index.html,style.css,app.js},
  tests/{provutil,test_prov_data,test_prov_ui}.py, docs/{progress,HANDOFF}.md. (Dashboard tests untouched: timeline.json moved out of site/data/.)
Test status (command + result): `make test`: 571 passed (2026-11-10T14:40). `make faults` was not rerun in P5 (no analysis code changed).
Decisions (HUMAN/AGENT):
  HUMAN: keep three prompt categories (confirmed 2026-11-10). timeline.json lives in site/timeline/data/ (spec change); dashboard test exemptions reverted.
  HUMAN: categories are human-typed ("Typed by me" prefix) / automated / shared. Actor is HUMAN | CLAUDE | shared.
  HUMAN: approvals = HUMAN decision tags in progress.md. Rejected plans = `- REJECTED:` bullets, "not recorded" before 2026-11-10. Narrative goes in docs/timeline-narrative.md.
  AGENT: spec edits in commits with neither agent:/human: prefix (the 3 early claude-chat: commits) are shared. Spec edits in agent: commits are HUMAN.
  AGENT: a commit's phase = phase named in its subject, else the last earlier hook event's .phase, else "unknown". Review entries are timed by the commit that added the heading.
  AGENT: lines changed exclude logs/, raw_logs/, data/, results/, site/data/, site/validation/data/.
  AGENT: make timeline is NOT part of make report (events.jsonl grows every prompt). P7's make site should call it.
Key facts for P6/P7:
  - timeline.json is real project history: "synthetic": false, with the banner saying so. The schema is in src/provenance/ (src/report/schemas/ is 1:1 with results/*.json per ANL-09).
  - test_committed_timeline_matches_a_fresh_build allows newer items in a fresh build, but every committed item must be unchanged. If you change the builder, run `make timeline` before committing.
  - After any code change: `make test && make report` twice so the explorer snapshot is all-green.
  - GitHub Pages is not enabled. P7 (PUB-02) deploys to https://aayushkeshari.github.io/genai-cs-policy/.
Open questions for Aayush:
  - Currently 0 prompts are human-typed: no logged prompt starts with "Typed by me", so all 43 are "shared".
  - Carried from P2: possible error in the committed P2 review-log entry (stance 0.76 vs macro-F1 0.741 / accuracy 0.761). Aayush chose to leave it.
Gotchas for the next session:
  - The project path has spaces, so quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = . (import src.*).
  - `make test` takes ~40 s including the UI tests, which need the network for the explorer's CDN libraries. `make faults` takes ~2.5 min.
  - While building, run only the tests you're changing; run the full suite before each commit (Aayush's instruction).
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md: the rules are frozen (SHA-256 test).
  - src/analysis/ and both src/report builders must never mention ground_truth or import src.evaluation (tested).
  - When writing progress.md prose, put tag words in backticks (`HUMAN:`, `REJECTED:`) or they count as tags.
  - tests/conftest.py must contain only the plugin. Never edit logs/ or raw_logs/; hooks own them.
