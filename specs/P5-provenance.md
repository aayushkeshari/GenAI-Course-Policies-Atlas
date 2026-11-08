# P5 — Contributions and timeline (site/timeline/)

- **PROV-01** `make timeline` merges logs/events.jsonl, docs/progress.md, git log, and docs/review-log.md
  into `site/data/timeline.json`. Every item has ts, actor (HUMAN/CLAUDE), phase, type, summary, and source.
- **PROV-02** Actor attribution rules: prompts, `human:` commits, review-log entries, and spec edits are HUMAN.
  Responses, `agent:` commits, and generated code are CLAUDE. Ambiguous items are labelled "shared"; never guess.
- **PROV-03** Timeline view: zoomable vertical timeline with filters for actor, phase, and type, and
  clear/compact markers.
- **PROV-04** Q&A view: each prompt paired with the response excerpt that followed it, searchable.
- **PROV-05** Contribution summary: counts per actor (prompts, approvals, rejected plans, spec edits,
  reviews, commits, lines changed), plus a short narrative that Aayush writes.
- **PROV-06** Redaction pass before anything reaches site/: strip absolute home paths, emails, tokens, and keys.
  A test scans site/ for these patterns.
