# P6 — Token usage (site/tokens/)

- **TOK-01** Before writing the parser, inspect one real transcript in raw_logs/transcripts/ and record the
  actual usage field names in docs/progress.md (expected: input, output, cache-creation, and cache-read tokens per assistant message).
- **TOK-02** `make tokens` produces one row per assistant message: ts, session_id, model, the four token counts,
  and phase/activity (joined from the nearest preceding UserPromptSubmit event in logs/events.jsonl).
- **TOK-03** Session boundaries: mark /clear (SessionStart source=clear) and /compact (PreCompact) events.
- **TOK-04** Metrics: totals by phase and by activity (planning, data, analysis, writing-code, validation, docs);
  tokens per prompt; context size per turn (input + cache tokens), which should show a sawtooth at clears/compacts;
  cache-read share.
- **TOK-05** Experiment (Aayush picks a comparable small task, e.g. "add one chart"): run it in condition A,
  a long session with no clear; condition B, right after /clear + /resume; and condition C, right after /compact.
  Run each condition once (1 run per condition, per Aayush). Report the comparison and state plainly that the
  sample is small: with n = 1 per condition the differences are anecdotal, not evidence.
- **TOK-06** Usage-limit events on the Pro plan get logged by hand in docs/usage-limits.md and shown on the page.
- **TOK-07** Page: charts for the above, plus a "what I learned" section that Aayush writes.
- **TOK-08** Tests: parser on a fixture transcript; totals equal the sum of rows; the phase join has no gaps.
