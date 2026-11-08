# P0 — Instrumentation (build first)

Purpose: from the first real task onward, capture everything P5 (provenance) and P6 (tokens) need.

- **INST-01** `.claude/settings.json` registers command hooks for UserPromptSubmit, Stop, PreCompact,
  SessionStart, and SessionEnd, all calling `.claude/hooks/log_event.py` via `$CLAUDE_PROJECT_DIR`.
- **INST-02** `log_event.py` reads hook JSON from stdin and appends one line to `logs/events.jsonl`:
  `{ts (ISO, local tz), event, session_id, phase (contents of .phase or "untagged"), payload}`.
  - UserPromptSubmit: payload.prompt = full prompt text
  - Stop: payload.response_excerpt = the last assistant text in transcript_path (first 1,000 chars)
  - PreCompact: payload.trigger (manual/auto)
  - SessionStart: payload.source (startup/resume/clear/compact)
  - SessionEnd: payload.reason
- **INST-03** The hook never blocks Claude Code. It always exits 0, writes nothing to stdout on
  UserPromptSubmit (stdout there is injected into context), and logs its own errors to `logs/hook_errors.log`.
- **INST-04** On SessionEnd and PreCompact, copy the session transcript to `raw_logs/transcripts/`
  (gitignored) so token data survives local cleanup of transcripts.
- **INST-05** Before writing the hook, check the current Claude Code hooks docs for exact field names
  and record what you confirmed in docs/progress.md.
- **INST-06** Makefile targets (stubs are fine for now): `data analysis test report tokens timeline site serve clean`.
- **INST-07** `make test` runs pytest and writes a machine-readable run file to `results/tests/` (format in P4).
- **INST-08** Tests for log_event.py feed it sample JSON for each event type and check the output lines.

Manual check (Aayush): send 3 prompts, run `/compact`, run `/clear`. Then confirm events.jsonl
contains all of it in the right order with phase tags.
