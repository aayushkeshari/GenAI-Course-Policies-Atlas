# Project 2 for CS 4005: Agentic Development with Claude Code

A study, using **synthetic data**, of how US computer science departments permit, encourage and talk about
generative AI, with a focus on software engineering courses. Claude Code (the agent) wrote the code. Aayush (the
human supervisor) owned the specs, reviewed the work, and wrote the evaluation and reflection.

> **All study data is synthetic.** Real university names are attached to invented policies and statements. Nothing
> here describes what these schools actually do. The timeline and token pages are the exception:
> they show the real record of how the project was built.

**Live site:** https://aayushkeshari.github.io/genai-cs-policy/

| Page | What it shows | Goal |
|---|---|---|
| [Findings dashboard](https://aayushkeshari.github.io/genai-cs-policy/dashboard/) | Answers to RQ1–RQ8: policies by course level, rhetoric and tone, SE vs other courses, assessment changes | G1 |
| [Validation explorer](https://aayushkeshari.github.io/genai-cs-policy/validation/) | Test runs, requirement traceability, coverage, fault injection, recovery of planted effects | G2 |
| [Contribution timeline](https://aayushkeshari.github.io/genai-cs-policy/timeline/) | Prompts, responses, commits, spec edits and reviews, split into human and agent work | G3 |
| [Token usage](https://aayushkeshari.github.io/genai-cs-policy/tokens/) | Tokens by phase and prompt, context size across /clear and /compact, the clear/compact experiment | G4 |
| [Evaluation & reflection](https://aayushkeshari.github.io/genai-cs-policy/evaluation/) | Aayush's evaluation against the goals and the reflection, shown unedited | G5 |

## Reproduce everything

Requirements: Python 3.11, `make`, and network access (to install packages and Chromium, and for the browser tests,
which load pinned CDN libraries).

```sh
make setup        # create .venv, install the pinned requirements.txt, install Chromium for the UI tests
make all          # data -> analysis -> site data -> timeline -> tokens -> site -> tests
make serve        # open http://127.0.0.1:8000/
make prepublish   # the gate before publishing: tests, redaction scan, link check, synthetic banner on every page
```

`make all` is deterministic for a given seed (`make all SEED=2026` is the default). Two inputs exist only on the
machine where the project was built:

- `raw_logs/` (gitignored) holds the Claude Code session transcripts. Without it, `make all` skips `make tokens` and
  keeps the committed `results/tokens.json`.
- `logs/events.jsonl` is written by the Claude Code hooks in `.claude/hooks/`. It is committed, so the timeline
  rebuilds from it.

### Makefile targets

| Target | Does |
|---|---|
| `data` | P1: generate the synthetic institutions, courses, statements and hidden ground truth into `data/raw/` |
| `analysis` | P2: clean, code the text, run the statistics into `results/`, then evaluate against the ground truth |
| `report` | P3/P4: build the dashboard data (`site/data/`) and the validation explorer data (`site/validation/data/`) |
| `timeline` | P5: merge hook events, git log, progress and review logs into `site/timeline/data/timeline.json` |
| `tokens` | P6: one row per assistant message from the transcripts, plus metrics, into `results/tokens.json` |
| `site` | P7: copy `docs/evaluation.md` unedited into `site/evaluation/` |
| `test` | Run pytest. Every run is archived in `results/tests/` |
| `faults` | P4: inject deliberate bugs into a temporary copy and check that the tests catch them |
| `prepublish` | P7: `site` + `test`, then the redaction, link and banner checks in `src/publish/prepublish.py` |
| `serve` | Serve `site/` locally |

## Publishing

`.github/workflows/pages.yml` deploys `site/` to GitHub Pages on every push to `main`. `site/` is committed
already built and has no build step, so run `make prepublish` locally before pushing. One-time setup: in the
repository's **Settings → Pages → Build and deployment**, set **Source** to **GitHub Actions**.

## How it was built

- `specs/` holds one spec per phase (P0 instrumentation to P7 publish). Every requirement has an ID such as `DATA-03`,
  and at least one test tagged `@pytest.mark.req("DATA-03")`. The validation explorer shows that mapping.
- `CLAUDE.md` gives the agent its standing rules: plan before code, never weaken a test, and log every task in
  `docs/progress.md` with decisions tagged by who made them (human or agent).
- Hooks in `.claude/hooks/` log every prompt, response, compaction and session boundary to `logs/events.jsonl`. They
  also copy transcripts to `raw_logs/`. The timeline and token pages are built from these logs.
- Context was managed with `/prep-clear`, `/clear` and `/resume`. `docs/HANDOFF.md` is the only state that carries
  over a clear.
- Only Aayush did these: editing and approving specs, hand-coding the 30-statement sample, `docs/review-log.md`,
  the design of the token experiment, `docs/evaluation.md` and the reflection, and `docs/tokens-learned.md`.

## Layout

```
specs/            phase specs (human-owned)
src/              data generator, analysis, evaluation, report builders, provenance, tokens, publish checks
tests/            pytest suite, each test tagged with requirement IDs
site/             the published static site (HTML/CSS/JS, pinned CDN libraries, no build step)
results/          analysis outputs, token metrics, and every archived test run
docs/             progress log, handoff, methods, codebook, data dictionary, review log, evaluation
logs/             hook-written event log (do not edit)
```
