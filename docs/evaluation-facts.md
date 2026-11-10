# Evaluation facts (G1–G5)

Collected by the agent on 2026-11-10 at HEAD `5ceb95f` (plus this commit), for Aayush's evaluation in
`docs/evaluation.md`. This page lists facts and their sources only, with no judgments.

**Data note:** synthetic data. Real university names are attached to invented policies and statements. Nothing here
describes what these schools actually do. The timeline and token figures are real project history.

**Local URLs** work after `make serve` (http://127.0.0.1:8000/). The live site will be
https://aayushkeshari.github.io/genai-cs-policy/. It is not yet deployed: GitHub Pages is not enabled, and the
Pages API returned 404 on 2026-11-10.

## Project-wide test facts

Source: the newest run file, `results/tests/run-20261110T153717.597660-0500.json`, and `site/validation/data/`.

| Fact | Value |
|---|---|
| Tests in the newest `make test` run | 646, all passed (41.4 s) |
| Test files | 33 |
| Test kinds | unit 536, ui 70, recovery 18, integration 16, property 3, fault 3 |
| Requirements traced | 75. All 75 have status "passing" in `traceability.json` |
| Archived `make test` runs | 149 files in `results/tests/` |
| Line coverage of `src/` (snapshot run) | 93.82% (1,877 statements, 116 missing) |
| Fault injection (`results/faults.json`) | 10 of 10 faults caught (detection rate 1.0). Behavioural tests alone also caught 10 of 10 |
| Fault-run provenance | Generated 2026-11-08T08:40:06-05:00 at commit `ac34740`, with 453 tests (497 with UI tests). Not rerun since |

Tests per requirement group (a test tagged with several groups counts once in each):

| Group | Phase | Requirements | Tests |
|---|---|---|---|
| INST | P0 | 9 | 97 |
| DATA | P1 | 17 | 151 |
| ANL | P2 | 14 | 166 |
| DASH | P3 | 8 | 26 |
| VAL | P4 | 8 | 78 |
| PROV | P5 | 6 | 63 |
| TOK | P6 | 8 | 31 |
| PUB | P7 | 5 | 37 |

## G1: Synthetic data, analysis and dashboard

**Evidence**
- Specs: `specs/P1-data.md`, `specs/P2-analysis.md`, `specs/P3-dashboard.md`
- Data: `data/raw/{institutions,statements,courses}.csv`, `data/raw/ground_truth.json`, `data/clean/`, `docs/data-dictionary.md`
- Code: `src/data/generate.py`, `src/analysis/`, `src/evaluation/`, `src/report/build_site_data.py`
- Results: `results/{descriptives,allowed_uses,assessment,association,regression,rhetoric,coder_eval,kappa,recovery,rhetoric_recovery}.json`
- Docs: `docs/methods.md`, `docs/codebook.md`, `data/reference/hand_code_sample.csv`
- Page: `site/dashboard/`, at http://127.0.0.1:8000/dashboard/

**Counts and figures**
- Tests: DATA 151, ANL 166, DASH 26, for 39 requirements.
- Data size: 150 institutions, about 350 statements, about 2,000 course-term rows (`docs/data-dictionary.md`).
- Faults F01–F09 target G1 code (data, cleaning, coding, analysis, evaluation and site export). All 9 were caught.
- Rule-based text coder (`results/coder_eval.json`):

| Split | n | Macro-F1 (mention codes) | Stance accuracy | Stance macro-F1 |
|---|---|---|---|---|
| dev | 168 | 1.0 | 1.0 | 1.0 |
| held-out | 180 | 0.829 | 0.761 | 0.741 |
| held-out, reserved phrasings | 127 | 0.755 | 0.701 | 0.677 |
| held-out, no reserved phrasings | 53 | 0.968 | 0.906 | 0.871 |

- Hand-coded sample (`results/kappa.json`, n = 30, unweighted Cohen's kappa):

| Code | Aayush vs coder | Aayush vs truth |
|---|---|---|
| stance | 0.649 | 0.894 |
| mentions_integrity | 0.500 | 1.0 |
| mentions_careers | 0.462 | 1.0 |
| mentions_collaboration | 1.0 | 1.0 |

- Rhetoric-gap recovery (`results/rhetoric_recovery.json`, ANL-13): 22 flagged, precision 0.929, recall 0.684.
- Planted-effect recovery (`results/recovery.json`): `coverage.all_met` is true for the planted effects across the seeds.

## G2: Validation explorer

**Evidence**
- Spec: `specs/P4-validation.md`
- Code: `src/validation/`, `src/report/build_validation_data.py`, `tests/conftest.py` (run-file plugin)
- Data: `results/tests/run-*.json` (149 runs), `results/tests/coverage/`, `results/faults.json`, `docs/review-log.md`
- Page: `site/validation/`, at http://127.0.0.1:8000/validation/

**Counts**
- Tests: VAL 78, for 8 requirements.
- Fault injection: 10 faults, 10 caught. Tests catching each fault: F01 3, F02 8, F03 2, F04 3, F05 4, F06 2, F07 2, F08 2, F09 2, F10 1.
- Golden-only catches (caught only by byte-comparison tests): 0.
- Review-log entries in `docs/review-log.md`: 5.

## G3: Contribution record

**Evidence**
- Spec: `specs/P5-provenance.md`
- Sources: `logs/events.jsonl` (hook events), `git log` (71 commits), `docs/progress.md` (55 entries), `docs/review-log.md`
- Code: `src/provenance/build_timeline.py`, `.claude/hooks/log_event.py`
- Page: `site/timeline/`, at http://127.0.0.1:8000/timeline/. The data is `site/timeline/data/timeline.json` (301 items, head `5ceb95f`)

**Counts**
- Tests: PROV 63, for 6 requirements.
- Per-actor counts (`timeline.json` → `summary.per_actor`):

| Measure | HUMAN | CLAUDE | shared |
|---|---|---|---|
| Prompts | 57 | 0 | 0 |
| Responses | 0 | 61 | 0 |
| Commits | 8 | 60 | 3 |
| Lines added (commits) | 530 | 20,103 | 28 |
| Lines removed (commits) | 34 | 720 | 6 |
| Spec edits | 23 | 0 | 8 |
| Reviews (`docs/review-log.md`) | 5 | 0 | 0 |
| Approvals (HUMAN tags in progress.md) | 56 | — | — |
| Rejected plans (REJECTED tags) | 1 | — | — |

- Agent decisions (AGENT tags in progress.md): 93. Q&A pairs: 55. Unanswered prompts: 2.
- Prompt categories: human-typed 0, automated 0, shared 57.

How the counts are defined (from `summary.rules`):
- Lines changed are from each actor's commits, attributed by commit prefix: `agent:` to CLAUDE, `human:` to HUMAN, anything else to shared. Generated and hook-owned paths are excluded: logs/, raw_logs/, data/, results/, site/data/, site/validation/data/ and site/timeline/data/.
- REJECTED tags were recorded only from 2026-11-10T14:27:58-05:00. Earlier rejections were not logged.

## G4: Token usage

**Evidence**
- Spec: `specs/P6-tokens.md`
- Data: `results/tokens.json`, built 2026-11-10 15:17 from 9 transcripts, 1 subagent transcript and 131 hook events
- Docs: `docs/tokens-learned.md`, `docs/usage-limits.md` (no usage-limit events recorded)
- Code: `src/tokens/build_tokens.py`
- Page: `site/tokens/`, at http://127.0.0.1:8000/tokens/

**Counts**
- Tests: TOK 31, for 8 requirements.
- Coverage limits: P7 sessions are not included, because a session's transcript is copied only at /compact or when the session ends. 4 messages are subagent (sidechain) messages.
- Boundaries logged: 6 /clear and 2 /compact.
- Largest context drop at a boundary: 323,040 to 39,242 tokens (/clear, 2026-11-08).

Token totals by phase:

| Phase | Messages | Input | Output | Cache creation | Cache read | Total | Cache-read share |
|---|---|---|---|---|---|---|---|
| P0 | 47 | 108 | 65,234 | 153,351 | 2,957,561 | 3,176,254 | 95.1% |
| P1 | 60 | 134 | 101,244 | 125,923 | 6,414,948 | 6,642,249 | 98.1% |
| P2 | 74 | 172 | 143,578 | 201,479 | 16,460,439 | 16,805,668 | 98.8% |
| P3 | 80 | 182 | 101,733 | 177,977 | 10,466,435 | 10,746,327 | 98.3% |
| P4 | 137 | 288 | 160,720 | 787,802 | 23,559,849 | 24,508,659 | 96.8% |
| P5 | 70 | 146 | 112,614 | 172,099 | 8,776,843 | 9,061,702 | 98.1% |
| P6 | 40 | 92 | 55,386 | 121,252 | 7,592,962 | 7,769,692 | 98.4% |
| **Total** | 508 | 1,122 | 740,509 | 1,739,883 | 76,229,037 | 78,710,551 | 97.8% |

- By activity: planning had 396 messages and 54,998,344 tokens. Writing-code had 112 messages and 23,712,207 tokens.
- By model: claude-opus-5-5 had 504 messages and 78,588,239 tokens. claude-haiku-5-5 had 4 messages and 122,312 tokens.

TOK-05 experiment (task: one standalone bar chart of the policy-level shares; 1 run per condition):

| Condition | Messages | Output | Cache creation | Cache read | Total | First context | Peak context | Cache-read share |
|---|---|---|---|---|---|---|---|---|
| A: long session, no clear | 8 | 5,992 | 11,473 | 1,703,562 | 1,721,047 | 208,184 | 219,556 | 99.3% |
| B: after /clear | 5 | 3,096 | 17,697 | 193,413 | 214,216 | 39,509 | 45,016 | 91.6% |
| C: after /compact | 4 | 2,501 | 37,933 | 212,907 | 253,349 | 60,097 | 65,252 | 84.9% |

- Output files: A 7.8 KB, B 3.6 KB, C 3.3 KB (`scratch/tok05/`, gitignored).
- Two earlier attempts were excluded as invalid: event line 111 (C, no /compact before it) and line 113 (B, the session did not start with /clear).
- Run B was sent right after /clear, without /resume. Aayush kept the run with this deviation noted.
- Caveat recorded in `results/tokens.json`: n = 1 per condition, so the differences are anecdotal.
- Recorded figure mismatch: `docs/tokens-learned.md` states "97.6% of the project's 61.8M tokens", while `results/tokens.json` reports 97.8% of 78,710,551.

## G5: Published

**Evidence**
- Spec: `specs/P7-publish.md`
- Site: `site/index.html` (landing page) and `site/evaluation/` (renders `docs/evaluation.md` unedited). Local URLs: http://127.0.0.1:8000/ and http://127.0.0.1:8000/evaluation/
- Deploy: `.github/workflows/pages.yml` (push to main → GitHub Pages)
- Gate: `make prepublish` → `src/publish/prepublish.py`
- `README.md` and `make all`
- Repository: https://github.com/aayushkeshari/genai-cs-policy

**Counts and status**
- Tests: PUB 37, for 5 requirements.
- Last prepublish result: "prepublish: OK (6 pages: redaction clean, links resolve, synthetic banner on every page)".
- Pages deployment: not enabled. Settings → Pages → Source has not been set to GitHub Actions. The 3 "Deploy site to GitHub Pages" runs so far (pushes of `c9217ed`, `91a4785` and `5ceb95f`) all ended in failure.
- `docs/evaluation.md` is still the unfilled template (goal table and reflection heading only).
