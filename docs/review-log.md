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

## 2026-11-08 — P2 analysis

**Results reviewed**
- Clustering removes two false positives: Baccalaureate (naive p = 0.007 → clustered p = 0.28)
  and public/private (naive significant on 2/5 seeds, never with clustering). Clustered SEs are
  2.5–2.7× the naive ones; the bootstrap cross-check agrees within 8%.
- Planted effects recovered: clustered 95% CI contains the planted value on ≥4/5 seeds for every effect.
- Coder held-out macro-F1 0.829 (target 0.80); 0.968 on seen wording vs 0.755 on unseen; stance weakest (0.76).
- Rhetoric-gap list: 13/14 are planted mismatches; recall 13/19.

**ANL-04 sample:** coded by Aayush.
- Kappa vs truth: stance 0.89, themes 1.00. Kappa vs coder: stance 0.65, integrity 0.50,
  collaboration 1.00, careers 0.46. The coder misses held-out phrasings that an independent reader gets.

**Test changes reviewed**
- Accepted: removing 4 coder rules written from knowledge of the generator. That was leakage.
  Remaining risk: the same agent wrote both the generator and the coder.
- Accepted: moved the cluster-width test from per-term means (~2 rows/institution, ratio ~1.04)
  to the overall mean and public/private gap (ratio ~2×, floor 1.5×).
- Regression bootstrap uses 500 refits as a cross-check; descriptives keep 2,000.

**My take** 
The clustering result is the clearest win. It shows a naive analysis would have reported effects that don't exist. The leakage catch matters just as much, because it's the kind of problem that's invisible unless someone asks where the rules came from.

## 2026-11-08: P3 dashboard

**Review**
- Every displayed number (400+) and all 451 chart values are tested against their source JSON,
  and Playwright loads each view at 1280px and 375px in light and dark mode with no console errors.
- Clustered vs naive results are shown side by side in three places: the regression, Cramér's V,
  and the chi-square p-values.
- One test catch was real: a hand-typed "precision is 1.0" in the coder note now comes from the JSON.
- Coder negation error ("Far from banning…" coded −2) surfaced in the drilldown. "Far from" never
  appears in the dev half, so it was documented in methods.md and on the drilldown instead of
  being fixed against held-out data.

## 2026-11-08: P4 validation explorer

**Review**
- Fault detection 10/10, but only 5/10 by behavior-specific tests; the other 5 were caught only
  by golden-file comparison. Asked for behavior tests on those five (sign, term index,
  denominator, rhetoric gap direction, dropped site field).
- Run files deduplicated by content hash (~490 KB → ~170 KB per run), decided before git
  history grew; every run is still kept.
- Claude found that Python's bytecode cache had silently skipped some fault injections;
  fixed, with a test.
- Accepted one P3 test change: the privacy check now scans decoded JSON, which is stricter.
- Decided PROV-02 categories for P5: human-typed / drafted with Claude chat / automated / shared.

## 2026-11-08: P3 dashboard

**Review**
- Every displayed number (400+) and all 451 chart values are tested against their source JSON,
  and Playwright loads each view at 1280px and 375px in light and dark mode with no console errors.
- Clustered vs naive results are shown side by side in three places: the regression, Cramér's V,
  and the chi-square p-values.
- One test catch was real: a hand-typed "precision is 1.0" in the coder note now comes from the JSON.
- Coder negation error ("Far from banning…" coded −2) surfaced in the drilldown. "Far from" never
  appears in the dev half, so it was documented in methods.md and on the drilldown instead of
  being fixed against held-out data.

## 2026-11-08: P4 validation explorer

**Review**
- Fault detection 10/10, but only 5/10 by behavior-specific tests; the other 5 were caught only
  by golden-file comparison. Asked for behavior tests on those five (sign, term index,
  denominator, rhetoric gap direction, dropped site field).
- Run files deduplicated by content hash (~490 KB → ~170 KB per run), decided before git
  history grew; every run is still kept.
- Claude found that Python's bytecode cache had silently skipped some fault injections;
  fixed, with a test.
- Accepted one P3 test change: the privacy check now scans decoded JSON, which is stricter.
- Decided PROV-02 categories for P5: human-typed / drafted with Claude chat / automated / shared.