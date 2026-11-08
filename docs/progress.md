# Progress log (append-only, timestamps from `date -Iseconds`)

## 2026-11-08T04:16:47-05:00 — [P0] Step 1: confirm hooks docs (INST-05) + add INST-09

**What changed**
- Read https://code.claude.com/docs/en/hooks against Claude Code 2.1.319, using a web-fetch subagent. Findings are below.
- Added INST-09 (redaction in the hook) to specs/P0-instrumentation.md. Aayush asked for it.
- No code yet.

### Hooks docs confirmed
Reliability: [V] means verbatim from the page. [S] means it came from a model-extracted summary of a page section and is not yet verified verbatim. Aayush verifies this independently in review-log.md.

- **Common stdin fields (all events)** [S]: `session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`. These are confirmed by a verbatim example input for another event [V].
- **UserPromptSubmit** [S]: `prompt` holds the submitted text. Optional `session_title`. No matcher support [V].
  - Exit 0: plain stdout is **added to Claude's context** [S]. The hook must print nothing (INST-03).
- **Stop** [S]: `stop_hook_active`, `last_assistant_message`, `background_tasks`, `session_crons`.
  - `last_assistant_message` "contains the text content of Claude's final response, so hooks can access it without parsing the transcript file". No matcher support [V].
  - Decision: use `last_assistant_message`. Fall back to reading `transcript_path` only if it is missing.
- **PreCompact** [S]: `trigger` (`manual` | `auto`) and `custom_instructions` (null when auto). Matcher values: `manual`, `auto` [V].
  - Exit 0: stdout feeds the compaction summary [S]. The hook will print nothing.
- **SessionStart** [S]: `source`, plus optional `model`, `agent_type`, `session_title`.
  - Values [V]: `startup`, `resume`, `clear`, `compact`, **`fork`**. `fork` is not in the spec's list. The hook records whatever value arrives.
  - Exit 0: stdout added to context [S].
- **SessionEnd** [S]: `reason`. Values [V]: `clear`, `resume`, `logout`, `prompt_input_exit`, `other`.
- **Exit codes** [S]: 0 means OK. 2 blocks the prompt, the stop, or the compaction. Any other non-zero code is a non-blocking error. The hook always exits 0 (INST-03).
- **settings.json shape** [V]: `{"hooks": {"<Event>": [{"matcher": "...", "hooks": [{"type": "command", "command": "...", "timeout": N}]}]}}`.
  - A matcher on an event that doesn't support one is silently ignored [V]. We omit matchers, which matches everything.
- **$CLAUDE_PROJECT_DIR** [V]: "In shell form, wrap it in double quotes". The project path contains spaces, so the command is `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/log_event.py"`.
- **Timeouts** [V]: the command default is 600s, lowered to 30s on UserPromptSubmit. **SessionEnd hooks share a 1.5s budget**, raised to the per-hook `timeout` if one is set, up to 60s.
  - Decision: set `"timeout": 10` on SessionEnd so the transcript copy can't be cut off.
- **Reload** [S]: edits to hooks in settings files are "normally picked up automatically by the file watcher". The manual check will still be done in a fresh session.

**Tests run**: none (no code yet).

**Decisions**
- HUMAN: phase comes from the requirement-ID prefix.
- HUMAN: `@pytest.mark.kind` marks test kind, default `unit`.
- HUMAN: INST-05 is tested by a progress.md section check, plus a manual review entry.
- HUMAN: add redaction to the hook (INST-09).
- AGENT: use `last_assistant_message` with a transcript fallback.
- AGENT: SessionEnd timeout of 10s.
- AGENT: transcript copies in raw_logs/ are verbatim (not redacted), because they're gitignored and P6 needs the exact token data.

**Open questions**
- Should `fork` be added to the spec's SessionStart source list? (Spec-text change only. The hook already handles it.)
- Resolved at 2026-11-08T04:16:47-05:00 follow-up. HUMAN: add `fork` to the SessionStart source list in the spec (done). HUMAN: keep raw_logs/ unredacted. Answers were drafted with Claude chat at the instructor's request.
