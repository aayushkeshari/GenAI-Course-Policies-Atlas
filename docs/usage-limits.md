# Usage-limit events (TOK-06)

Logged by hand by Aayush whenever the Pro plan's usage limit is hit or warned about. `make tokens` reads this
table and the tokens page shows it. One row per event. Use an ISO time (`date -Iseconds`), and keep the
columns as they are.
| When | Plan | What happened | Phase | Notes |
|---------------------------|-----|-----------------------------------------------------|----|----------------------------------------------------------------------|
| 2026-11-10T18:08:00-05:00 | Pro | Usage limit reached; Claude Code paused until 19:20 | P7 | Hit while writing the evaluation, reflection, and timeline narrative |