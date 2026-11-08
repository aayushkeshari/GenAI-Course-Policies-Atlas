# P2 — Analysis

Outputs go to `results/*.json`. Every number on the dashboard must come from these files.

- **ANL-01** Cleaning (`src/analysis/clean.py`): dedupe, normalize casing, keep missing policy as NA
  (no imputation), write `data/clean/`. Log row counts before and after.
- **ANL-02** Codebook `docs/codebook.md` defines stance and theme codes with inclusion/exclusion rules
  and examples. `code_text.py` applies it with transparent rules (keyword/phrase patterns, no LLM calls),
  so every coding decision can be traced to a rule.
- **ANL-03** Coder vs ground truth: per-label precision/recall/F1 and a stance confusion matrix.
  Target macro-F1 ≥ 0.80. If it falls short, report the actual number honestly. Do not tune against the test set:
  split statements into a dev half (for tuning rules) and a held-out half (for reporting).
- **ANL-04** Human agreement (HUMAN task): generate `data/reference/hand_code_sample.csv` with 30 held-out
  statements and blank label columns. Aayush fills it in. Report Cohen's kappa for human vs coder and human vs truth.
- **ANL-05** Descriptives with 95% bootstrap CIs (2,000 resamples, fixed seed): policy distribution by level,
  by is_se, by term; stance and theme prevalence by carnegie and year.
- **ANL-06** Association: chi-square + Cramér's V for policy × level and policy × is_se.
- **ANL-07** Ordinal logistic regression: policy ~ level + is_se + term_index + control + carnegie
  (statsmodels OrderedModel). Report coefficients, 95% CIs, and n used.
- **ANL-08** Recovery tests: estimated directions match DATA-06..09, and the DATA-10 null is not significant
  at α = 0.05. These tests may read ground_truth.json; analysis code may not.
- **ANL-09** `results/` JSON files follow schemas in `src/report/schemas/`, validated by tests.
- **ANL-11** Allowed-uses analysis (RQ6): prevalence of each use by level and by is_se, with bootstrap CIs.
  A recovery test checks that the intro-course gap between explanation/debugging and code_generation (DATA-15) shows up.
- **ANL-12** Assessment analysis (RQ7): assessment_adaptation by policy level and course level, with chi-square and Cramér's V.
- **ANL-13** Rhetoric vs practice (RQ8): per institution, compare coded statement stance with mean course permissiveness
  (both standardized). Report the correlation and list institutions whose gap is in the top decile. A recovery test
  checks how many of the DATA-17 mismatched institutions land in that list (report precision/recall).
- **ANL-14** Clustering: course-term rows are nested in courses and institutions, so they are not independent.
  Every inferential result on course data (ANL-05 CIs, ANL-07 regression, ANL-08 recovery and null tests,
  ANL-11, ANL-12) must account for clustering by `inst_id`. Use cluster-robust (sandwich) SEs, a mixed model
  with an institution random effect, or a cluster bootstrap that resamples institutions. `docs/methods.md`
  states which method was used for each result. A test checks that the DATA-10 null stays non-significant
  under the clustered method, since naive row-level tests can flag sampling noise in institution effects
  as a real effect.
- **ANL-10** `docs/methods.md` describes the approach in plain language, including the limits of
  synthetic data and keyword coding.
