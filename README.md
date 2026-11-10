# Project 2 for CS 4005: Agentic Development with Claude Code

These are **draft specifications**, not code. Claude Code writes all the code; you own the specs.

## Set up (once)
1. Create an empty GitHub repo, copy this kit in, and commit it as:
   `human: import spec drafts (drafted with Claude chat)`
2. Read every spec and change anything you disagree with. Commit your edits on their own
   (`human: revise P1 data spec — ...`). Your git history then shows which decisions were yours.
3. In the repo, start `claude`, pick Opus with `/model`, and send:
   > Read specs/00-overview.md and specs/P0-instrumentation.md. Propose a plan for P0. Don't write code yet.
4. Approve or correct the plan, then let it build P0. Logging must work before P1 starts.

## The loop for each phase
1. `!echo "P1:planning" > .phase` (the `!` runs a shell command without spending a turn). This tags token usage.
2. Ask for a plan from the phase spec. Push back on it. Approve it.
3. Switch the tag (`P1:writing-code`, `P1:validation`, ...) as the work changes.
4. Claude implements, writes tagged tests, runs `make test`.
5. **You** review something real: a diff, a test, a chart. Write it up in `docs/review-log.md`.
6. `/prep-clear` → wait for "Ready to clear." → `/clear` → `/resume`.

## Only you do these
- Editing and approving specs
- Hand-coding 30 sample statements (P2, ANL-04). This is the human check on the AI text coder.
- Entries in `docs/review-log.md`
- The clear/compact token experiment design (P6). Claude runs it, you choose the task.
- `docs/evaluation.md` and the reflection
