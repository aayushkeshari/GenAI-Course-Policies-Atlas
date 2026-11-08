# RUNBOOK — copy-paste path through the whole project

Claude Code writes all the code. You paste prompts, approve, and do the five small human tasks
marked YOUR TURN (about 1 hour in total). Pro plan limits will probably spread this over a few days.
Run /prep-clear → /clear → /resume whenever a phase ends or a session gets long.

Tip: Shift+Tab cycles Claude Code's permission modes. Use auto-accept edits during implementation
to cut down on approval clicks, and plan mode when you ask for a plan.

## 0. Setup (terminal)
```bash
mkdir genai-cs-policy && cd genai-cs-policy
unzip ~/Downloads/p2-agentic-kit.zip && cp -r kit/. . && rm -rf kit
git init && git add -A && git commit -m "human: import spec drafts (drafted with Claude chat)"
# create an empty public GitHub repo named genai-cs-policy, then:
git remote add origin https://github.com/<you>/genai-cs-policy.git && git push -u origin main
claude
```
In Claude Code, use `/model` to pick Opus.

YOUR TURN #1 (10 min): read the specs and change at least one thing you disagree with or want differently.
Commit it with `human: revise specs — <what>`.

## P0 — Instrumentation
```
Read specs/00-overview.md and specs/P0-instrumentation.md. Propose a plan for P0. Don't write code yet.
```
```
Approved. Implement P0 completely, run make test, and show me the result. Stop only if the spec is ambiguous.
```
Check that logging works: send any prompt, run `/compact`, then `!tail -5 logs/events.jsonl`.
Then `/prep-clear` → `/clear` → `/resume`.

## P1 — Data   (`!echo "P1:data" > .phase` first)
```
Go: plan P1 from specs/P1-data.md, then implement it after I approve. Show me 5 sample rows from each CSV and the ground_truth.json effects.
```
YOUR TURN #2 (5 min): skim the sample rows. Do they look plausible? Note anything odd in docs/review-log.md
and tell Claude to fix it. Then `/prep-clear` → `/clear` → `/resume`.

## P2 — Analysis   (`!echo "P2:analysis" > .phase`)
```
Implement specs/P2-analysis.md through ANL-03, then generate the ANL-04 hand-coding sample and stop.
```
YOUR TURN #3 (15–20 min): fill in data/reference/hand_code_sample.csv yourself, without looking at the coder's labels.
```
I've finished the hand-coding sample. Finish P2 (ANL-04 to ANL-10). Show me the recovery test results and coder F1.
```
`/prep-clear` → `/clear` → `/resume`

## P3 — Dashboard   (`!echo "P3:writing-code" > .phase`)
```
Implement specs/P3-dashboard.md. When done, run make serve and give me the local URL.
```
YOUR TURN #4 (10 min): open the dashboard. Pick one chart and check its numbers against results/*.json by hand.
Log the check in docs/review-log.md. `/prep-clear` → `/clear` → `/resume`

## P4 — Validation   (`!echo "P4:validation" > .phase`)
```
Implement specs/P4-validation.md, including make faults. Report the fault detection rate and list any uncaught faults.
```
Ask Claude why each uncaught fault slipped through, and have it add tests if needed.
Log one test you read yourself in review-log. `/prep-clear` → `/clear` → `/resume`

## P5 — Timeline   (`!echo "P5:writing-code" > .phase`)
```
Implement specs/P5-provenance.md. Show me the contribution counts per actor.
```
Write the 3–5 sentence contribution narrative (PROV-05) yourself.

## P6 — Tokens   (`!echo "P6:writing-code" > .phase`)
```
Implement TOK-01 to TOK-04 and TOK-08 from specs/P6-tokens.md.
```
YOUR TURN #5: pick the experiment task (e.g. "add a pub_type filter to the dashboard"). Run it 2× in each condition
(long session / after /clear+/resume / after /compact), reverting with git between runs. Tag each run with
`!echo "P6:exp-A1" > .phase` etc. Then:
```
Analyze the TOK-05 experiment runs (phase tags P6:exp-*) and build the token page (TOK-06, TOK-07).
```

## P7 — Publish   (`!echo "P7:docs" > .phase`)
```
Implement specs/P7-publish.md and run make prepublish. Tell me exactly which GitHub setting I need to change for Pages.
```
In the GitHub repo settings, set Pages to deploy from GitHub Actions, then push.

## Finish — evaluation and reflection (yours)
```
Collect facts for my evaluation: for each goal G1–G5, list evidence links, test counts, the fault detection rate,
token totals by phase, and the clear/compact experiment results. Facts only, no judgments.
```
Write docs/evaluation.md and the reflection yourself, commit with `human:`, and push.
