# CLAUDE.md — standing instructions (auto-loaded every session)

## Project
Study, using SYNTHETIC data, how US CS departments permit, encourage, and talk about generative AI,
with a focus on software engineering courses. Deliverables are static web pages: an analysis dashboard,
a validation explorer, a contribution timeline, and a token-usage report. All are published on GitHub Pages.
Human supervisor: Aayush. You are the implementing agent.

## Session rules
- Read only the spec for the current phase (see docs/HANDOFF.md). Open other specs only when you need
  something specific from them. Context costs tokens.
- Implement what the spec says. If the spec is wrong or unclear, propose a spec change and wait.
  Do not change specs yourself.
- Plan before code for anything over ~50 lines. Wait for approval.
- Every requirement ID (e.g. DATA-03) needs at least one test tagged `@pytest.mark.req("DATA-03")`,
  with a docstring that says what the test proves.
- Run `make test` before you call any task done. Never weaken or skip a test to make it pass.
  If a test is wrong, say so and propose the fix.

## Logging (required — this is graded)
- After each completed task, append to docs/progress.md:
  `## <output of date -Iseconds> — [Phase] <title>` then: what changed, tests run and result,
  decisions tagged HUMAN or AGENT, open questions. Get timestamps from `date -Iseconds`. Never make them up.
- Commit messages begin with `agent:`. Commit messages for Aayush's own changes begin with `human:`.
- Never edit logs/ or raw_logs/. Hooks own them.

## Constraints
- Python 3.11+, deps pinned in requirements.txt. Use the Makefile targets defined in specs.
- Site: static HTML/CSS/JS in site/, no build step. Pin every CDN library to an exact version.
- Data is synthetic. Institution names are fictional. Every page that shows data says so.
- No secrets, absolute home paths, or emails in anything under site/.

## Context protocol
`/prep-clear` checkpoints before a clear. `/resume` picks up afterwards. docs/HANDOFF.md is the
only state that carries over a clear, so keep it accurate.
