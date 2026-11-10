# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-10T15:13:55-05:00
Current phase: P6. All TOK requirements are built and tested. The TOK-05 experiment is done: A, B and C are measured with 1 run each, and the comparison is in progress.md. .phase is "P6:writing-code".
Last completed task: TOK-05 results written up (entry at 2026-11-10T15:13:55). 605 tests pass. Committed and pushed.
TOK-05: A total 1.72M tokens, B 214k, C 253k (n = 1, anecdotal). Run B skipped /resume. This is noted as a deviation, and Aayush kept the run.
Next task: Aayush writes docs/tokens-learned.md and logs any usage-limit events. Then `make tokens && make test && make report`, then close P6 / start P7 (PUB).
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
  - GitHub Pages is not enabled. P7 (PUB-02) deploys to https://aayushkeshari.github.io/genai-cs-policy/.
Open questions for Aayush:
  - Write docs/tokens-learned.md (TOK-07 "what I learned"), and log any usage-limit events in docs/usage-limits.md.
  - Possible error in the committed P2 review-log entry (stance 0.76 vs macro-F1 0.741 / accuracy 0.761). Aayush chose to leave it.
Gotchas for the next session:
  - The project path has spaces, so quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = .
  - Never `git reset --hard` or `git checkout .`: it would roll back logs/events.jsonl, which the hooks own.
  - When writing progress.md prose, put tag words in backticks (`HUMAN:`, `REJECTED:`) or they count as tags.
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md (frozen, SHA-256 test). tests/conftest.py must contain only the plugin.
