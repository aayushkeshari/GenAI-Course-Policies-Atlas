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

## 2026-11-08: P1 synthetic data

**Data check**
- Looked at sample rows from institutions.csv, courses.csv, statements.csv.
- Institution names read as fictional. Course rows are consistent: policy-0 rows have no tools
  or allowed uses; blanked-policy rows have all policy-derived fields blank, assessment_adaptation kept.
- Planted mess is visible: "Intro" vs "intro" casing, out-of-place duplicate rows.

**Real-university list spot-check**
- All 159 entries are real US schools with CS programs; no duplicates.
- Limitation: the DATA-02 test only catches exact matches to these 159 names, so a collision with
  a school not on the list would pass. Low risk, since the names are built from invented words.

**Decisions**
- Statement text was too repetitive (3 variants per label) to be a real test of the P2 coder.
  Raised to 9 phrasings per bank, with negations, hedges, keyword traps, and phrasings reserved
  for the held-out half.
- DATA-16 rewrite accepted as a fair fix (the strict per-level version was flaky). Added a
  Cochran-Armitage trend test; it passes on 5/5 seeds (|z| ≈ 17–18).
- Added ANL-14: P2 must account for institution clustering, because the public/private null can
  look like an effect without it.
- 7 terms (fall + spring); missing policy blanks all policy-derived fields.

**Note:** the progress log records these decisions as plain "HUMAN". They were drafted with
Claude chat; my prompts in logs/events.jsonl carry the tag.

**My take:** 
The data is messy in the ways the spec asked for, and the planted effects are documented with exact parameters, so P2 has a real target to hit. Upgrading the statement text was the most important change. Without it, the coder's accuracy score would have looked good without proving anything.
