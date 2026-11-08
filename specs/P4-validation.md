# P4 — Validation explorer (site/validation/)

Audience: a skeptical reviewer. The goal is evidence, not a green dashboard.

- **VAL-01** A conftest plugin writes `results/tests/run-<timestamp>.json` per run. For each test it records:
  nodeid, req_ids, phase, kind (unit/property/integration/recovery/ui/fault), status, duration_s,
  failure message, and `body_sha256`. The test's docstring and source code are stored once per content hash
  in the sidecar `results/tests/bodies/<body_sha256>.json`, which is written only if absent, so an unchanged
  test adds no new text. Run files from before this change (schema test-run/1) hold docstring and source
  inline; readers accept both formats.
- **VAL-02** Keep every run file and every body file. The explorer shows the latest run plus pass/fail history per test.
- **VAL-03** Traceability matrix: parse requirement lines from specs/*.md. Show requirement → tests → status.
  Requirements with no tests are shown in red. Coverage % from pytest-cov is shown per module.
- **VAL-04** Fault injection (`make faults`): on a temp copy of the repo, apply ≥8 deliberate bugs
  (e.g. flip a regression sign, skip dedupe, change seed handling, break a keyword rule, off-by-one in term index),
  run the suite, and record which tests caught each one. Report a fault detection rate. Uncaught faults are listed, not hidden.
- **VAL-05** Explorer UI: search; filter by phase, kind, status, and requirement; click a test to see its docstring,
  source, history, and linked spec text.
- **VAL-06** Claims page: each finding on the dashboard links to the tests that support it.
- **VAL-07** Renders `docs/review-log.md` (Aayush's manual reviews) next to the automated evidence.
- **VAL-08** The explorer's own data loading and filters have tests (Playwright).
