**What I learned about tokens**

- Context size drives cost. 97.6% of the project's 61.8M tokens were cache reads, which means Claude re-read existing context far more than it generated anything new.
- Clearing is the biggest lever. The same small task cost about 8× more at the end of a long session (1.72M tokens) than right after /clear (214k). The largest single context drop was 323k → 39k at one /clear.
- Compact helps, but less than clear. Run C cost about 18% more than run B, because the compaction summary stays in context.
- The spec-driven workflow made clearing cheap. Because HANDOFF.md and the phase specs carried the state, /prep-clear → /clear → /resume lost almost nothing.
- Slow tests cost tokens too. Once the full suite took about 7 minutes, every fix-and-rerun loop added up. Running only the current phase's tests while building, and the full suite once per phase, cut that.
- Caveats: one run per condition (n = 1), so the ratios are anecdotal; only the direction is clearly larger than the noise. Subagent usage was missed until INST-04 was extended mid-project.
