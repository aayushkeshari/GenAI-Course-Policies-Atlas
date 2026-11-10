# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-10T15:38:00-05:00
Current phase: P7 (publish). PUB-01..05 are built and tested, and `make prepublish` passes. .phase is "P7:writing-code". P6 is closed (docs written, TOK-05 measured).
Last completed task: DATA-02 spec change, real university names on synthetic institutions, with the new banner on every page (progress entry 2026-11-10T15:38:00). 646 tests pass. Committed and pushed.
DATA-02 now: names from data/reference/real_universities.txt (`Name | ST`), assigned by a separate seeded shuffle and matched by state. CLAUDE.md still says names are fictional (Aayush's file).
Next task: Aayush sets Settings → Pages → Source = "GitHub Actions". Then confirm the "Deploy site to GitHub Pages" run succeeds and
  https://aayushkeshari.github.io/genai-cs-policy/ loads (`gh run list --workflow pages.yml`). Aayush writes docs/evaluation.md + the reflection.
  Then `make prepublish`, commit, push.
P7 files: site/index.html, site/evaluation/{index.html,app.js,style.css,evaluation.md}, src/publish/{__init__,prepublish}.py,
  .github/workflows/pages.yml, Makefile (site, all, prepublish), README.md, tests/test_pub.py, "All pages" link in the 4 section headers.
Files touched in P6: specs/P6-tokens.md (TOK-05), specs/P0-instrumentation.md (INST-04), .claude/hooks/log_event.py, Makefile (tokens),
  src/tokens/{__init__,build_tokens}.py, src/report/schemas/tokens.schema.json, results/tokens.json, site/tokens/{index.html,style.css,app.js,data/tokens.json},
  docs/usage-limits.md, tests/{tokutil,test_tok_data,test_tok_ui,test_log_event}.py, .gitignore (scratch/), docs/{progress,HANDOFF}.md
Test status (command + result): `make test`: 605 passed. All TOK requirements have tests.
Decisions (HUMAN/AGENT):
  HUMAN: TOK-05 = 1 run per condition, with the small sample stated. P5 keeps three prompt categories. timeline.json lives in site/timeline/data/.
  AGENT: a row = one unique message.id (entries repeat per content block: 896 entries, 393 ids). <synthetic> placeholders are skipped.
  AGENT: join = nearest earlier prompt in the same session. Rows before a session's first logged prompt take the session's first event's phase ("session-start", 36 rows, pre-hook P0).
    A session the hooks never saw uses the nearest prompt in any session ("any-session", none so far).
  AGENT: experiment rows = rows joined to any prompt containing "TOK-05 run X". Follow-ups for the same run should repeat the marker.
  AGENT: activity = the .phase suffix as logged. Only "planning" and "writing-code" have ever been logged. data/analysis/validation/docs appear only if .phase uses them.
Key facts:
  - raw_logs/ is gitignored, so token tests check the committed results/tokens.json. Fixture tests cover the parser.
  - The hook copies transcripts only at PreCompact and SessionEnd. The current session is not in raw_logs until one of those fires.
  - Subagent transcripts are copied to raw_logs/transcripts/subagents/<session>/ (INST-04, approved). The 1 existing one was backfilled.
  - After any code change: `make test && make report` twice so the explorer snapshot is all-green.
  - GitHub Pages: the workflow exists; it deploys only once Aayush sets Source = GitHub Actions. CI does not run tests (needs local logs); `make prepublish` is the gate.
  - Never put leak-like strings (/Users/, emails) in pytest parametrize IDs: redaction collapses the node IDs and `make report` fails.
Open questions for Aayush:
  - Write docs/tokens-learned.md (TOK-07 "what I learned"), and log any usage-limit events in docs/usage-limits.md.
  - Possible error in the committed P2 review-log entry (stance 0.76 vs macro-F1 0.741 / accuracy 0.761). Aayush chose to leave it.
Gotchas for the next session:
  - The project path has spaces, so quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = .
  - Never `git reset --hard` or `git checkout .`: it would roll back logs/events.jsonl, which the hooks own.
  - When writing progress.md prose, put tag words in backticks (`HUMAN:`, `REJECTED:`) or they count as tags.
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md (frozen, SHA-256 test). tests/conftest.py must contain only the plugin.
