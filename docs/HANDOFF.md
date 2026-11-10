# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-10T15:06:57-05:00
Current phase: P6. TOK-01..04, 06, 07 and 08 are built and tested. TOK-05 analysis is built, but the experiment is incomplete. INST-04 now copies subagent transcripts. .phase is "P6:writing-code".
Last completed task: tokens page site/tokens/ (make serve, then http://127.0.0.1:8000/tokens/). 605 tests pass. Pushed.
TOK-05 status (from results/tokens.json): A = valid run logged at events line 109 but "awaiting transcript" (its session 748a356f
  isn't copied to raw_logs/ until it compacts or ends). B and C = not run. Lines 111 (C) and 113 (B) are excluded: they were sent with no compact or clear.
If a prompt contains "TOK-05 run B" or "TOK-05 run C": do exactly that task in scratch/tok05/<X>/ only. Ask no questions and do no other work.
Next task (Aayush must type the slash commands into the prompt box; text in a message does not run them):
  1. /compact (this also copies the session transcript, so run A becomes measurable), then send the run C prompt.
  2. /clear, then /resume, then send the run B prompt.
  3. /clear, then /resume, then "experiment done". Then: `make tokens`, check A/B/C status = measured with runs = 1,
     write the comparison in progress.md with the n = 1 caveat, `make test` + `make report`, commit, push.
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
