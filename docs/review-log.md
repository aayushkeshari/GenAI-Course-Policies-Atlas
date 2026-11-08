## 2026-11-08 — P0 instrumentation

**Manual hook test (done by me)**
- Ran /clear, /resume, 3 prompts, /compact, /exit, then checked logs/events.jsonl with tail.
- Saw SessionEnd(clear) → SessionStart(clear) with a new session_id, PreCompact(manual),
  my prompts with Stop excerpts, and SessionEnd(prompt_input_exit). All tagged P0:planning.
  No hook_errors.log. Transcript copies present in raw_logs/transcripts/.

**Docs cross-check of [S] facts (done by me, against code.claude.com/docs/en/hooks)**
- Confirmed: common fields, UserPromptSubmit prompt/session_title/30s timeout, Stop's
  last_assistant_message (docs say transcript may lag, so the design is right), stdout-to-context
  rule for UserPromptSubmit/SessionStart, SessionStart sources incl. fork, SessionEnd reasons,
  PreCompact manual/auto, SessionEnd 1.5s budget, file-watcher reload.
- Not verified (page section not retrieved): Stop's stop_hook_active/background_tasks/session_crons,
  PreCompact custom_instructions, "PreCompact stdout feeds the summary" (looks doubtful; harmless
  since the hook prints nothing).
- New: UserPromptSubmit also fires for scheduled tasks, background subagents, and cross-session
  messages, so not every logged prompt is human-typed. Flag for P5 attribution (PROV-02).

**Decisions**
- Phase from req prefix; redaction in hook (repo is public); raw_logs/ unredacted (gitignored, P6 needs exact data).

**Flagged**
- Known redaction gap: a key glued onto a preceding word (foosk-…) isn't caught.

**My take:** 
P0 does what I need. Every event I triggered showed up in order with the right phase tag, and Claude was upfront about 
which docs facts it hadn't verified instead of passing them off as confirmed. The redaction gap is acceptable for a
class project since I won't be pasting keys into prompts, but I want the UserPromptSubmit attribution
issue handled before P5 so the timeline doesn't credit me with prompts I didn't type.