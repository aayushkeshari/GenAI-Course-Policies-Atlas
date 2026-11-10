# Methods

> **SYNTHETIC DATA.** Real university names are attached to invented policies and statements. Nothing here
> describes what these schools actually do. Every course, statement and number is invented by
> `src/data/generate.py`, and the results describe the generator, not real US computer science departments.
> The data is synthetic so the analysis can be checked against a known truth.

This page explains in plain language how the analysis works. The numbers themselves are in `results/*.json`,
and each of those files has a schema in `src/report/schemas/`. They aren't repeated here, so this page can't
go out of date.

## 1. Data and cleaning (ANL-01)
There are three tables: 150 institutions (real university names, invented data), about 350 official statements, and about 2,000 course-term
rows covering fall 2023 to fall 2026 (see `docs/data-dictionary.md`). Cleaning:
- drops exact duplicate rows
- lowercases the `level` column
- adds a term index (0 for F23, up to 6 for F26)

A missing policy is **left missing**. Nothing is imputed, and every analysis that uses policy drops those rows
and reports how many it dropped. `results/clean_log.json` records the row counts before and after.

## 2. Coding the statements (ANL-02, ANL-03, ANL-04)
Statements are coded for **stance** (−2 prohibited … +2 embraced) and three **themes**: integrity,
collaboration, careers. The coder uses keyword and phrase rules (`src/analysis/code_text.py`); there's no
machine learning and no LLM. Each code records the rule that produced it, and `docs/codebook.md` defines every
code and lists every rule.

**Honest evaluation.** The statements are split by institution into a **dev** half (even inst_id) and a
**held-out** half (odd inst_id).
- Rules were written and tuned on the dev half only. Every rule must cite text from a dev statement, and a test
  enforces this.
- The rules were then frozen, and the held-out half was scored once (`results/coder_eval.json`).
- A third of the held-out wording never appears in the dev half, so the held-out score measures how well the
  rules generalize to new wording. It is reported for statements with and without that unseen wording.
- Tests check that the coder never opens the truth file, and that its dev results don't change when the
  held-out labels are scrambled.

**Human check.** Aayush hand-coded 30 held-out statements using only the codebook definitions.
`results/kappa.json` reports Cohen's kappa as "Aayush vs coder" and "Aayush vs truth".

## 3. Why clustering matters (ANL-14)
A department's courses share one institution: the same culture, the same committee, often the same rules. Rows
from one institution are therefore not independent, and treating them as independent makes estimates look more
precise than they are. In the synthetic data, a naive analysis declares a public/private difference "significant"
on some random seeds, even though the generator plants **no** such effect. It does the same for a
Baccalaureate-college effect. Every inferential result therefore accounts for clustering by institution
(`inst_id`):

| Result | File | Inference method |
|---|---|---|
| Policy, stance and theme descriptives (ANL-05) | `results/descriptives.json` | 95% **cluster bootstrap** CIs: institutions resampled with replacement, 2,000 resamples, fixed seed, percentile intervals |
| Allowed uses (ANL-11) | `results/allowed_uses.json` | cluster bootstrap, as above, including the intro learning-vs-generation gap |
| Assessment shares and association (ANL-12) | `results/assessment.json` | cluster bootstrap CIs for shares, and for Cramér's V (the main inference); the chi-square p-value is reported but labelled **naive** |
| Policy × level, policy × SE association (ANL-06) | `results/association.json` | Cramér's V with a cluster bootstrap CI (main); chi-square p-value labelled **naive** |
| Ordinal logistic regression (ANL-07) | `results/regression.json` | **cluster-robust (sandwich) standard errors grouped by inst_id** (main). Naive SEs are shown alongside, and a cluster bootstrap with 500 refits cross-checks the sandwich SEs |
| Rhetoric vs practice (ANL-13) | `results/rhetoric.json` | institutions are the units of analysis; the correlation CI comes from a bootstrap over institutions, which is the cluster bootstrap at this level |
| Recovery checks (ANL-08) | `results/recovery.json` | uses the clustered regression CIs above |

## 4. The analyses
- **Descriptives (ANL-05):**
  - the share of each policy level, and the mean policy, by course level, by SE vs non-SE, by term, by census region, and overall
  - coded stance and theme prevalence by Carnegie class, by year, by census region, and overall
  - census regions are compared instead of states: with about three synthetic institutions per state, a state average is mostly noise
- **Allowed uses (ANL-11):** how often each use (explanation, debugging, code generation, testing, writing) is allowed, by level and by SE, among courses that allow AI at all.
- **Assessment (ANL-12):** which assessment adaptations appear at each policy level and course level.
- **Association (ANL-06):** chi-square and Cramér's V for policy against level, and policy against SE.
- **Regression (ANL-07):** an ordinal logistic regression of policy on level, SE, term, control and Carnegie class. The references are intro, public and R1. Each effect is also expressed as a multiple of the per-term trend, a scale-free number that can be compared with the generator's settings.
- **Rhetoric vs practice (ANL-13):** for each institution, its average coded stance and its average course policy, both standardized. Institutions where the two disagree most (the top 10% by gap) are listed.

## 5. Checking against the truth (ANL-08, ANL-13 recovery)
Only `src/evaluation/` and the tests may read the hidden truth file; analysis code may not, and a test enforces
this. The recovery checks ask four questions:
- **Direction:** do the planted effects (DATA-06 to DATA-09) come out the right way round?
- **Null:** is the planted non-effect of public vs private non-significant under clustering?
- **Size:** is each effect, as a multiple of the per-term trend, within 25% of the planted value? Does its
  clustered 95% CI contain the planted value on at least 4 of 5 random seeds?
- **Rhetoric gap:** how many of the deliberately mismatched institutions (DATA-17) appear in the rhetoric-gap
  list? This is reported as precision and recall.

## 6. Limits
**Of synthetic data:**
- The data was generated from a simple model with effects chosen in advance. Real departments have messier,
  correlated and unmeasured influences.
- Recovering the truth here shows that the pipeline works. It shows nothing about real universities.
- Statements are built from fixed phrase banks, so they are far more uniform than real policy text.

**Of keyword coding:**
- The rules only recognize wording close to what they were built from. New wording usually falls through:
  stance defaults to 0 and themes to false.
- Negations and hedges are handled only where a rule was written for them.
- Known error (found in P3, not fixed): a prohibition word inside a negation that no dev rule covers flips the
  stance. "Far from banning chatbots, our curriculum makes them central…" matches the `S-2-ban` rule and is
  coded −2 (prohibitive) when it is enthusiastic. The dev half contains only one negated prohibition ("AI use is
  not prohibited"), which has its own rule, and no "far from"-style wording. A general negation rule would have
  had to be written from the held-out example, which would be tuning on held-out data, so the rules stay frozen.
  The flip is the worst kind of coder error for ANL-13, because it moves an institution to the opposite end of
  the stance scale. Some institutions in the rhetoric-gap list may be there because of coding errors rather
  than a real mismatch. The dashboard's institution drilldown says so and shows the statements so a reader can check.
- The person who wrote the rules also wrote the generator, so they had seen the held-out wording. Tests block
  direct copying, but the held-out score may still be slightly optimistic.

**Of the methods:**
- The ordinal regression uses a logit link, while the generator's noise is normal and rounded. Effect ratios
  come out a little smaller than planted (attenuation); the recovery checks allow for this.
- Bootstrapped Cramér's V is biased upward (V can't go below 0), so its interval leans high.
- "Mean course permissiveness" in ANL-13 is a raw average and isn't adjusted for each institution's mix of course
  levels.
- The 22 planted mismatch institutions sit at opposite extremes and largely cancel the overall stance–policy
  correlation, even though the two are linked for most institutions.
