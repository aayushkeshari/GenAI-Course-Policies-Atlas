# 00 — Overview

## Goals (from the assignment)
- G1 Synthetic data + analysis + dashboard on genAI policy and rhetoric in US CS departments and SE courses
- G2 Validation explorer that convinces a skeptical reviewer the code is correct
- G3 Timestamped record of human vs Claude contributions, including prompts and responses
- G4 Token usage report, including the effects of /clear, /compact, and different project steps
- G5 Everything published on GitHub and the web

## Research questions (answered with synthetic data)
- RQ1 How are students permitted or encouraged to use genAI, by course level?
- RQ2 How do official department publications talk about AI?
- RQ3 Is the tone positive, neutral, or negative, and is it shifting over time?
- RQ4 Do publications frame AI as a collaborator?
- RQ5 How do software engineering courses differ from other CS courses?
- RQ6 Do policies separate using AI to *learn* (explanations, debugging help) from using AI to *produce graded work*
  (writing code that gets submitted)? This is the line students and TAs actually deal with in intro courses.

## Phases
| Phase | Spec | Output |
|---|---|---|
| P0 | P0-instrumentation.md | hooks, logging, Makefile skeleton, test-report plumbing |
| P1 | P1-data.md | deterministic synthetic data generator + ground truth |
| P2 | P2-analysis.md | cleaning, text coding, statistics, results JSON |
| P3 | P3-dashboard.md | findings dashboard |
| P4 | P4-validation.md | validation explorer, traceability, fault injection |
| P5 | P5-provenance.md | contribution timeline and Q&A log |
| P6 | P6-tokens.md | token usage report and clear/compact experiment |
| P7 | P7-publish.md | landing page, redaction, GitHub Pages |

## Requirement IDs
Formatted `- **AREA-NN** text` (areas: INST, DATA, ANL, DASH, VAL, PROV, TOK, PUB). The validation
explorer parses these lines, so keep the format exact.

## Definition of done (every phase)
All of the phase's requirements are covered by passing tests, the progress entry is written,
HANDOFF is updated, and Aayush has logged at least one review in docs/review-log.md.

## Repo layout
```
CLAUDE.md  Makefile  requirements.txt  .phase
specs/  docs/  src/{data,analysis,report,tokens,provenance}/  tests/
data/{raw,clean,reference}/  results/  logs/  raw_logs/(gitignored)  site/
```
