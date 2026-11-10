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

## 2026-11-08T07:01:56-05:00 — [P3] Step 1: `make report` builds site/data/ (DASH-01)

**What changed**
- New `src/report/build_site_data.py` (+ `src/report/__init__.py`); `make report` runs it.
  - It validates 8 results files against their schemas and copies them byte for byte: descriptives, allowed_uses, assessment, association, regression, rhetoric, coder_eval and kappa.
  - It also exports trimmed raw rows from data/clean/ (labelled "raw synthetic rows, not results"):
    - institutions.json
    - courses.json (missing policy stays null)
    - statements.json (the coder's labels and rule IDs, prefixed `coded_`)
- Not copied: recovery, rhetoric_recovery and coder_dev_eval, which are truth-derived and not needed by DASH-03.
- site/data/ is committed. Total is about 1 MB, most of it courses.json at 640 KB.
- New tests/test_dash_data.py with 7 tests:
  - site/data/ is current
  - copies are exact and schema-valid
  - a schema-invalid file stops the build
  - no ground-truth fields leak, and the module never reads data/raw/ or imports src.evaluation
  - statement labels equal the coder's output
  - row files are labelled synthetic
  - course rows match the clean data

**Tests run**
- `make test`: 407 passed.
- One new test failed first: the truth-leak test banned `stance` and `mentions_*` keys in every file. In kappa.json and coder_eval.json those are the names of aggregate scores, not hidden labels. The bare-label check now applies to the row files only. Entity-level truth fields stay banned everywhere.

**Decisions**
- HUMAN: export trimmed statements, courses and institutions as raw synthetic rows. Exclude every ground-truth field, with a test. `make report` builds the data and `make site` will call it in P7.
- AGENT: the coder's labels are exported under `coded_*` names so they can never be confused with the truth's bare `stance`/`mentions_*` names.
- AGENT: truth-derived recovery files are left out of site/data/. P4 (validation explorer) can decide separately.

**Open questions**
- None blocking.

## 2026-11-08T07:09:50-05:00 — [P3] Steps 2–5: dashboard shell, chart views, statement explorer, institution drilldown (DASH-02..06, DASH-08)

**What changed**
- New `site/dashboard/`: `index.html`, `style.css` and `app.js`. Plain HTML/CSS/JS with no build step.
  - CDN libraries are pinned: Chart.js 4.4.1 (cdnjs) and chartjs-chart-matrix 2.0.1 (jsdelivr, for the heatmap).
- **DASH-02:** a "Synthetic data — illustrative only" banner sits in the shared header, so every view shows it. The footer repeats it. The app refuses to render any data file that lacks `synthetic: true`.
- **DASH-03:** 13 canvases across 5 chart views, plus the KPI summary:
  - Course policy: policy by level (100% stacked bars), SE vs non-SE, trend by term (mean with a CI band), census region (mean policy and mean stance as small multiples, each on its own axis).
  - Uses & assessment: allowed uses by level (heatmap), assessment by policy level.
  - Statements: stance and theme prevalence, rhetoric-vs-practice scatter.
  - Regression: coefficient plot with clustered vs naive CIs.
  - Coder accuracy: F1 by statement set, kappa.
- Inference labelling:
  - Cramér's V is shown with its cluster-bootstrap CI as the main inference; chi-square p is labelled naive.
  - The regression shows clustered CIs as thick bars and naive CIs as thin grey bars. Its note gives the Baccalaureate naive-vs-clustered p.
- **DASH-04:** the statement explorer has text search (with highlighting), filters for stance, theme (including "no theme"), pub_type and year, and pages of 30. Each card shows the coded stance, the coded themes and the rule IDs that fired.
- **DASH-05:** each panel has a one-sentence takeaway built from the data, a "Show data table" toggle (aria-expanded) and a link to its JSON. Takeaway wording that depends on the data (for example "barely predicts", "does not matter", "CIs overlap") is chosen by a condition on the data, not hard-coded.
- **DASH-06:**
  - Colors: Okabe-Ito-style categorical slots in fixed order from the dataviz reference palette, an ordinal blue ramp for policy 0–4, and a binned blue ramp for the heatmap. Each mode has its own selected steps.
  - Theme: light/dark/auto toggle, saved in localStorage inside try/catch.
  - Keyboard: ARIA tabs with arrow/Home/End keys, a skip link, labelled form controls, and canvases with role="img" and an aria-label holding the takeaway.
- **DASH-08:** the institution drilldown shows the institution's facts and its rhetoric row (with a top-decile flag), a course × term policy grid (n/a = not stated, · = not offered), and its statements. Clicking a scatter dot, an institution name on a statement card, or a top-decile table row opens it. The URL hash (`#view=drilldown&inst=I027`) makes every view linkable.
- Provenance hooks for DASH-07:
  - Every displayed number is a `<span data-src="file.json#/pointer" data-fmt>`.
  - Every chart dataset carries `srcs` (one JSON pointer per value).
  - The explorer's filtered counts are tagged `data-derived`.
- Playwright 1.63.0 (+ greenlet, pyee) is pinned in requirements.txt. `make setup` now runs `playwright install chromium`.

**Tests run**
- `make test`: 407 passed. No UI tests yet; they come in step 6.
- Rendered every view headlessly at 1280px light and 375px dark: no console errors, and no horizontal page scroll at 375px. Checked the screenshots by eye.
  - Fixed: heatmap colors were blended in RGB (they looked grey) and had black labels on dark cells. They now use binned ramp steps with ink chosen per step.
  - Fixed: the drilldown course grid was cramped in two columns, so it is now full width.
  - Fixed: the sticky header takes too much room on phones, so it is not sticky below 600px.

**Decisions**
- HUMAN: Playwright is pinned, Chromium is installed by `make setup`, and the UI test fails rather than skips without it.
- AGENT: the views are grouped into 8 tabs. The heatmap uses the chartjs-chart-matrix plugin because Chart.js has no native heatmap.
- AGENT: stance and theme bars use a single series color rather than a diverging palette, because the axis labels already carry the stance.

**Open questions**
- Observed while checking: the drilldown's default institution (top-decile gap −4.55) has one statement that the coder labels −2 via `S-2-ban`. The statement says "Far from banning chatbots…", which is a negation miss. Some top-decile "gaps" are therefore coder errors. The rhetoric-gap recall of 0.68 already reflects this. Nothing to change in P3; worth a line in the P2/P4 discussion.

## 2026-11-08T07:16:32-05:00 — [P3] Step 6: DASH-07 browser tests (plus DASH-02..06, 08), `make serve`

**What changed**
- New `tests/test_dash_ui.py`, 17 tests. Each serves site/ over HTTP and drives headless Chromium with Playwright.
  - DASH-07: every view loads with no console or page errors in light/dark mode at 1280px and 375px. All 13 canvases have a chart with data and visible pixels. No horizontal scroll.
  - DASH-07: all 400+ `[data-src]` numbers (every view, every data table open) match results/*.json. They are formatted by an independent Python re-implementation of JS `toFixed` (Decimal, ties away from zero).
  - DASH-07: all 451 plotted chart values equal the value at their JSON pointer.
  - DASH-07: tables, KPI tiles, takeaways and notes have no digits left once the sourced spans are removed, apart from a short list of fixed labels.
  - DASH-02: the banner is in the viewport on every view at both widths.
  - DASH-03: each required view has the right shape (e.g. 5×4 heatmap, one scatter dot per institution, clustered and naive CIs per coefficient).
  - DASH-04: explorer search and filters match a direct filter of statements.json, and cards show labels and rule IDs.
  - DASH-05: one-sentence takeaway, working table toggle and existing source links for all 11 panels.
  - DASH-06: arrow/Home/End tab keys, Enter on table toggles, and the theme cycle redraws charts without errors. Dark tokens cover every light token in both dark scopes.
  - DASH-08: a real mouse click on a top-decile scatter dot opens that institution, with its course policies and statements. The picker and the deep link work.
  - DASH-01: CDN URLs are pinned to x.y.z on allowed hosts, there is no build tooling, and there are no emails, home paths or secrets under site/.
- `site/dashboard/app.js`: the coder note hand-typed "precision is 1.0". It now shows the sourced value, and only when every theme's precision is 1 in every set.
- `make serve` (a P7 stub) now runs a minimal `python -m http.server` on 127.0.0.1:$(PORT), default 8000, so the dashboard can be viewed now.

**Tests run**
- `make test`: 424 passed.
- Failures in the new tests along the way, all fixed in the test, with nothing weakened:
  - The chart-value count had a guessed bound (> 500). The true count is 451, derived per chart in a comment and asserted exactly.
  - The keyboard test read aria-selected before the hashchange handler ran. It now waits for the attribute.
  - The no-unsourced-digits regex now allows the label "F1"/"F1s".
- The no-unsourced-digits test also found a real issue (the hand-typed "1.0"), fixed in app.js as above.

**Decisions**
- HUMAN: the UI tests fail rather than skip without Chromium.
- AGENT: the UI tests load Chart.js from the pinned CDN, so `make test` needs network access.
- AGENT: `make serve` was filled in early, at Aayush's request to run it. P7 owns the rest of the site and may extend it.

**Open questions**
- Aayush: review the dashboard (`make serve`, then http://127.0.0.1:8000/dashboard/).
- The P2 review-log entry is still missing from docs/review-log.md.

## 2026-11-08T07:39:44-05:00 — [P3] "Far from banning" coder error: documented as a known limit, not fixed

**What changed**
- Checked the dev half only (even-numbered inst_id, 168 statements) for "far from"-style negated prohibitions. I searched for "far from", "rather than / instead of banning", "not banned/prohibited/forbidden", "no longer", "anything but" and "hardly".
  - The only hit is one phrasing, "AI use is not prohibited", in 12 dev statements. Its own rule `S+1-not-prohibited` already covers it.
  - There is no "far from"-style wording in dev. Any general negation rule would have had to be written from the held-out example, so per Aayush's instruction the coder was not changed. The rules stay frozen at 32f3cd2.
- `docs/methods.md` §6 "Of keyword coding": a new bullet describes the known error: what it is, why it is unfixed, and its effect on ANL-13. It has no numbers, as the methods-doc test requires.
- Institution drilldown: a caveat appears whenever the institution has a rhetoric-gap row. It says the gap uses coder labels and can reflect a coding error, gives the "far from banning" example, and points to methods.md.
- Tests:
  - New `test_methods_documents_the_far_from_negation_limit` (ANL-10).
  - The DASH-08 scatter-click test now also checks the caveat.

**Tests run**
- `make test`: 425 passed.

**Decisions**
- HUMAN: fix only if dev has the pattern, otherwise document it. Never tune on held-out.
- AGENT: the dev search found only the already-handled "not prohibited", so this is documented, not fixed.

**Open questions**
- None.

## 2026-11-08T07:40:09-05:00 — [P3] Checkpoint before /clear: DASH-01..08 implemented and tested

**What changed**
- No code changes since `3b82ea8`. HANDOFF rewritten for P3 review and P4 planning.

**Tests run**
- `make test`: 425 passed (2026-11-08T07:39).

**Decisions**
- None new. All P3 decisions are recorded in the step entries above.

**Open questions**
- Carried to HANDOFF:
  - Aayush's P3 review and P3 review-log entry
  - moving .phase to P4
  - pushing `3b82ea8` and this checkpoint
  - PROV-02 prompt-source question (P5)

## 2026-11-08T07:47:27-05:00 — [P4] Step 1: VAL-01 body sidecars (spec change), coverage in make test, spec parser

**What changed**
- `specs/P4-validation.md`: VAL-01/02 now say the run file records `body_sha256`, and the docstring and source are stored once per content hash in `results/tests/bodies/<sha>.json`. Body files are kept like run files. Old test-run/1 files stay as they are, and readers accept both formats.
- `tests/conftest.py` now writes schema test-run/2. Each body file holds exactly `canonical_body(docstring, source)`, so its SHA-256 equals its name. A body file is written only if absent. Docstrings are now home-scrubbed too.
- New `src/validation/runs.py` reads either format and verifies each body's hash. New `src/validation/specs.py` parses `- **AREA-NN**` bullets, joining wrapped lines and keeping nested bullets on their own lines. It finds 75 requirements.
- `make test` adds `--cov=src --cov-report=json:results/coverage.json`.
- Tests:
  - `test_runfile.py` was adapted to the new format: the schema is test-run/2, and the field set has `body_sha256` instead of inline docstring/source. The docstring/source assertions are unchanged; they now read through the sidecar.
  - New tests cover: content-addressing and write-once; plugin and reader producing the same bytes; reading old-format files; rejecting tampered bodies; every committed run file loading.
  - New `test_val_specs.py` covers the parser and checks that every req tag names a real spec ID.
  - New Makefile coverage test.
- Run files shrink from about 490 KB to about 170 KB. 433 tests share 193 bodies, because parametrized tests share one.

**Tests run**
- `make test`: 433 passed.

**Decisions**
- HUMAN: option (c), sidecar bodies now, as a spec change to VAL-01/02. Keep every run.
- AGENT: the exact spec wording, and the content-addressed directory layout (one file per hash).
- AGENT: the 54 existing test-run/1 files are left untouched. Rewriting them wouldn't shrink git history and would alter historical records.

**Open questions**
- None.

## 2026-11-08T07:55:56-05:00 — [P4] Step 2: validation explorer data (site/validation/data/)

**What changed**
- New `src/report/build_validation_data.py`, run by `make report` after the dashboard build. It writes these files:
  - `manifest.json`
  - `tests.json`
  - `history.json`: one status letter per run per test
  - `traceability.json`: 75 requirements, each with a rolled-up status (passing, partial, failing or untested) and a phase_started flag
  - `coverage.json`
  - `review-log.md` (verbatim)
  - `recovery/{recovery,rhetoric_recovery,coder_dev_eval}.json` (byte copies)
- The snapshot is one `make test` run, so freshness is testable. `make test` now archives a per-module coverage summary for its own run in `results/tests/coverage/<run file>`, using `src.validation.runs attach-coverage`, which checks timestamps. The builder takes the newest run that has such a summary.
  - `test_validation_data_is_current` rebuilds from the run named in the manifest, so later runs don't make the data stale.
  - After a code change, `make test && make report` must run twice before the snapshot is an all-green run.
- The full pytest-cov report moved from `results/coverage.json` to `results/tests/coverage/latest.json`, which is git-ignored. Putting it at the top level of results/ in step 1 broke `test_every_results_file_has_a_schema_and_vice_versa`. Step 1's own run passed only because the file didn't exist yet.
- New `src/validation/redact.py`. Published test text (node IDs, sources, docstrings, messages, requirement text) contains deliberate fake fixtures: `/Users/alice`, fake tokens, and paths inside parametrize IDs. These become visible `‹redacted-path|email|secret›` placeholders, and tests.json carries a redaction note. One spec line, INST-09's `/Users/<name>` example, shows as a placeholder.
- **Test changed (P3):** `test_no_secrets_home_paths_or_emails_under_site` now checks decoded JSON strings instead of escaped JSON text. On raw text, the escaped newline before a decorator (`\n@pytest.mark…`) matched the email pattern as `n@pytest.mark.req`, which was a false positive. Decoding is strictly stronger: a `\u0040` escape can no longer hide a real email. The patterns are unchanged.
- New `tests/test_val_data.py` (19 tests) covers:
  - freshness and reproducibility
  - fidelity of tests.json to the run file and its bodies
  - history matching each run file
  - traceability rows and the rollup rule
  - per-module coverage, and attach-coverage refusing a report from another run
  - snapshot selection
  - the verbatim review log
  - truth-derived files appearing only under the validation recovery directory, with the dashboard never referencing validation data
  - no private strings anywhere under site/validation/
  - redaction placeholders
  - synthetic labels and manifest hashes

**Tests run**
- `make test`: 457 passed (after two report/test cycles).

**Decisions**
- HUMAN: show the three truth-derived files in a separate validation-only view. Keep the dashboard and site/data truth-free.
- AGENT: per-run coverage archive and snapshot-by-run for reproducibility; redaction with visible placeholders; the decoded-JSON fix to the P3 privacy test.

**Open questions**
- None blocking. Aayush may want to review the P3 privacy-test change. It strengthens the check, but it is a change to an existing test.

## 2026-11-08T08:09:30-05:00 — [P4] Step 3: fault injection (`make faults`, VAL-04)

**What changed**
- New `src/validation/faults.py`, run by `make faults`.
  - It copies the repo to a temp directory, leaving out .venv, .git, logs and raw_logs. Every fault must match its file exactly once; this is checked on the copy before any run.
  - It needs a clean baseline run, then applies 10 faults one at a time and runs the suite on each.
  - "Caught by" means the test passed on the baseline and fails or errors with the fault. The report goes to `results/faults.json`, which has a new schema at `src/report/schemas/faults.schema.json`. The builder validates the report and publishes it with caught_by node IDs redacted.
- The 10 faults:
  - F01: flip the regression sign
  - F02: skip dedupe
  - F03: ignore the seed
  - F04: break the S-2-ban keyword rule
  - F05: off-by-one term_index
  - F06: kappa without chance correction
  - F07: wrong denominator
  - F08: flip the rhetoric gap
  - F09: site data drops census_region
  - F10: home-path redaction no-op
- UI tests (`test_dash_ui.py`, `test_val_ui.py`) are excluded except for F09, as Aayush decided. The runner's own tests (`test_val_faults.py`) are always excluded, because they would run the runner recursively and check the report while it's being rewritten.
- Bug found by the runner's own test: a same-size edit made within one second reused a stale `.pyc`, so the fault silently didn't run. F08 is exactly that kind of edit. Fault runs now set PYTHONDONTWRITEBYTECODE=1, and the tiny-repo test proves this works.
- Each catching test is classified as golden-file (`*_is_current` / `*_are_current`: re-derive a committed output and compare it byte for byte) or behavioral. The report gives both rates.
- **Result:** detection rate **10/10**, with no uncaught faults. Only **5/10** were caught by a behavioral test. F01, F05, F07, F08 and F09 are caught only by golden-file tests: no test checks the regression's sign, term_index starting at 0, the gap's denominator, the gap's sign, or the export's field list directly.
- Bootstrap note: after the golden fields were added, the earlier report no longer matched its schema, so the fault baseline couldn't pass. For one bootstrap run I derived those fields from its caught_by, then ran `make faults` again. The committed file is that genuine run.
- New `tests/test_val_faults.py` (11 tests) covers:
  - a tiny-repo run: one fault caught, one not, the repo byte-identical afterwards, and no stale bytecode
  - the match-exactly-once rule
  - a non-clean baseline aborting the run
  - the committed report being current and consistent, and its published copy being redacted
  - golden-file classification
  - the Makefile target

**Tests run**
- `make faults`: 10/10 caught, 5/10 behavioral, about 2.5 min.
- `make test`: 470 passed.

**Decisions**
- HUMAN: UI tests are skipped in fault runs except for F09, and the page says so.
- AGENT: the 10 faults and their exact sites; excluding the runner's self-tests; the golden/behavioral split; adding no new tests just to raise the behavioral rate.

**Open questions**
- For Aayush: should behavioral tests be added for F01, F05, F07, F08 and F09, for example a regression sign check on planted data, term_index == 0 for F23, a hand-computed gap denominator, a gap sign check on a constructed institution, and a field list check on the export? Not done, because it wasn't asked for.

## 2026-11-08T08:14:32-05:00 — [P4] Step 4: validation explorer UI (site/validation/)

**What changed**
- New `site/validation/{index.html,style.css,app.js}`. No build step and no chart library. It reuses `../dashboard/style.css` for tokens and components, so the two pages read as one system and share the theme toggle. The pinned CDN libraries are marked 12.0.2 and DOMPurify 3.1.6 from cdnjs, used for the review log only.
- Views:
  - **Tests:** KPIs, plus search over node ID, docstring and source, and filters for phase, kind, status and requirement. Filter state lives in the URL hash. Each row has a status pill and a 20-run history strip. The detail pane shows the docstring, failure message, full history strip with legend and pass count, linked spec text, source, and body SHA.
  - **Traceability:** all 75 requirements, with counts and phase/status filters. Untested and failing requirements are red, and a "phase not started" badge marks later phases; nothing is hidden.
  - **Coverage:** total and per-module meters with numbers.
  - **Fault injection:** detection rate, behavioral rate, uncaught count; the method, UI and self-test exclusions; an explicit uncaught list and golden-only list; every fault with its diff and catching tests, each tagged golden or behavioral.
  - **Recovery vs. ground truth (validation only):** a separate view with its own note.
  - **Review log:** the log next to an automated-evidence summary.
  - **Claims:** built here; its data comes in step 5.
- Statuses use the reserved status palette, always with an icon and a text label (dataviz method). Coverage meters use the accent on a lighter step of the same hue.
- I checked rendering in Chromium at 1280 and 390 px wide, with no horizontal overflow and no JS errors. The only 404 is claims.json, which arrives in step 5.

**Tests run**
- `make test`: 470 passed. The Playwright tests for the explorer (VAL-08) come in step 6.

**Decisions**
- HUMAN: marked plus DOMPurify from the CDN, pinned.
- AGENT: share the dashboard stylesheet rather than copy it; use plain `<pre>` for source with no highlighter, which avoids another CDN dependency; share the theme key with the dashboard.

**Open questions**
- None.

## 2026-11-08T08:18:51-05:00 — [P4] Step 5: claims (VAL-06) and dashboard evidence links

**What changed**
- New `src/report/claims.json` with 17 claims: one per dashboard chart panel (11) and one per summary headline tile (6).
  - Each claim gives the finding in words and the tests that support it: computation tests, recovery tests where they apply, and the dashboard UI and data tests that check the display.
  - There are no numbers in the claim text. The builder publishes each test's snapshot status and a rolled-up claim status, and a missing test counts as failing.
- The dashboard has an "Evidence: supporting tests" link under each panel's footer and in each headline tile, pointing to `../validation/#view=claims&claim=<id>`.
  - My first version put the link inside `.panel-foot`, which broke the P3 test that all footer links are data-source links. The link moved out of the footer; the test is unchanged.
- New `tests/test_val_claims.py` (5 tests):
  - claims match the dashboard's panels and tiles exactly
  - each claim has at least two computation tests, all present in the snapshot run
  - the published status is the rollup
  - the two conditional claim wordings ("barely predicts", "does not matter") match the data
  - the dashboard renders the Evidence links
- One run had a transient Playwright timeout in `test_synthetic_banner_visible_on_every_view`: the CDN stalled and that run took 50 s. It passed on the next three runs. Not changed.

**Tests run**
- `make test`: 475 passed.

**Decisions**
- HUMAN: one claim per panel plus the headline numbers.
- AGENT: which tests support each claim; claims include recovery tests as method evidence, labeled validation-only on the explorer.

**Open questions**
- None.

## 2026-11-08T08:26:59-05:00 — [P4] Step 6: explorer Playwright tests (VAL-08), final fault run, P4 checkpoint

**What changed**
- New `tests/test_val_ui.py` (27 tests, kind ui). Expected values come from Python over `site/validation/data/`, independently of app.js. They cover:
  - every view in light, dark and 390 px, with the synthetic banner and no horizontal scroll
  - a 404 on a data file showing an explicit error
  - header numbers
  - 10 filter combinations set by URL, matching a Python filter exactly
  - the form controls writing the hash, and Clear resetting it
  - the detail pane: docstring, source, one history cell per run, pass count, spec text
  - deep links and Enter-to-select
  - the traceability rows and KPI counts, untested requirements in red, filters, and count links leading to the right tests
  - coverage rows
  - fault rates, cards and the uncaught/golden lists
  - the dashboard Evidence link opening the claim
  - the recovery tab's exact label and note
  - the review log's headings rendering, sanitized
  - keyboard tabs and ARIA
  - exact CDN pins
- Fixes the tests found:
  - The review log overflowed at 390 px because of a long unbreakable word: `.md { overflow-wrap: anywhere }`.
  - In one test, `innerText` keeps a trailing newline in `<pre>`, so both sides are now stripped before comparing. This was a test-side comparison fix.
- `make faults` was rerun on the final suite. F09 now includes `test_dash_ui.py` and `test_val_ui.py`. The result is unchanged at 10/10 caught and 5/10 behavioral. Even with the UI tests, F09 (census_region dropped from institutions.json) is caught only by `test_site_data_is_current`.

**Tests run**
- `make faults`: 10/10, 5/10 behavioral.
- `make test`: 502 passed (twice, after `make report`).

**Decisions**
- AGENT: GitHub Pages is not enabled on the repo, and deploying is P7 (PUB-02/03), so I did not enable it. The explorer is local-only until P7.

**Open questions**
- See HANDOFF: P4 review-log entry, behavioral tests for the five golden-only faults, PROV-02.

## 2026-11-08T08:37:24-05:00 — [P4] Behavioral tests for the five golden-only faults

**What changed**
- Aayush's P4 review asked for behavioral tests for F01, F05, F07, F08 and F09. The tests that caught these faults before compared committed results byte for byte; they didn't check the specific behavior. Each new test runs the code itself:
  - F01 (ANL-07): `test_model_frame_passes_predictors_through_unchanged`. In the design matrix, term_index is the cleaned term_index (0..6) and every other predictor is a 0/1 indicator.
  - F05 (ANL-01): `test_term_index_is_zero_based_position_in_terms`, on both the committed and the seed-7 clean data. F23 is 0 and F26 is 6.
  - F07 (ANL-11): `test_intro_gap_is_computed_over_intro_rows_only`. It recomputes `allowed_uses()` and compares the result with a hand count over intro rows with policy >= 1.
  - F08 (ANL-13): `test_gap_sign_on_a_constructed_example`. Three hand-built institutions give a gap of positive, zero and negative.
  - F09 (DASH-01/08): `test_export_keeps_every_institution_field_the_dashboard_reads`. A fresh build's institutions.json has every `inst.<field>` that app.js reads (the drilldown shows census_region) and every clean column. Under F09, the drilldown would have shown "undefined" with no test failing.
- Checked on a temp copy that each new test fails under its fault: 5/5.

**Tests run**
- Targeted: 6 passed. `make test`: 508 passed (twice, after `make report`).

**Decisions**
- HUMAN: add behavioral tests for the five golden-only faults.
- AGENT: what each test checks, and the fixtures used (a constructed example for F08, recomputation for F07).

**Open questions**
- None. `make faults` is rerun in the next commit.

## 2026-11-08T08:41:15-05:00 — [P4] Fault injection rerun with the behavioral tests

**What changed**
- `make faults` was rerun and `results/faults.json` and the explorer data were rebuilt.
- The detection rate is still **10/10**. The behavioral rate rose from **5/10 to 10/10**: every fault is now caught by at least one test that checks the specific behavior, and no fault is golden-file only.
  - F01, F05, F07, F08 and F09 are each caught by their new behavioral test as well as the golden-file test.

**Tests run**
- `make faults`: 10/10 caught, 10/10 behavioral.
- `make test`: 508 passed (twice).

**Decisions**
- None new.

**Open questions**
- None.

## 2026-11-08T08:42:43-05:00 — [P4→P5] PROV-02 prompt categories added to the P5 spec

**What changed**
- `specs/P5-provenance.md` PROV-02 now classifies logged prompts further:
  - human-typed: the prompt starts with "[drafted by Aayush"
  - automated: subagent reports, scheduled tasks, cross-session messages
  - shared: if unclear

  The wording is Aayush's instruction, verbatim.
- Explorer data rebuilt, because spec text is an input to the traceability view.

**Tests run**
- Targeted: test_val_specs and test_val_data, 27 passed. `make test`: 508 passed (twice).

**Decisions**
- HUMAN: the PROV-02 categories and the "[drafted by Aayush" marker.

**Open questions**
- The P4 review-log entry lists four categories: human-typed / drafted with Claude chat / automated / shared. The spec instruction has three, and its marker "[drafted by Aayush" defines *human-typed*. Should "drafted with Claude chat" be its own category, with the marker identifying it instead? Confirm before P5 planning.

## 2026-11-08T08:43:43-05:00 — [P4] Checkpoint before /clear: P4 complete and reviewed

**What changed**
- No code changes since `9bd44d7`. HANDOFF rewritten for P5 planning.

**Tests run**
- `make test`: 508 passed (2026-11-08T08:43).

**Decisions**
- None new.

**Open questions**
- Carried to HANDOFF: PROV-02 category wording (3 vs 4 categories), and moving .phase to P5.

## 2026-11-10T14:34:16-05:00 — [P5] Step 1: timeline builder, actor/category rules, redaction (PROV-01/02/06)

**What changed**
- Spec changes Aayush approved: PROV-01 actor is HUMAN | CLAUDE | shared. The PROV-02 human-typed marker is now "Typed by me". PROV-05 names docs/timeline-narrative.md and defines approvals (HUMAN decision tags) and rejected plans (REJECTED: tags, "not recorded" before the rule existed).
- CLAUDE.md logging rules: record rejected plans as `REJECTED: …` (approved by Aayush).
- New src/provenance/build_timeline.py and timeline.schema.json. `make timeline` writes site/data/timeline.json with 237 items. It merges logs/events.jsonl, git log (commits and per-file spec edits), docs/progress.md headings and docs/review-log.md headings.
- New tests/provutil.py (fixture git project) and tests/test_prov_data.py (PROV-01/02/04/05/06 data tests).
- Test change for Aayush to accept: tests/test_dash_data.py::test_site_data_is_current and tests/test_dash_ui.py's synthetic check now exclude site/data/timeline.json by name. PROV-01 puts it in site/data/, but it is real project history (synthetic: false), so it cannot carry the dashboard's synthetic: true. Every dashboard-owned file is still checked byte for byte.

**Tests**
- tests/test_prov_data.py: 37 passed.
- `make test`: the first run had 4 failures, all stale-explorer-snapshot checks in test_val_data after the spec change. After `make report`, the second `make test` passed 545, then `make report` again.

**Decisions**
- HUMAN: three prompt categories as listed (human-typed "Typed by me" / automated / shared). Approvals = HUMAN decision tags in progress.md. Rejected plans are "not recorded" before 2026-11-10. Narrative in docs/timeline-narrative.md.
- AGENT: a spec edit inside a commit with neither `agent:` nor `human:` (the three early `claude-chat:` commits) is "shared". Spec edits in `agent:` commits stay HUMAN per PROV-02.
- AGENT: automated prompts are those starting with `<task-notification`, `<scheduled-task`, `<cross-session-message` or `<teammate-message`. None exist yet.
- AGENT: per PROV-02, automated prompts still have actor HUMAN. Only their category says automated.
- AGENT: review-log headings carry only a date, so each is timed by the commit that first added it (`git log -S`), else end of day with ts_precision "day".
- AGENT: a commit's phase comes from its subject (`agent: P4 …`), else the last earlier hook event's .phase, else "unknown". The 3 pre-hook spec commits are "unknown".
- AGENT: lines changed exclude generated or hook-owned paths (logs/, raw_logs/, data/, results/, site/data/, site/validation/data/).
- AGENT: the schema lives in src/provenance/, not src/report/schemas/ (ANL-09 ties that folder 1:1 to results/*.json).
- AGENT: `make timeline` is not part of `make report`, because events.jsonl grows with every prompt. P7's `make site` will call it.

**Open questions**
- Aayush wrote "four categories" but listed three. Three are implemented, and a fourth is a one-line rule change.
- Accept the two dashboard test changes above?

## 2026-11-10T14:40:21-05:00 — [P5] Step 3: timeline page, Q&A view, contribution summary (PROV-03/04/05)

**What changed**
- New site/timeline/ (index.html, style.css, app.js). It is vanilla JS with no CDN libraries, and it reuses the dashboard's tokens, theme toggle and banner style.
  - Timeline: a vertical list with filters for actor, phase, type and prompt category, kept in the URL hash. Five zoom levels (buttons or Ctrl/⌘+scroll) space items by elapsed time; gaps over 4 h are shortened and labelled with their real length. A Compact/Clear toggle switches density. Markers differ by shape (circle, diamond, outlined square) and also carry a text label. Clicking a row shows its details and source.
  - Prompts & responses: every prompt with its paired response excerpt. Search is live and highlights matches, and timeline rows link to their exchange.
  - Contribution summary: KPI tiles, a per-actor table (— where a measure doesn't apply, with rejected plans "not recorded" before 2026-11-10), a prompt-category table with the rules, and the narrative or a "not yet written" placeholder.
- Step 2 (Q&A pairing and summary counts in the data) went into step 1's builder with its tests, so it needs no separate commit.
- Builder fix: a REJECTED tag counts only when it starts a bullet line, because my own step 1 prose mentioned the tag inline and would have counted as a rejection. Spec-edit summaries no longer repeat the commit subject.
- New tests/test_prov_ui.py, with 26 browser tests for PROV-03/04/05.

**Tests**
- tests/test_prov_ui.py and tests/test_prov_data.py: 63 passed. One test of mine was wrong at first: it compared spacing using Python's round() (round half to even) against JS Math.round. It now mirrors Math.round.
- `make test`: 571 passed, twice, with `make report` after each run.

**Decisions**
- AGENT: no chart library. The timeline is a styled list, so there is nothing to pin.
- AGENT: times are shown as logged (the author's local offset) and are not converted to the viewer's zone.
- AGENT: the narrative renders as escaped plain paragraphs, with a line starting "#" shown as a heading. It is not Markdown, so no sanitiser is needed.

**Open questions**
- None new. Carried: the fourth PROV-02 category, and acceptance of the two dashboard test changes from step 1.

## 2026-11-10T14:42:19-05:00 — [P5] Step 4: rebuild, traceability check, HANDOFF, push

**What changed**
- Rebuilt site/data/timeline.json (242 items) and the explorer data. The traceability view shows PROV-01..06 all passing: 8, 22, 17, 9, 5 and 2 tests.
- Rewrote docs/HANDOFF.md for the end of P5.

**Tests**
- `make test`: 571 passed, twice, with `make report` after each run.

**Decisions**
- None new.

**Open questions**
- A fourth PROV-02 category? Accept the two dashboard test changes? Both are listed in HANDOFF.
