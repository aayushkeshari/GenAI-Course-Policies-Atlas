# P5 — Contributions and timeline (site/timeline/)

- **PROV-01** `make timeline` merges logs/events.jsonl, docs/progress.md, git log, and docs/review-log.md
  into `site/timeline/data/timeline.json`. Every item has ts, actor (HUMAN | CLAUDE | shared), phase, type, summary, and source.
- **PROV-02** Actor attribution rules: prompts, `human:` commits, review-log entries, and spec edits are HUMAN.
  Responses, `agent:` commits, and generated code are CLAUDE. Ambiguous items are labelled "shared"; never guess.
  Logged prompts are further classified: human-typed (the prompt starts with "Typed by me"); automated
  (subagent reports, scheduled tasks, cross-session messages); shared if unclear.
- **PROV-03** Timeline view: zoomable vertical timeline with filters for actor, phase, and type, and
  clear/compact markers.
- **PROV-04** Q&A view: each prompt paired with the response excerpt that followed it, searchable.
- **PROV-05** Contribution summary: counts per actor (prompts, approvals, rejected plans, spec edits,
  reviews, commits, lines changed), plus a short narrative that Aayush writes (docs/timeline-narrative.md).
  Approvals are the HUMAN decision tags in docs/progress.md. Rejected plans are the REJECTED: tags in
  docs/progress.md; history before that tag existed is shown as "not recorded".
- **PROV-06** Redaction pass before anything reaches site/: strip absolute home paths, emails, tokens, and keys.
  A test scans site/ for these patterns.
