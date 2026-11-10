# Evaluation & Reflection (written by Aayush)

| Goal | Evidence | How well met | Notes |
|---|---|---|---|
| G1 Data, analysis, dashboard | data/raw/, results/*.json, site/dashboard/ | Mostly met | Planted effects recovered on ≥4/5 seeds; clustering removed two false positives (e.g. p = 0.007 → 0.28). Weakest part: the data is synthetic, so findings say nothing about real departments. A future version should collect real published policies. |
| G2 Validation explorer | site/validation/, results/faults.json | Met | 646 tests, 93.8% line coverage; every requirement traced to tests; 10/10 injected faults caught by behavior-specific tests; recovery vs ground truth shown separately. |
| G3 Contribution record | site/timeline/, logs/events.jsonl, docs/progress.md, git log | Met | Timestamped prompts, responses, decisions, and commits by actor. Prompt categories are coarse: most prompts are "shared". |
| G4 Token usage | site/tokens/, results/tokens.json | Met, with caveats | 78.7M tokens, 97.8% cache reads. Clear vs compact vs long session compared with n = 1 per condition, so the ratios are anecdotal. |
| G5 Published | GitHub repo (private, shared with instructor); Pages workflow in P7 | Partially met | Deployment is built and tested, but the site is not publicly deployed because the repo is private. |

## Reflection: agentic vs AI-assisted development
What surprised me most was how powerful the agentic approach is. Claude Code wrote nearly all of this project: 60 of the commits and over 20,000 lines, against my 8 commits and about 530 lines, mostly specs and review notes. It built a data generator, a clustered statistical analysis, a dashboard where every number is tested against its source, and a validation explorer that catches all 10 deliberately injected bugs. Watching that happen was impressive, and at times a little scary. It's easy to feel like an imposter when the tool produces in an hour what would take me days.

It was far from perfect, though. Claude Code often misread what I meant in the specs and requirements. It wrote a test that demanded an effect show up at every single policy level when the spec only described a trend. It aimed another test at the wrong statistic, and it guessed numbers like chart counts instead of checking them. The most serious case: it wrote four text-coding rules from its own knowledge of the data generator, which quietly leaked the answer key into the analysis. None of these were obvious from the output alone. They only surfaced because the specs had testable requirements and I kept asking where things came from.

That shaped what my job actually was: mostly reviewing and making sure everything worked. I wrote and corrected specs, answered design questions, accepted or pushed back on test changes, and checked results. I wrote very little code directly.

I've used ChatGPT, Cursor, and Claude in an AI-assisted way before, where I stay in the code and the AI suggests or fills in. The agentic approach flips that. I worked at the level of plans and evidence, and the code was something I inspected rather than wrote. It's much faster, but only trustworthy if the specs are precise and the validation is strong. Spec-driven development also made context management practical: clearing the session between phases cost almost nothing because HANDOFF.md carried the state, and a long session cost about 8× more tokens for the same task.
