# HANDOFF — overwritten at each /prep-clear
Updated: 2026-11-10T15:05:00-05:00
Current phase: P6 (token usage). TOK-01..04 and TOK-08 are built, and TOK-05 is amended to 1 run per condition and its analysis is built. P5 is done and pushed. .phase is "P6:writing-code".
Last completed task: `make tokens` gives results/tokens.json (393 messages, 61.7M tokens, phase join without gaps). 587 tests pass. Pushed.
NOW: Aayush is running the TOK-05 experiment (protocol below). If a prompt contains "TOK-05 run A", "TOK-05 run B" or "TOK-05 run C",
  do exactly the task it states, in scratch/tok05/<X>/ only. Ask no questions and do no other work. scratch/ is gitignored.
Next task, after the experiment (Aayush will say "experiment done"):
  1. Check that raw_logs/transcripts/ has the B session (copied at its SessionEnd), then `make tokens`.
  2. Check experiment.conditions A, B and C in results/tokens.json each have runs = 1 and messages > 0. If one is empty, report it and don't guess.
  3. Add the comparison to the progress log, then plan TOK-06 (docs/usage-limits.md) and TOK-07 (site/tokens/ page with charts plus Aayush's "what I learned").
     Load the dataviz skill before the charts. The page must state that n = 1 per condition and the comparison is anecdotal.
TOK-05 protocol (the same task text in every run; only the letter changes):
  A: in the current long session (no clear), send the task prompt with "TOK-05 run A".
  C: type /compact, then send the task prompt with "TOK-05 run C".
  B: type /clear, then /resume, then send the task prompt with "TOK-05 run B".
  End: type /clear (this copies B's transcript), then /resume and say "experiment done".
Files touched in P6: specs/P6-tokens.md (TOK-05), Makefile (tokens), src/tokens/{__init__,build_tokens}.py, src/report/schemas/tokens.schema.json,
  results/tokens.json, tests/{tokutil,test_tok_data}.py, .gitignore (scratch/), docs/{progress,HANDOFF}.md
Test status (command + result): `make test`: 587 passed (2026-11-10T15:0x). TOK-06/07 have no tests yet, so they show red in the explorer.
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
  - Subagent transcripts are not copied by the hook (1 so far, ~122k tokens). Open question for Aayush: change INST-04?
  - After any code change: `make test && make report` twice so the explorer snapshot is all-green.
  - GitHub Pages is not enabled. P7 (PUB-02) deploys to https://aayushkeshari.github.io/genai-cs-policy/.
Open questions for Aayush:
  - Copy subagent transcripts in the hook (INST-04 change)?
  - Possible error in the committed P2 review-log entry (stance 0.76 vs macro-F1 0.741 / accuracy 0.761). Aayush chose to leave it.
Gotchas for the next session:
  - The project path has spaces, so quote paths. Use .venv/bin/python (3.11). pytest has pythonpath = .
  - Never `git reset --hard` or `git checkout .`: it would roll back logs/events.jsonl, which the hooks own.
  - When writing progress.md prose, put tag words in backticks (`HUMAN:`, `REJECTED:`) or they count as tags.
  - Do NOT edit src/analysis/code_text.py or docs/codebook.md (frozen, SHA-256 test). tests/conftest.py must contain only the plugin.
