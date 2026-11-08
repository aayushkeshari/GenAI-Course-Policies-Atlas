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

## 2026-11-08T04:19:34-05:00 — [P0] Step 2: pinned deps, pytest config, venv

**What changed**
- `.venv` created with Python 3.11.
- `requirements.txt` pins pytest 9.2.0, pytest-cov 7.1.0, and every transitive dependency to exact versions.
- `pytest.ini` sets `testpaths = tests` and `--strict-markers`, and registers the `req` and `kind` markers. A typo in a marker name now fails the run instead of quietly dropping the test from traceability.

**Tests run**
- `.venv/bin/python -m pytest -q` exited with 5 (no tests collected). This is expected: `tests/` doesn't exist yet.

**Decisions**
- AGENT: build the venv on 3.11, the minimum the project allows, so the pins are known to work there.
- AGENT: pin transitive deps too, for reproducibility.
- AGENT: the hook itself stays stdlib-only and runs under the system `python3`, not the venv.

**Open questions**: none.

## 2026-11-08T04:25:33-05:00 — [P0] Step 4: log_event.py hook with redaction (INST-02/03/04/08/09)
(Done before step 3, so settings.json never points at a missing script and each commit works if checked out.)

**What changed**
- Added `.claude/hooks/log_event.py`, stdlib only. It appends one redacted JSON line per event to `logs/events.jsonl` with the fields `{ts, event, session_id, phase, payload}`.
  - Stop uses `last_assistant_message`. If that's missing, it falls back to the last assistant text in the transcript. It redacts first and then cuts to 1,000 chars, so a key at the boundary can't leak as a fragment.
  - PreCompact and SessionEnd copy the transcript verbatim to `raw_logs/transcripts/<session_id>.jsonl`. The session_id is sanitized first.
  - Every error goes to `logs/hook_errors.log`, redacted.
  - stdout is pointed at /dev/null, and the script exits through `os._exit(0)`.
- Added `tests/hookutil.py`, `tests/test_log_event.py` and `tests/test_redaction.py`.

**Tests run**
- `.venv/bin/python -m pytest -q`: 70 passed.
- One earlier failure was a wrong test, not a hook bug. The test glued a token straight onto word characters (`xxxsk-ant…`), and the `\b` boundary is deliberate. I fixed the test input and added a "task-management-system" lookalike test.
- Manual smoke test under /usr/bin/python3 3.9.6 and Homebrew 3.14 passed.

**Decisions**
- AGENT: ts uses millisecond precision for ordering in P6.
- AGENT: unknown events are logged with an empty payload rather than dropped.
- AGENT: token patterns need 16+ chars after the prefix and a word boundary in front.
  - Known limitation: a key glued to the preceding word chars (e.g. `foosk-…`) is not redacted.
  - Home paths inside URLs (`example.com/Users/x`) are deliberately left alone.

**Open questions**: none.

## 2026-11-08T04:25:33-05:00 — [P0] Step 3: register hooks in .claude/settings.json (INST-01)

**What changed**
- Added `.claude/settings.json`. It registers UserPromptSubmit, Stop, PreCompact, SessionStart and SessionEnd, each calling `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/log_event.py"`. The path is quoted because the project path contains spaces.
- No matchers are set, because these events match everything when no matcher is given.
- SessionEnd has `timeout: 10`.
- Added `tests/test_settings.py`. Besides checking the structure, it runs the exact registered command string through `/bin/sh` from a temp project dir whose path contains spaces.

**Tests run**
- `.venv/bin/python -m pytest -q`: 70 passed.

**Decisions**
- AGENT: use bare `python3` from PATH, not the venv, since the hook is stdlib only and works on 3.9+.

**Open questions**
- The hooks did not start firing in this session (no `logs/` yet). The manual check must run in a fresh session.

## 2026-11-08T04:25:57-05:00 — [P0] Step 5: Makefile (INST-06)

**What changed**
- Added a `Makefile` with the targets `data analysis test report tokens timeline site serve clean`, plus `setup`, which creates the venv.
  - Every target except `test` is an echo stub that names the phase that will fill it in.
  - `clean` removes caches only.
- Added `tests/test_makefile.py`.

**Tests run**
- `make test`: 81 passed.

**Decisions**
- AGENT: added a `setup` target that the spec doesn't list.
- AGENT: `clean` never deletes logs/, raw_logs/ or results/, and a test enforces this.

**Open questions**: none.

## 2026-11-08T04:27:30-05:00 — [P0] Step 6: run-file plugin (INST-07, VAL-01 format)

**What changed**
- Added `tests/conftest.py`, a plugin that writes `results/tests/run-<YYYYMMDDTHHMMSS.ffffff±zzzz>.json` for every pytest run.
  - Each test entry records nodeid, req_ids, phase, kind, status, duration_s, failure_message, docstring, source, file and line.
  - The run as a whole records the schema version, start and end times, exit status, Python version, git commit and dirty flag, the current `.phase`, the args, a status summary and collection errors.
- Added `-p pytester` to pytest.ini.
- Added `tests/test_runfile.py`. It copies the conftest source into an isolated pytester project and runs it in a subprocess, covering pass, fail, skip, setup error, xfail, collection error, home-path scrubbing and one file per run.

**Tests run**
- `make test`: 88 passed.
- The real run file covers INST-01/02/03/04/06/07/08/09. INST-05 is still missing; step 8 adds it.

**Decisions**
- HUMAN: phase comes from the first req ID's area prefix.
- HUMAN: kind comes from `@pytest.mark.kind`, default `unit`.
- AGENT: status values are passed/failed/skipped/error/xfailed/xpassed.
- AGENT: the home dir is replaced with `~` in the run file, since P4/P7 may publish it.
- AGENT: run files are committed to git, because VAL-02 keeps every run and P4 needs the history.
- AGENT: the plugin also registers its markers, so it works in projects without our pytest.ini.

**Open questions**: none.

## 2026-11-08T04:27:56-05:00 — [P0] Steps 7–8: remaining tests (INST-05; INST-01/06/07 done earlier)

**What changed**
- Step 7 (hook tests, INST-02/03/04/08/09) shipped with the hook in the step-4 commit, so there is no separate commit for it.
- Added `tests/test_docs.py` (INST-05). It checks three things:
  - The "Hooks docs confirmed" section names each event together with the stdin field the hook reads.
  - The section records the common fields and the `$CLAUDE_PROJECT_DIR` quoting rule.
  - The section comes before the log_event.py entry in the log.
- The INST-01, INST-06 and INST-07 tests were added in steps 3, 5 and 6.

**Tests run**
- `make test`: 95 passed.
- Every one of INST-01 through INST-09 has at least one `@pytest.mark.req` test.

**Decisions**
- HUMAN: INST-05 is checked by a test on the progress.md section, plus Aayush's manual review entry.

**Open questions**: none.

## 2026-11-08T04:28:26-05:00 — [P0] Step 9: wrap-up, HANDOFF, push

**What changed**
- Final `make test` run.
- Rewrote `docs/HANDOFF.md`.
- Scanned the repo for home paths and emails: none found.
- Pushed to origin/main.

**Tests run**
- `make test`: 95 passed.

**Decisions**: none new.

**Manual check for Aayush (INST manual check)**
1. In a terminal: `cd "<project>" && claude`. This must be a NEW session, because the hooks weren't loaded in the one that created them. If prompted, approve the project hooks. `/hooks` lists them.
2. Send 3 short prompts.
3. Run `/compact`, then `/clear`.
4. Send one more prompt, then exit.
5. Check the results:
   - `tail -n 20 logs/events.jsonl | python3 -m json.tool --json-lines` should show, in order: SessionStart(startup), [UserPromptSubmit, Stop] ×3, PreCompact(manual), SessionStart(compact), SessionEnd(clear), SessionStart(clear) with a new session_id, UserPromptSubmit, Stop, SessionEnd(prompt_input_exit). Every entry should show phase "P0:planning".
   - `ls raw_logs/transcripts/` should list the first session's transcript. The second appears after you exit.
   - `cat logs/hook_errors.log` should not exist or be empty.

**Open questions**: none.

## 2026-11-08T04:31:40-05:00 — [P0] Checkpoint before /clear

**What changed**
- No code changes.
- The hooks became active mid-session: Claude Code's file watcher picked up settings.json after step 9.
- `logs/events.jsonl` now has live entries: Stop at 04:28:38 and UserPromptSubmit("/prep-clear") at 04:30:59. Both are tagged `P0:planning`.
- A scan of the log found no home paths or emails. `hook_errors.log` is absent.
- The live log is being committed for the first time.

**Tests run**
- `make test`: 95 passed.

**Decisions**
- AGENT: commit `logs/`, the hook-owned provenance that P5 needs. Its contents were not edited.

**Open questions**
- The SessionEnd(clear) and SessionStart(clear) from this /clear are the first real test of those events. Check them during the manual check.

## 2026-11-08T05:04:53-05:00 — [P1] Synthetic data generator, planted effects, schema tests, data dictionary

One entry for steps 1–6. Per-step entries were not written as each step finished, and timestamps are
not backdated. Each step has its own commit, listed below.

**What changed**
- Step 1 (`ec587a7`):
  - `data/reference/real_universities.txt`: 159 real universities, written from memory, for Aayush to spot-check.
  - `src/data/generate.py`: stdlib-only, deterministic, generates institutions.
  - `tests/datautil.py`: shared test helpers.
  - DATA-01/02 tests.
- Step 2 (`02f8847`):
  - Hidden institution parameters (inst_effect, stance_latent, rhetoric-gap flags).
  - statements.csv: 348 rows at every seed, built from a fixed shuffled mix of 0–4 statements per institution.
  - DATA-03/09/11 tests.
- Step 3 (`4c08660`):
  - Course catalog: 2–4 courses per institution, the first always intro. Each course runs each of the 7 terms with probability 0.635.
  - Policy is a latent-score model. allowed_uses, tools_named, disclosure and assessment are generated conditionally on policy.
  - DATA-04/06/07/08/10/15/16 tests.
- Step 4 (`850a2a4`):
  - Messy data in courses.csv: 8% MCAR missing policy with derived fields blanked, 10% re-cased level, 1% exact duplicates.
  - The full ground_truth.json: exact parameters, plain-language planted effects, per-row truth, and a record of every change made by the messy-data step.
  - `src/analysis/__init__.py` stub so the DATA-05 grep has a real target.
  - DATA-05/12/17 tests.
- Step 5 (`3753cc2`):
  - `make data` (SEED ?= 2026) and the committed `data/raw/`.
  - DATA-13 schema tests on the committed data and on seed 7, plus a stale-data check.
- Step 6:
  - `docs/data-dictionary.md` and DATA-14 tests.
- Seed 2026 output:
  - 150 institutions, 348 statements, 1,980 course rows (20 of them duplicates).
  - 157 blanked policies, 196 re-cased levels, 22 rhetoric-gap institutions (11 of each kind).

**Tests run**
- `make test`: 236 passed. Every DATA-01..17 requirement has at least one tagged test.
- Effect tests run on seeds 2026, 1, 2, 3, 4 (statements/courses) and 2026, 1, 2 (truth/mess).

**Decisions**
- HUMAN: terms are fall + spring, 7 terms (F23…F26).
- HUMAN: tools_named is multi-label and semicolon-separated, empty when policy = 0.
- HUMAN: a missing policy blanks policy, disclosure_required, allowed_uses and tools_named; assessment_adaptation is kept.
- HUMAN: duplicates go in courses.csv only.
- HUMAN: effects are moderate, and their exact parameters are recorded in ground_truth.json.
- HUMAN: the real-university list may be written from memory.
- HUMAN: commit per step, run through step 6, push at the end.
- AGENT: stdlib only (random/csv/json), no new deps. Policy rounds halves up (not banker's rounding).
- AGENT: statement count is a fixed mix (348). Independent draws gave 301 at seed 2026, outside ±10% of 350.
- AGENT: course policy has a persistent course_effect, so a course's policy is stable across terms. This keeps term-to-term changes driven by the trend, and the term means rise strictly at all 5 seeds.
- AGENT: the generator also rejects names that match the real list case-insensitively, which is stricter than DATA-02's exact match.
- AGENT: the DATA-16 observed test compares pooled groups (0–1 > 2 > 3–4). Per-level strict order is checked on the planted weights.
  - The first version required strict per-level order in the data and failed at seed 4: 0.107 vs 0.111 at policy 3→4, where the planted step is only 0.05 with ~100 rows at policy 4.
  - **Aayush: please review whether this counts as an acceptable fix or as weakening the test.**
- AGENT: the DATA-05 grep is case-insensitive, covers every file type under src/analysis/, and catches `ground-truth`/`groundtruth`. Only the package docstring that states the rule is exempt.
- AGENT: ground_truth.json and data/raw are committed (deterministic, ~690 KB), because P4 needs the truth.

**Open questions**
- DATA-10 null: at seed 2 the observed public−private gap is −0.21, about 2.5 SE, entirely from sampling noise in institution effects. At seed 2026 it is +0.08. This is the false-positive trap the null is meant to set. P2 should model institution clustering, or a naive t-test on rows may flag it.
- Real-university list: Aayush to spot-check `data/reference/real_universities.txt`.

## 2026-11-08T05:09:55-05:00 — [P1] DATA-16 trend test (Cochran–Armitage)

**What changed**
- `tests/test_data_courses.py`: added a stdlib Cochran–Armitage trend test across policy 0..4, with a helper check against known cases.
- New DATA-16 property test: the trend must be significant (p < 0.05) in the planted direction on at least 4 of 5 seeds, for both falling in-class exams/oral defenses and rising process logs/AI critiques.
- Observed: all 5 seeds, |z| between 17.0 and 18.5, p < 1e-63.

**Tests run**
- `make test`: 238 passed.

**Decisions**
- HUMAN: the pooled-group rewrite of the DATA-16 order test is a fair fix. The strict per-level version was flaky, not stronger.
- HUMAN: add a significance-based trend test, because the generator-settings check alone only proves the config.
- AGENT: Cochran–Armitage rather than a logistic slope: stdlib only, and the outcome is binary across ordered levels.

**Open questions**
- None.

## 2026-11-08T05:10:03-05:00 — [P1] Spec change: ANL-14 institution clustering (at Aayush's direction)

**What changed**
- `specs/P2-analysis.md`: added **ANL-14**. Inferential results on course data must account for clustering by `inst_id`, using cluster-robust SEs, a mixed model, or a cluster bootstrap. methods.md names the method used for each result, and a test checks that the DATA-10 null stays non-significant under it.

**Tests run**
- None needed (spec text only). `make test` is unaffected.

**Decisions**
- HUMAN: P2 must account for institution clustering. The spec edit was made by the agent at Aayush's direction.
- AGENT: the ID is ANL-14, the next free number. It lists which existing requirements it applies to, and adds a null-under-clustering test.

**Open questions**
- None.

## 2026-11-08T05:12:31-05:00 — [P1] Statement text as a real coding test: larger banks, hard cases, reserved held-out phrasings

**What changed**
- `src/data/generate.py` (generator_version 2):
  - Every stance level and every label now has 9 phrasings, and there are 18 neutral fillers.
  - Each phrasing is tagged `plain`, `negation`, `hedge`, `ai_no_stance` or `keyword_trap`.
  - Sentence order is fully shuffled, so the stance sentence can appear anywhere.
  - A public dev/held-out split by institution parity (odd inst_id → held-out).
  - 3 of every 9 phrasings are reserved for held-out statements only.
  - ground_truth.json now records the split, the reserved-phrasing count and the hard-case tags per statement, plus the full phrase banks.
- Regenerated `data/raw/`. The statements changed, and so did the courses, because the random stream shifted.
- Seed 2026:
  - 168 dev and 180 held-out statements. 71% of held-out statements contain a reserved phrasing; dev contains none.
  - Hard cases: ai_no_stance 115, negation 83, keyword_trap 76, hedge 41 statements.
  - 2,075 course rows: 21 duplicates, 164 missing policies, 205 re-cased levels.
- `tests/test_data_statements.py`: the bank-assembly test now handles any sentence position and checks exactly one stance sentence. New DATA-03 tests check bank variety, hard cases (banks and data, including that keyword traps leave the label false), and reserved phrasings only in the held-out half (checked on the text itself).
- `docs/data-dictionary.md`: documents how the text is built, the hard cases, the split rule, and the new ground-truth fields.
- `specs/P2-analysis.md`: removed the seed-2 "−0.21" figure from ANL-14. It is −0.12 after regeneration, and a specific number would go stale.

**Tests run**
- `make test`: 244 passed. All planted-effect tests still pass on the regenerated data.

**Decisions**
- HUMAN: make text coding a real test with 8+ variants, paraphrases, negations, hedges, AI-without-stance sentences, and phrasings reserved for the held-out half.
- AGENT: the dev/held-out split is by institution parity. ANL-03 does not define the split, and the generator must know it to reserve phrasings. Splitting by institution also stops the same institution's statements from appearing in both halves. The rule is public in the data dictionary.
- AGENT: keyword traps are only for integrity and collaboration. A "careers" trap sentence would itself arguably mention careers, which would make the label ambiguous.
- AGENT: public−private gaps after regeneration are +0.02, −0.00, −0.12, +0.04, +0.10 across seeds 2026, 1–4.

**Open questions**
- ANL-03 should name the split rule, e.g. "use the dev/held-out split defined in docs/data-dictionary.md". Aayush to decide during P2 planning.

## 2026-11-08T05:12:41-05:00 — [P1] Checkpoint before /clear

**What changed**
- No code changes since `379e077`. HANDOFF has been rewritten for the P1 review.

**Tests run**
- `make test`: 244 passed.

**Decisions**
- None new. This session's decisions are in the entries above. HUMAN: `.phase` committed as a `human:` commit (`4bd3465`).

**Open questions**
- Carried over to HANDOFF: the ANL-03 split rule wording, the real-university list spot-check (Aayush), a P1 review-log entry, and the PROV-02 prompt-source question for P5.

## 2026-11-08T05:35:58-05:00 — [P1] Checkpoint before /clear: P1 closed, P2 planning next

**What changed**
- No code changes since `d8d0851`.
- Aayush's P1 review-log entry was added verbatim and committed as `human:` (`461b7ac`). That commit also included Aayush's `.phase` change to `P2:planning`.
- HANDOFF rewritten for P2 planning.

**Tests run**
- `make test`: 244 passed.

**Decisions**
- HUMAN: P1 accepted (review-log entry). The real-university list was spot-checked: all 159 are real, no duplicates.
- HUMAN: `.phase` set to `P2:planning`.

**Open questions**
- From Aayush's review-log note: decisions logged as "HUMAN" in progress.md were drafted with Claude chat. P5 provenance should tell "decided by Aayush" apart from "written by Aayush". This adds to the PROV-02 open question.

## 2026-11-08T05:43:44-05:00 — [P2] Step 0: deps, test path, analysis target, ANL-03 spec wording

**What changed**
- `requirements.txt`: full pinned tree from `pip freeze`. Adds pandas 3.1.1, numpy 2.4.6, scipy 1.17.1, statsmodels 0.15.0 and jsonschema 4.26.0, plus their dependencies (formulaic, patsy, narwhals, attrs, referencing, rpds-py, etc.).
- `pytest.ini`: `pythonpath = .`, so tests can `import src.analysis...`.
- `Makefile`: `analysis` runs `python -m src.analysis.run`, then `python -m src.evaluation.run`. Both runners are empty step lists for now.
- `src/__init__.py`, `src/evaluation/__init__.py` (states that only this package and tests may read the truth).
- `specs/P2-analysis.md`: ANL-03 now cites the split in docs/data-dictionary.md, requires that coder rules are tuned on the dev half only and that a test fails if the coder reads held-out labels, and says only src/evaluation/ and tests may read ground truth. Edited at Aayush's direction.

**Tests run**
- `make test`: 244 passed. `make analysis` runs (no steps yet).

**Decisions**
- HUMAN: ANL-03 cites the data-dictionary split; tune on dev only; a leakage test is required.
- HUMAN: src/evaluation/ is the only non-test code allowed to read ground truth.
- HUMAN: clustered SEs grouped by inst_id are the main method. Verified that OrderedModel.fit accepts cov_type="cluster": the null is non-significant on 5/5 seeds when clustered, while naive p < 0.05 on seeds 2 and 4.
- HUMAN: the kappa test shows SKIPPED ("awaiting human coding (ANL-04)") until Aayush fills in the sample.
- HUMAN: chi-square reports a naive p labelled as naive, with the cluster-bootstrap CI for Cramér's V as the main inference.
- HUMAN: ±25% coefficient-ratio check, plus coverage (the clustered 95% CI contains the planted value on at least 4 of 5 seeds).
- HUMAN: stop when the ANL-04 sample is ready.

**Open questions**
- None.

## 2026-11-08T05:44:45-05:00 — [P2] Step 1: ANL-01 cleaning

**What changed**
- `src/analysis/common.py`: paths and deterministic writers. Results JSON has sorted keys, floats rounded to 6 places, a synthetic-data note, and no timestamps.
- `src/analysis/clean.py`: exact dedupe, `level` stripped and lowercased, missing policy kept blank (read back as NA, no imputation), `term_index` added. Writes `data/clean/` and `results/clean_log.json`. Registered in `src/analysis/run.py`.
- Seed 2026: courses 2,075 → 2,054 rows (21 duplicates removed), 205 levels normalized, 164 policies missing (7.98%). Institutions 150 and statements 348 are unchanged.
- `tests/test_anl_clean.py`: dedupe, casing, NA and log checks on the committed data and on seed 7, plus a staleness check.

**Tests run**
- `make test`: 253 passed. The first run failed one test: my staleness test compared an unrounded float with the rounded file value. Fixed the test to compare after the writer's rounding.

**Decisions**
- AGENT: data/clean/ is committed (deterministic). A staleness test guards it, as for data/raw/.
- AGENT: cleaned booleans stay as "true"/"false" text in CSV. `read_clean` gives typed columns (policy as Int64 with NA).

**Open questions**
- None.

## 2026-11-08T05:48:20-05:00 — [P2] Step 2: ANL-02 codebook and rule-based coder, tuned on dev only; ANL-03 leakage guards

**What changed**
- `src/analysis/code_text.py`: 29 stance rules (ordered, negations first, default 0) and 20 theme rules.
  - Every rule cites a verbatim dev example. Every coded value records the rule ID behind it.
  - Writes `data/clean/statements_coded.csv`. Registered in `make analysis`.
- `src/evaluation/truth.py`: the only non-test reader of the truth file. `load_truth(split, stmt->inst)` picks statements by the public split rule and returns labels for that split only.
- `src/evaluation/coder_eval.py`: `score()` (per-label P/R/F1, stance per-class P/R/F1 + confusion matrix, macro-F1) and `dev_report()` (dev-only scores and errors → `results/coder_dev_eval.json`).
- `docs/codebook.md`: stance −2..+2 and the three themes with include/exclude rules and dev examples, the decision procedure, a rule table generated from code, and known limits. The limits include that the rule author also wrote the held-out phrasings.
- `tests/test_anl_coder.py`:
  - ANL-02: codebook completeness, rule table in sync, every value traces to a rule, no LLM/network imports, negation and keyword-trap cases, coded output current.
  - ANL-03: an audit-hook test that the coder never opens the truth file; src/analysis never imports src/evaluation; the dev loader returns only dev; the dev report is unchanged when held-out labels are scrambled; no reserved-only 4-gram in the rules or codebook; every rule and codebook example is dev text.

**Tuning on dev**
- First dev run: macro-F1 0.996. The 2 errors were "Internship partners" firing a collaboration rule; fixed with a lookbehind. Dev is now 1.000.
- The dev score is near-perfect by construction (the rules come from dev wording) and says nothing about generalization. The held-out score in step 3 is the real measure.

**Tests run**
- `make test`: 314 passed.
- The new grounding test failed on 4 rules: S+2-not-a-threat, S-2-no-form, S+2-master, S+2-designed-around. Their examples are non-reserved generator phrasings that never occur in any dev statement, so I had written them from knowledge of the generator, not from dev data. **I removed the rules rather than change the test.** The dev score stayed at 1.000.

**Decisions**
- AGENT: a rule may only cite and target wording seen in dev statements, generalizing by stem at most (e.g. `ban\w*`). No synonyms are added from outside dev.
- AGENT: overall macro-F1 = the mean of the three theme F1s (positive class) and the stance macro-F1 (mean over the stance classes present).
- AGENT: the leakage test uses a Python audit hook on `open`, so it catches any read of the truth file, not just a string reference.

**Open questions**
- None.

## 2026-11-08T05:50:09-05:00 — [P2] Step 3: ANL-03 held-out evaluation (frozen rules) and ANL-04 hand-coding sample

**What changed**
- Rules frozen at `32f3cd2` (the last commit touching code_text.py or codebook.md). The held-out evaluation was then run once and not followed by any tuning.
- `src/evaluation/coder_eval.py`: `heldout_report()` → `results/coder_eval.json`. It contains held-out scores, the held-out set split by reserved vs non-reserved wording, dev scores, the 0.80 target, `target_met`, and the rules SHA-256 and freeze commit.
- `src/evaluation/hand_sample.py`:
  - Writes `data/reference/hand_code_sample.csv`: 30 held-out statements chosen by the public split with seed 4005, label columns blank. It never overwrites a sample once any cell is coded.
  - Cohen's kappa (human vs coder, human vs truth), written to `results/kappa.json` only when every cell is coded.
- `src/evaluation/run.py`: `make analysis` now runs the held-out evaluation and the sample/kappa step.
- `tests/test_anl_eval.py`: score() on a toy case, a freeze guard (rules fingerprint must match), the report is current, the honest `target_met`, sample validity and no-overwrite, kappa known values, the kappa pipeline on a truth-filled copy, and the kappa result test.

**Results (seed 2026, held-out n = 180)**
- **Held-out macro-F1 0.829** (target 0.80, met).
  - Stance: accuracy 0.761, macro-F1 0.741.
  - Theme F1: integrity 0.81, collaboration 0.92, careers 0.84.
- Without reserved wording (n = 53): 0.968. With reserved wording (n = 127): 0.755. The gap is the generalization cost of dev-grounded rules.
- Stance errors are mostly unknown wording defaulting to 0: −1→0: 14, +1→0: 16, +2→0: 7, −2→0: 5. In one case the `ban\w*` stem misread a negated "banning" sentence (+2→−2).
- Dev: 1.000, by construction.

**Tests run**
- `make test`: 322 passed, 1 skipped. The skip is `test_human_agreement_kappa_reported`, recorded in the run file as `skipped` with "awaiting human coding (ANL-04)".

**Decisions**
- HUMAN: the kappa test is SKIPPED with that exact reason until the sample is coded.
- AGENT: kappa is unweighted Cohen's kappa per code (stance treated as 5 categories). Weighted kappa is not used.
- AGENT: the reserved-wording flag used for the subset scores is read from the truth file by src/evaluation, after the freeze, for reporting only.

**Open questions**
- Aayush: hand-code the 30 statements (ANL-04). Steps 4–9 of the P2 plan are not started.

## 2026-11-08T06:03:10-05:00 — [P2] ANL-04 change: the sample is coded by Aayush; kappa labelled "Aayush vs coder" / "Aayush vs truth"

**What changed**
- Aayush's coded sample was committed unchanged first, as `human:` (`6374d78`).
- `specs/P2-analysis.md` ANL-04 (at Aayush's direction): "The sample is coded by Aayush. Report Cohen's kappa as 'Aayush vs coder' and 'Aayush vs truth'." This replaces "human vs coder / human vs truth".
- `src/evaluation/hand_sample.py`:
  - Result keys `aayush_vs_coder` and `aayush_vs_truth` (were `human_vs_*`).
  - Added `coder_by: "Aayush"` and `comparison_labels` with the display labels.
  - The sample gets a `#` header comment naming Aayush as coder and the kappa labels. `read_sample` skips `#` lines, and `make_sample` writes the comment.
- `data/reference/hand_code_sample.csv`: the header comment line was prepended. None of Aayush's coded cells changed (the diff is +1 line).
- `tests/test_anl_eval.py`: renamed keys and docstrings, checks for `coder_by` and the labels, and a new test for the header comment.
- `make analysis` wrote `results/kappa.json` for the first time.

**Results (n = 30, unweighted Cohen's kappa)**
- Aayush vs truth: stance 0.894; integrity, collaboration and careers 1.000 each.
- Aayush vs coder: stance 0.649, integrity 0.500, collaboration 1.000, careers 0.462.
- The coder agrees with Aayush less than the truth does. This matches the held-out finding (step 3): the coder misses reserved wording that a human reads correctly.

**Tests run**
- `make test`: 324 passed. The kappa test now runs and passes instead of skipping.

**Decisions**
- HUMAN: the ANL-04 sample is coded by Aayush, and kappa is labelled "Aayush vs coder" / "Aayush vs truth".
- AGENT: the skip reason stays "awaiting human coding (ANL-04)", the exact text Aayush specified earlier. It is a pending-state message, not a kappa label.
- AGENT: the coded file was committed as `human:` before the agent's one-line header change, so Aayush's coding has its own provenance.

**Open questions**
- None.

## 2026-11-08T06:08:57-05:00 — [P2] Step 4: ANL-05 / ANL-11 / ANL-12 descriptives with cluster-bootstrap CIs

**What changed**
- `src/analysis/stats.py`:
  - Vectorized cluster bootstrap: institutions are resampled with replacement as multinomial weight vectors, 2,000 resamples, seed 4005, percentile 95% CIs.
  - Share and mean records.
  - Chi-square with a p-value labelled "naive", plus Cramér's V with a cluster-bootstrap CI as the main inference.
- `src/analysis/descriptives.py` → three results files:
  - `results/descriptives.json` (ANL-05): policy distribution and mean by level, SE, and term; coded stance and theme prevalence by carnegie and by year (from the coder, not the truth).
  - `results/allowed_uses.json` (ANL-11): use prevalence by level and SE among policy ≥ 1 rows, plus the intro explanation/debugging − code_generation gap with CIs.
  - `results/assessment.json` (ANL-12): shares by policy and by level, and assessment × policy and × level associations.
- Missing policy is excluded wherever the analysis conditions on policy, with the excluded count reported. Groups are listed in their natural order.
- Registered in `make analysis`. The whole step runs in under 1 s.

**Results (seed 2026)**
- Mean policy:
  - intro 0.99 [0.89, 1.08], intermediate 1.82, upper 2.39, graduate 2.53
  - SE 2.56 [2.40, 2.71] vs non-SE 1.48 [1.36, 1.59]
  - F23 1.18 → F26 2.44, rising every term
- Coded stance: R1 +0.41 [0.19, 0.62] vs R2 +0.12, Masters −0.15, Baccalaureate 0.00.
- Intro gaps: explanation − code_generation +0.74 [0.69, 0.79]; debugging − code_generation +0.57 [0.51, 0.62].
- Assessment × policy: Cramér's V 0.279 [0.262, 0.302]. Assessment × level: V 0.172 [0.153, 0.201].

**Tests run**
- `make test`: 339 passed.
- One new test failed at first. `test_clustered_intervals_are_wider_than_row_level_intervals` required cluster CIs ≥ 1.1× naive for the per-term means; the observed ratio was ~1.04×, because each institution has only ~2 rows per term.
  - The 1.1 threshold was my guess, aimed at a statistic where clustering barely matters.
  - I retargeted the test to the overall mean and the private−public gap (the planted null), where the measured ratio is ~2.05×, with a 1.5× floor.
  - The docstring states this, including the per-term result. Flagged for Aayush's review as a test change after a failure.

**Decisions**
- AGENT: the allowed-uses denominator is rows with policy ≥ 1, because allowed_uses is empty at policy 0 by design.
- AGENT: assessment by level uses all rows (assessment_adaptation is never missing); by policy uses known-policy rows.
- AGENT: the bootstrapped Cramér's V is biased upward (V ≥ 0). To be noted in methods.md.

**Open questions**
- Aayush: review the retargeted clustering-width test above.

## 2026-11-08T06:11:47-05:00 — [P2] Step 5: ANL-06 association, ANL-07 ordinal regression, ANL-14 clustering

**What changed**
- `src/analysis/inference.py`:
  - `results/association.json`: policy × level and policy × is_se, each with a contingency table, chi-square p labelled naive, and Cramér's V with a cluster-bootstrap CI.
  - `results/regression.json`: ordinal logit `policy ~ level + is_se + term_index + control + carnegie` (references intro, public, R1) on 1,890 known-policy rows across 150 institutions.
    - Main inference: SEs clustered by inst_id.
    - Also reported: naive SEs, and a cluster-bootstrap cross-check (500 institution resamples, seed 4005).
    - Each coefficient ÷ the term coefficient, with delta-method CIs.
- Registered in `make analysis`. The 500 bootstrap refits take ~75 s.

**Results (seed 2026)**
- Coefficients (clustered SE): intermediate +1.45 (0.20), upper +2.64 (0.19), graduate +2.79 (0.26), is_se +1.39 (0.20), term_index +0.49 (0.025). All p < 1e-10.
- private +0.11 (0.24), **p = 0.64 clustered** vs 0.21 naive.
- **Baccalaureate −0.35: naive p = 0.007, clustered p = 0.28.** There is no planted Carnegie effect on policy, so the naive model produces a false positive and clustering removes it.
- Clustered SEs for institution-level predictors are 2.5–2.7× naive. Bootstrap SEs are within 0–8% of the sandwich SEs.
- Ratios to the term effect: intermediate 2.96 [2.14, 3.78], upper 5.39 [4.63, 6.14], graduate 5.71 [4.64, 6.77], is_se 2.83 [2.06, 3.61], private 0.23 [−0.73, 1.19].
- Cramér's V: policy × level 0.339 [0.319, 0.367]; policy × is_se 0.456 [0.387, 0.524].

**Tests run**
- `make test`: 347 passed.

**Decisions**
- AGENT: the regression bootstrap is 500 refits, not 2,000. It is a cross-check, ANL-05's 2,000 applies to the descriptives, and 2,000 refits would take ~5 min.
- AGENT: the staleness test refits without the bootstrap. The bootstrap fields are covered by a separate agreement test (within 25% of the sandwich SE).
- AGENT: the Carnegie reference is R1 and the control reference is public.

**Open questions**
- None.

## 2026-11-08T06:12:50-05:00 — [P2] Step 6: ANL-13 rhetoric vs practice, with DATA-17 recovery

**What changed**
- `src/analysis/rhetoric.py` → `results/rhetoric.json`:
  - Per institution (135 with statements): mean coded stance, mean known policy, both z-standardized.
  - Gap = z(stance) − z(policy). Top-decile |gap| list (k = 14) with direction labels.
  - Pearson r with a bootstrap CI over institutions (2,000 resamples, seed 4005).
- `src/evaluation/rhetoric_eval.py` → `results/rhetoric_recovery.json` (reads the truth): precision and recall of the list against the DATA-17 flags, plus direction agreement.
- Both registered in `make analysis`.

**Results (seed 2026)**
- **Precision 0.93** (13/14 listed are planted mismatches; base rate 0.14). **Recall 0.68** (13/19 eligible flagged; with k = 14 the most possible is 0.74). The direction is correct for 13/13.
- Overall stance–policy correlation r = −0.08 [−0.28, 0.13]. The generator couples stance to policy for most institutions, but the 22 planted mismatches sit at opposite extremes and cancel that out in a plain correlation. This will be stated in methods.md.

**Tests run**
- `make test`: 351 passed.

**Decisions**
- AGENT: "mean course permissiveness" is the raw mean of known policies, not adjusted for course mix (level/SE), as the spec literally says. Noted as a limitation.
- AGENT: k = ceil(10% of institutions with statements). Recall is reported against flagged institutions that could appear (19 of 22 have statements).

**Open questions**
- None.

## 2026-11-08T06:14:05-05:00 — [P2] Step 7: ANL-08 recovery tests (directions, null, magnitudes, coverage)

**What changed**
- `src/evaluation/recovery.py` → `results/recovery.json` (reads the truth): directions for DATA-06..09, the DATA-10 null under clustering, ratio magnitudes against planted values (±25%), and clustered-CI coverage across seeds 2026, 1–4 (each regenerated, cleaned and refit; ~2.5 s).
- `tests/test_anl_recovery.py`: each check is re-derived from the results files and the truth.

**Results**
- Directions: DATA-06, 07, 08 and 09 all recovered.
- Null: private p = 0.64 clustered (0.21 naive). Not significant. Clustered p is above 0.05 on all 5 seeds, while naive p is below 0.05 on seeds 2 (p < 0.001) and 4 (p = 0.013).
- Ratios to the term effect (planted → estimate [CI]):
  - intermediate 3.5 → 2.96 [2.14, 3.78]
  - upper 6.0 → 5.39 [4.63, 6.14]
  - graduate 6.5 → 5.71 [4.64, 6.77]
  - is_se 3.0 → 2.83 [2.06, 3.61]
  - private 0 → 0.23 [−0.73, 1.19]
  
  All are within ±25%, and all run 6–15% low.
- Coverage (of 5 seeds): upper 5, is_se 5, private 5, intermediate 4, graduate 4. Seed 4 misses intermediate and graduate.

**Tests run**
- `make test`: 359 passed.

**Decisions**
- HUMAN: ±25% sanity check plus coverage ≥ 4/5.
- AGENT: magnitudes are compared as ratios to the term effect. Logit coefficients sit on a different scale from the generator's latent scale, but ratios are scale-free.
- AGENT: the consistent 6–15% underestimate is likely attenuation from fitting a logit to latent normal noise with rounding and clipping. To be noted in methods.md, not corrected.

**Open questions**
- None.

## 2026-11-08T06:15:12-05:00 — [P2] Step 8: ANL-09 JSON schemas for every results file

**What changed**
- `src/report/schemas/*.schema.json`: 12 Draft 2020-12 schemas, one per `results/*.json` (clean_log, coder_dev_eval, coder_eval, kappa, descriptives, allowed_uses, assessment, association, regression, rhetoric, rhetoric_recovery, recovery).
  - All require `synthetic: true` and a note containing "SYNTHETIC", and reject unknown top-level keys.
  - Value constraints: CIs are 2-number arrays, probabilities lie in [0, 1], kappa in [−1, 1], and the bootstrap settings and the regression's clustered main inference are fixed by `const`.
- `tests/test_anl_schemas.py`: one schema per results file and vice versa, each schema valid and each file validating, plus negative tests (a missing synthetic flag, an unknown key, a one-sided CI, a probability > 1, a non-clustered main inference) to show the schemas are not vacuous.

**Tests run**
- `make test`: 385 passed.

**Decisions**
- AGENT: the schemas are hand-specified JSON (built once from shared definitions in a scratch script). P3/P4 pages can read them directly.
- AGENT: results/tests/ run files are excluded. They belong to P0 (INST-07) and have their own format.

**Open questions**
- None.

## 2026-11-08T06:17:53-05:00 — [P2] Step 9: ANL-10 methods.md; P2 complete

**What changed**
- `docs/methods.md`: plain-language methods. Covers the synthetic-data warning, cleaning, coding with the dev/held-out design and Aayush's check, why clustering matters, a per-result table of inference methods (ANL-14), the analyses, the recovery checks, and limits (synthetic data, keyword coding, methods). It deliberately quotes no result numbers, so it cannot drift from results/.
- `tests/test_anl_methods.py`: the synthetic notice, coverage of every ANL requirement, a limits section, an inference method named for each inferential results file, and no hard-coded decimals.
- Verified end to end: a full `make analysis` from scratch reproduces every committed file in data/clean/ and results/ byte for byte.

**Tests run**
- `make test`: 395 passed. One methods test failed first: the doc said "cluster-bootstrap CI" in one row and the test expects "cluster bootstrap". Fixed the doc wording for consistency.

**Decisions**
- AGENT: methods.md carries no numbers; the dashboard and readers take numbers from results/*.json.

**Open questions**
- Aayush:
  - review the two tests changed after failing (step 4 clustering-width retarget; step 2 removal of 4 ungrounded rules)
  - review this phase and write a P2 review-log entry
  - decide whether to move .phase to P3

## 2026-11-08T06:25:31-05:00 — [P2] Checkpoint before /clear: test changes accepted, bootstrap counts confirmed

**What changed**
- No code changes since `09a5c67`. HANDOFF rewritten.
- Confirmed the bootstrap resample counts from the committed results and the code:
  - descriptives, allowed_uses, assessment and association: 2,000 (`stats.N_BOOT`). The rhetoric correlation also uses 2,000.
  - The 500 refits (`inference.REGRESSION_BOOT`) apply only to the regression cross-check.
  - The descriptives schema fixes `resamples` to 2,000 with `const`, and `test_descriptives_record_bootstrap_settings` asserts it.

**Tests run**
- `make test`: 395 passed.

**Decisions**
- HUMAN: both test changes made after failures are accepted: step 2 (removing the 4 generator-derived coder rules) and step 4 (retargeting the clustering-width test).
- HUMAN: 500 resamples is fine for the regression cross-check only. ANL-05 descriptives stay at 2,000.

**Open questions**
- Carried to HANDOFF: the P2 review-log entry, moving .phase to P3, and the PROV-02 prompt-source question for P5.

## 2026-11-08T07:00:13-05:00 — [P3] Step 1a: census_region and overall groupings added to ANL-05

**What changed**
- `src/analysis/descriptives.py`: policy descriptives are now also by census_region and overall (`by == group == "all"`); statement stance and themes are also by census_region and overall. Course rows take census_region from institutions.csv.
- `specs/P2-analysis.md` ANL-05 text, `src/report/schemas/descriptives.schema.json` (`by` is now an enum), `docs/methods.md` §4 updated to match.
- `results/descriptives.json` regenerated with `make analysis`. No other results file changed: the bootstrap weights are drawn once per table, so adding groups does not move existing records.
- Tests: the two ANL-05 parametrized tests now cover census_region and all; new `test_census_region_and_overall_groupings_cover_every_row`.

**Tests run**
- `make test`: 400 passed.

**Decisions**
- HUMAN: add census_region and an overall grouping to ANL-05 (P3 plan question 2), and update the P2 spec, schema and tests.
- AGENT: the overall group is encoded as by = "all", group = "all", so the dashboard reads it with the same record shape.

**Open questions**
- None.
